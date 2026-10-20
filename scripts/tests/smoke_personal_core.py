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
    calls = 0

    def invoke(tool, args, *, expected="success"):
        nonlocal calls
        calls += 1
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

    for title in (
        "Routines smoke: review",
        "Routines smoke: practice",
        "Routines smoke: prepare",
    ):
        invoke(
            "organizer_add", {"kind": "task", "title": title, "due_date": "yesterday"}
        )
    copy = {"source_date": "yesterday", "target_date": "today", "expected_count": 3}
    copied = invoke("organizer_copy_tasks", copy)
    assert copied["copied"] == 3 and all(i["status"] == "open" for i in copied["items"])
    assert invoke("organizer_copy_tasks", copy)["already_present"] == 3
    invoke("organizer_copy_tasks", {**copy, "expected_count": 2}, expected="failed")
    assert invoke("organizer_list", {"kind": "task", "period": "today"})["total"] == 3
    bindings = [
        {"record_id": i["record_id"], "expected_version": i["version"]}
        for i in copied["items"]
    ]
    repeated = invoke(
        "organizer_set_recurrence", {"items": bindings, "recurrence": "daily"}
    )["items"]
    assert (
        invoke(
            "organizer_list",
            {"kind": "task", "period": "tomorrow", "query": "Routines smoke"},
        )["total"]
        == 3
    )
    bindings = [
        {
            "record_id": i["record_id"],
            "expected_version": i["version"],
            "occurrence_date": i["occurrence_date"],
        }
        for i in repeated
    ]
    invoke("organizer_set_recurrence", {"items": bindings, "recurrence": "none"})
    assert (
        invoke(
            "organizer_list",
            {"kind": "task", "period": "tomorrow", "query": "Routines smoke"},
        )["total"]
        == 0
    )
    daily = invoke(
        "organizer_add",
        {"kind": "task", "title": "Daily smoke reading", "recurrence": "daily"},
    )["item"]
    binding = {
        "record_id": daily["record_id"],
        "expected_version": 1,
        "occurrence_date": daily["occurrence_date"],
    }
    done = invoke("organizer_update", {**binding, "status": "done"})["item"]
    tomorrow = invoke(
        "organizer_list", {"kind": "task", "period": "tomorrow", "query": "Daily smoke"}
    )
    assert tomorrow["total"] == 1 and tomorrow["items"][0]["status"] == "open"
    invoke(
        "organizer_update",
        {**binding, "expected_version": done["version"], "recurrence": "none"},
    )
    assert (
        invoke(
            "organizer_list",
            {"kind": "task", "period": "tomorrow", "query": "Daily smoke"},
        )["total"]
        == 0
    )
    assert (
        invoke(
            "organizer_list",
            {
                "kind": "task",
                "period": "today",
                "status": "done",
                "query": "Daily smoke",
            },
        )["total"]
        == 1
    )
    print(
        f"Native personal smoke passed: {calls} separate Core processes, local date {clock['local_date']}; isolated test data only."
    )


if __name__ == "__main__":
    main()
