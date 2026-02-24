from clients.status_backend import StatusBackend
import os, json, argparse
import constants

def main(username: str, password: str):
    os.makedirs(constants.CREDENTIALS_PATH, exist_ok=True)
    file_path = os.path.join(constants.CREDENTIALS_PATH, f"{username}.json")
    if os.path.exists(file_path):
        return

    backend = StatusBackend(**constants.STATUS_BACKEND_PARAMS)
    info = backend.initialize()
    
    params = {
        "display_name": username,
        "password": password
    }
    
    backend.create_account_and_login(**params)
    info = backend.wait_for_login()

    data = {
        "event": info["event"],
        "created_at": info["timestamp"],
        "credentials": params
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    backend.logout()

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Login script")
    parser.add_argument(
        "-u", "--username",
        required=True,
        help="Status App login username"
    )
    parser.add_argument(
        "-p", "--password",
        required=True,
        help="Status App local password"
    )
    args = parser.parse_args()
    main(args.username, args.password)