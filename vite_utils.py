import json
from pathlib import Path
from urllib.request import urlopen


def is_vite_dev_running() -> bool:
    # We launch this once at server start
    # so we don't care if it's synchronous
    try:
        with urlopen("http://localhost:5173/@vite/client"):
            return True
    except Exception:
        return False


def get_main_js_manifest() -> dict | None:
    # If vite server is running it gets precedence
    # over the manifest file
    if is_vite_dev_running():
        return None

    manifest_path = Path("./dist/.vite/manifest.json")
    if not manifest_path.exists():
        raise Exception("Manifest file not found")

    with open(manifest_path, "r") as manifest_file:
        json_file = json.load(manifest_file)

        return json_file["resources/main.js"]
