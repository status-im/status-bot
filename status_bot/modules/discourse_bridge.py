import requests, datetime, time, traceback
import pandas as pd
from html_to_markdown import convert as convert_to_markdown
from status_bot.modules.base import BaseModule, ModuleType
from status_sdk import Community, Channel
from typing import Optional

class Discourse:

    def __init__(self, base_url: str, username: Optional[str] = None, api_key: Optional[str] = None, img_size: int = 120):
        if base_url.endswith("/"):
            base_url = base_url[:-1]

        self.__base_url = base_url
        self.__img_size = img_size
        self.__headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self.__has_api = bool(api_key and username)
        if self.__has_api:
            self.__headers.update({
                "Api-Key": api_key,
                "Api-Username": username,
            })

    @property
    def base_url(self) -> str:
        return self.__base_url

    def get_topics(self) -> pd.DataFrame:
        """
        Get all public Discourse topics

        Output:
            - Currently available public topics
        """
        url = f"{self.__base_url}/latest.json"
        response = requests.get(url, headers=self.__headers)
        output: dict = response.json()

        data = pd.DataFrame(output["topic_list"]["topics"])

        columns = ["id", "slug", "title", "posts_count", "closed", "archived", "created_at", "last_posted_at"]
        data = data[columns]
        data = data.assign(
            **{date_column: pd.to_datetime(data[date_column]) for date_column in columns[-2:]},
            url = self.__base_url + "/t/" + data["slug"],
            channel_description = self.__base_url + "/t/" + data["id"].astype(str),
            is_open = ~(data["closed"] | data["archived"])
         ).sort_values("last_posted_at", ascending=False)\
            .drop(["closed", "archived"], axis=1)\
            .reset_index(drop=True)

        return data.copy()

    def get_posts(self, topic_id: int) -> pd.DataFrame:
        """
        Get all posts for the given topic ID.

        Parameters:
            - `topic_id` - the topic ID from `get_topics`

        Output:
            - The posts for the selected topic
        """
        url = f"{self.__base_url}/t/{topic_id}.json"
        response = requests.get(url, headers=self.__headers)
        output: dict = response.json()

        errors: list[str] = output.get("errors", [])
        if errors:
            error_msg = "\n- ".join(errors)
            raise Exception(f"Invalid URL {url}\n- {error_msg}")

        columns = ["id", "post_number", "reply_to_post_number", "user_id", "username", "cooked", "avatar_template", "post_url", "created_at", "updated_at"]
        posts = pd.DataFrame(output["post_stream"]["posts"])[columns]
        posts = posts.assign(
            avatar_template = posts["avatar_template"].apply(lambda slug: self.__base_url + slug.format(size=self.__img_size)),
            post_url = self.__base_url + posts["post_url"],
            cooked = posts["cooked"].apply(lambda html_text: convert_to_markdown(html_text).content),
            **{date_column: pd.to_datetime(posts[date_column]) for date_column in columns[-2:]},
        ).rename(columns={
            "id": "post_id",
            "avatar_template": "image_url",
            "reply_to_post_number": "reply_to",
            "cooked": "markdown_text"
        })
        posts.insert(0, "topic_id", topic_id)
        posts.insert(0, "id", posts.apply(lambda row: f"{row['topic_id']}-{row['post_id']}", axis=1))
        id_mapping = posts[["id", "post_number"]].set_index("post_number").to_dict()["id"]
        posts["reply_to"] = posts.apply(
            lambda row: id_mapping.get(None if pd.isna(row["reply_to"]) else int(row["reply_to"]), row["id"]),
            axis=1
        )
        return posts


    def post(self, topic_id: int, text: str, reply_to: Optional[int] = None) -> dict:
        """
        Write a comment to the selected topic.

        Parameters:
            - `topic_id` - the topic ID from `get_topics`
            - `text` - markdown text to be written in the `topic_id`
            - `reply_to` - if the comment is a reply to a previous comment

        Output:
            - the raw POST output
        """
        if not self.__has_api:
            return {}

        url = f"{self.__base_url}/posts.json"
        payload = {
            "topic_id": topic_id,
            "raw": text
        }
        if reply_to and reply_to != 1:
            payload["reply_to_post_number"] = reply_to

        response = requests.post(url, headers=self.__headers, json=payload)
        output: dict = response.json()
        output["post_url"] = self.__base_url + output["post_url"]
        output["avatar_template"] = self.__base_url + output["avatar_template"].format(size=self.__img_size)
        return output



class DiscourseBridge(BaseModule):

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.PERIODIC

    CLOSED_MESSAGE = "This conversation is archived. New messages will not be forwarded!"
    INVALID_CONTENT_TYPE_MESSAGE = "This message has an invalid content type. It will not be forwarded to Discourse!"

    def on_start(self):
        self.discourse = Discourse(self.settings["url"]["discourse"], self.settings["api"]["username"], self.settings["api"]["key"])
        self.community = Community(self.account, url=self.settings["url"]["community"])
        self.table_name = "bridge_info"
        self.discourse_seconds_wait: int = self.settings["delay"]
        self.success_emoji: str = self.settings["emoji_shortname"]
        super().on_start()

    def execute(self):
        current_channels = [community_info["name"] for community_info in self.community.channels]
        topics = self.discourse.get_topics()
        # `owner`, `admin` and `token_master` can set permissions
        is_admin = self.community.role != "none"
        community_name = self.community.name
        self.logger.info(f"{community_name} admin access: {is_admin}")
        for position, topic in enumerate(topics.to_dict("records")):
            topic_name = "-".join(f"{topic['id']}-{topic['slug']}"[:24].split("-")[:-1])
            is_new_topic = topic_name not in current_channels
            if is_new_topic and is_admin:
                self.community.create_channel(topic_name, topic["slug"], category_name=self.settings["category_name"])
                self.logger.info(f"Created # {topic_name} in {self.settings['category_name']}")

            channel = self.community[topic_name]
            current_permissions = channel.permissions

            if len(current_permissions) == 0 and not topic["is_open"] and is_admin:
                channel.add_permission("view")

            if len(current_permissions) > 0 and topic["is_open"] and is_admin:
                for permission_id in current_permissions["id"].to_list():
                    channel.delete_permission(permission_id)

            self.to_status_app(channel, topic, is_new_topic)
            channel.position = position
            self.to_discourse(channel, topic["is_open"], community_name)

    def to_status_app(self, channel: Channel, topic: dict, is_new_topic: bool) -> bool:
        """
        Upload all new messages to the Community Channel and Postgres
        """
        def get_topic_data(topic: dict, is_new: bool) -> pd.DataFrame:
            if is_new:
                return pd.DataFrame()

            query = f"""
            SELECT id, message_id
            FROM {self.db_schema}.{self.table_name}
            WHERE topic_id = {topic['id']}
            """
            return pd.DataFrame(self.ctx.db.fetch_all(query))

        posts = self.discourse.get_posts(topic["id"])
        topic_info = get_topic_data(topic, is_new_topic)
        mapping = {} if is_new_topic else topic_info.set_index("id")["message_id"].to_dict()

        records = []
        uploaded = [] if len(topic_info) == 0 else topic_info["id"].to_list()
        for post in posts.to_dict("records"):
            if post["id"] in uploaded:
                continue
            reply_to = mapping.get(post["reply_to"])
            if post["reply_to"] == post["id"]:
                reply_to = None

            message_id = None
            post_slug: str = post['post_url'].split('/t/')[-1].split("/")[0]
            text = f"Timestamp: **{str(post['created_at']).split('.')[0]} {str(post['created_at'].tz)}**\nSender: **{post['username']}**\nDiscourse Topic: [{post_slug}]({post['post_url']})\n\n{post['markdown_text']}"
            for index in range(0, len(text), self.account.message_length):
                start = index
                end = index + self.account.message_length
                current_message = text[start:end]
                params = {
                    "message": current_message,
                    "reply_to_message_id": reply_to
                }
                if index != 0:
                    params.pop("reply_to_message_id")

                sent_id = channel.send_message(**params)
                if not message_id:
                    message_id = sent_id

                records.append({
                    **post,
                    "markdown_text": current_message,
                    "slug": topic["slug"],
                    "message_id": sent_id,
                    "chat_id": channel.id,
                    "source": "discourse",
                    "is_open": True
                })

            mapping[post["id"]] = message_id

        if records:
            records = pd.DataFrame(records)
            self.ctx.db.insert(records, self.table_name, self.db_schema)
            self.logger.info(f"Uploaded {len(records)} records to {self.db_schema}.{self.table_name} for {topic['url']}")

        return len(records) > 0


    def to_discourse(self, channel: Channel, is_open: bool, community_name: str) -> bool:

        def get_uploaded(channel: Channel) -> pd.DataFrame:
            query = f"""
            SELECT *
            FROM {self.db_schema}.{self.table_name}
            WHERE chat_id = '{channel.id}'
            """
            return pd.DataFrame(self.ctx.db.fetch_all(query))

        info = get_uploaded(channel)

        now = datetime.datetime.now()
        start_timestamp = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_timestamp = now.replace(hour=23, minute=59, second=59, microsecond=0)

        messages = channel.get_messages()
        if not messages:
            return False

        messages = pd.DataFrame(messages)

        query = ~messages["id"].isin(info["message_id"])
        columns = ["id", "text", "image", "album_id", "compressed_key", "content_type", "response_to", "whisper_timestamp"]

        for column in columns:
            if column in messages.columns:
                continue
            messages[column] = None

        new_messages = messages.loc[query, columns].reset_index(drop=True)
        if query.sum() == 0:
            return False

        # Oldest to newest. `.sort_values` is not used in case there are
        # messages sent at once. For example a text message with multiple
        # images, they will have the exact same `whisper_timestamp`
        new_messages= new_messages.iloc[::-1].reset_index(drop=True)
        image_albums = []
        post_number_mapping = info.set_index("message_id")["post_number"].to_dict()
        table_id_mapping = info.set_index("post_number")["id"].to_dict()
        metadata = {
            "topic_id": int(info["topic_id"].iloc[0]),
            "slug": info["slug"].iloc[0],
            "chat_id": channel.id,
        }
        records = []
        for new_message in new_messages.to_dict("records"):
            timestamp: pd.Timestamp = new_message["whisper_timestamp"]
            text: str = new_message["text"]
            is_invalid_content_type = new_message["content_type"] not in self.settings["content_type"]
            # Default appearance in Status App
            display_name = new_message["compressed_key"][:3] + "..." + new_message["compressed_key"][-6:]
            text = f"Sender: **{display_name}**\nURL: [{community_name} # {channel.name}]({channel.url})\n\n{text}"

            if not is_open or is_invalid_content_type:
                common_info = {
                    "is_open": False,
                    "source": "status",
                    **metadata
                }
                bot_message = self.INVALID_CONTENT_TYPE_MESSAGE if is_invalid_content_type else self.CLOSED_MESSAGE
                msg_id = channel.send_message(bot_message, new_message["id"])
                records += [
                    {**common_info, "markdown_text": text, "message_id": new_message["id"], "created_at": timestamp},
                    {**common_info, "markdown_text": bot_message, "message_id": msg_id, "created_at": datetime.datetime.now()},
                ]
                continue

            # Process one image per album - text is the same
            album_id = new_message.get("album_id")
            if pd.isna(album_id):
                album_id = None

            if album_id in image_albums:
                continue

            reply_to = post_number_mapping.get(new_message["response_to"], 1)
            if album_id:
                image_albums.append(new_message["album_id"])
                # TO DO: download images and upload with `.post`
                image_urls = new_messages.loc[new_messages["album_id"] == new_message["album_id"], "image"].to_list()

            try:
                output = self.discourse.post(metadata["topic_id"], text, reply_to)
                if not output:
                    self.logger.warning(f"API key for {self.discourse.base_url} not found... Message '{new_message['id']}' was not uploaded to Discourse.")
                    continue
                point = {
                    "id": f"{metadata['topic_id']}-{output['id']}",
                    "topic_id": metadata["topic_id"],
                    "post_id": output["id"],
                    "post_number": output["post_number"],
                    "reply_to": table_id_mapping[reply_to],
                    "user_id": output['user_id'],
                    "username": output['username'],
                    "markdown_text": text,
                    "image_url": output["avatar_template"],
                    "post_url": output["post_url"],
                    "created_at": timestamp,
                    "updated_at": pd.Timestamp(output["created_at"]),
                    "slug": metadata["slug"],
                    "message_id": new_message["id"],
                    "chat_id": metadata["chat_id"],
                    "source": "status",
                    "is_open": True
                }
                records.append(point)
                post_number_mapping.update({point["message_id"]: point["post_number"]})
                table_id_mapping.update({point["post_number"]: point["id"]})
                channel.send_emoji_reaction(point["message_id"], self.success_emoji)
                self.logger.info(f"Waiting {self.discourse_seconds_wait}s")
                time.sleep(self.discourse_seconds_wait)
            except Exception as e:
                self.logger.error(f"\n{traceback.format_exc()}")

        if not records:
            return False

        records = pd.DataFrame(records)
        self.ctx.db.insert(records, self.table_name, self.db_schema)
        self.logger.info(f"Uploaded {len(records)} records to {self.db_schema}.{self.table_name} for # {channel.name}")
        return True
