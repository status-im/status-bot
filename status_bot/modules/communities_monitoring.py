import logging

from status_bot.modules.base import BaseModule, ModuleType
from status_bot.models import Community, Channel

logger = logging.getLogger(__name__)

class CommunitiesMonitoring(BaseModule):

    DESCRIPTION = """
        This module look at the differents community the Bot has access to and monitores
        the enabled on.
    """
    @property
    def module_type(self) -> ModuleType:
        return ModuleType.PERIODIC

    def on_start(self):
        logger.info("Starting module CommunityMonitoring")
        pass

    def execute(self):
        if self.ctx.db is None:
            return
        logger.info("Executing module CommunityMonitoring")
        with self.ctx.db.session() as session:
            for c in self.ctx.account.communities:
                tags = ",".join(tag["name"] for tag in c["tags"])
                community = Community(
                    id = c["id"],
                    url = c["url"],
                    name = c["name"],
                    verified = c["verified"],
                    tags = tags,
                    is_member = c["is_member"],
                    joined = c["joined"],
                    joined_timestamp = c["joined_timestamp"],
                    requested_timestamp = c["requested_timestamp"],
                    encrypted = c["encrypted"],
                    number_members = c["members"],
                )
                logger.info(f"Community : {community}")
                session.merge(community)
                for ch in c.get("channels", []):
                    permissions = ch.get("permissions", {})
                    session.merge(Channel(
                        id=ch["id"],
                        chat_id=ch["chat_id"],
                        name=ch["name"],
                        description=ch["description"],
                        community_id=community.id,
                        can_post=permissions.get("posting", False),
                        can_view=permissions.get("viewing", False),
                        can_post_reaction=permissions.get("canPostReactions", False),
                        token_gated=permissions.get("posting", False),
                    ))
            session.commit()
