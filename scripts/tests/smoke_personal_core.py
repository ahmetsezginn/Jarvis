"""Opt-in fixed Native Core CLI smoke, isolated under target; no user's organizer touched."""

import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4


def main():
    root = Path(__file__).resolve().parents[2]
    target = (root / "target").resolve()
    data_root = (target / f"personal-smoke-{uuid4().hex}").resolve()
    data_root.relative_to(
        target
    )  # All generated test data must remain inside this workspace.
    executable = target / "organizer-validation/debug/jarvis-core.exe"
    if not executable.is_file():
        raise RuntimeError(
            "Build Core with --target-dir target/organizer-validation first"
        )
    data_root.mkdir()
    env = {**os.environ, "LOCALAPPDATA": str(data_root)}

    def invoke(tool, args, *, expected="success"):
        result = subprocess.run(
            [str(executable), "tool", tool, json.dumps(args)],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
        output = json.loads(result.stdout)
        assert output["status"] == expected, output.get("error")
        assert result.returncode == (0 if expected == "success" else 1)
        return output["data"]

    clock = invoke("organizer_clock", {})
    empty = invoke("organizer_list", {"kind": "task", "period": "today"})
    assert not empty["items"] and not (data_root / "JARVIS").exists()
    saved = invoke(
        "organizer_add",
        {"kind": "task", "title": "Smoke appointment", "due_date": "tomorrow"},
    )["item"]
    invoke(
        "organizer_add",
        {
            "kind": "note",
            "title": "Smoke location",
            "body": "The spare cable is in the green box.",
        },
    )
    assert invoke("organizer_list", {"kind": "task", "period": "today"})["total"] == 0
    page = invoke("organizer_list", {"kind": "task", "period": "tomorrow"})
    assert page["total"] == 1 and page["items"][0]["record_id"] == saved["record_id"]
    update = {"record_id": saved["record_id"], "expected_version": 1, "status": "done"}
    assert invoke("organizer_update", update)["item"]["version"] == 2
    assert (
        invoke("organizer_list", {"kind": "task", "period": "tomorrow"})["total"] == 0
    )
    assert invoke("organizer_list", {"kind": "task", "status": "done"})["total"] == 1
    assert "green box" in invoke("organizer_list", {"kind": "note"})["items"][0]["body"]
    invoke("organizer_update", update, expected="failed")
    print(
        f"Native personal smoke passed: 11 separate Core processes, local date {clock['local_date']}; isolated test data only."
    )


if __name__ == "__main__":
    main()
