"""Opt-in actual game launch via the existing catalog/IPC/policy, no direct OS launcher."""

import argparse
import json
from pathlib import PureWindowsPath

from jarvis_brain.core.client import JarvisCoreClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--folder", required=True)
    parser.add_argument("--launch", action="store_true")
    args = parser.parse_args()
    folder = PureWindowsPath(args.folder)
    with JarvisCoreClient(request_timeout=30) as core:
        data = core.execute_tool(
            "search_files", {"query": args.name, "extension": "url"}
        ).data
        matches = [
            entry
            for entry in data["entries"]
            if entry["name"].casefold() == args.name.casefold()
            and PureWindowsPath(entry["location"].removeprefix("\\\\?\\")).parent
            == folder
        ]
        if len(matches) != 1:
            raise RuntimeError(
                "No unique shortcut in the requested folder; nothing launched"
            )
        result = {"name": matches[0]["name"], "matched": True, "opened": False}
        if args.launch:
            opened = core.execute_tool(
                "open_file", {"entry_id": matches[0]["entry_id"]}
            ).data
            if opened.get("opened") is not True:
                raise RuntimeError("Core did not accept shortcut opening")
            result["opened"] = True
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
