from clients.status_backend import StatusBackend
import os, json, argparse, logging
import constants, data_utils

def main(username: str, password: str, logger: logging.Logger):
    os.makedirs(constants.CREDENTIALS_PATH, exist_ok=True)
    file_path = os.path.join(constants.CREDENTIALS_PATH, f"{username}.json")
    if os.path.exists(file_path):
        logger.info(f"There is a JSON file for {username}. Skipping account creation.")
        return

    backend = StatusBackend(**constants.STATUS_BACKEND_PARAMS)
    info = backend.initialize()

    params = {
        "display_name": username,
        "password": password
    }
    logger.info(f"Creating account for {username}")
    backend.create_account_and_login(**params)
    info = backend.wait_for_login()
    logger.info(f"Created account for {username}!")
    data = {
        "event": info["event"],
        "created_at": info["timestamp"],
        "credentials": params
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    logger.info(f"JSON data for {username} saved in {file_path}")
    backend.logout()
    logger.info("Logged out of Status App.")

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Login script")
    parser.add_argument(
        "-u", "--username",
        help="Status App login username"
    )
    parser.add_argument(
        "-p", "--password",
        help="Status App local password"
    )
    args = parser.parse_args()

    params = {
        "username": os.environ.get("STATUS_USERNAME") if not args.username else args.username,
        "password": os.environ.get("STATUS_PASSWORD") if not args.password else args.password,
        "logger": data_utils.get_logger("create-account")
    }

    main(**params)
