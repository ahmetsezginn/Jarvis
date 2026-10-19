"""Synthetic personal metadata for unit/opt-in model tests; never opens files or a database."""

from copy import deepcopy
from datetime import date, timedelta

from jarvis_brain.errors import CoreToolError
from jarvis_brain.ipc.protocol import ToolResult

from scripts.evaluation.analyze_file_assistance import SyntheticCore


class PersonalCore(SyntheticCore):
    today = date(2026, 10, 18)

    def __init__(self):
        super().__init__()
        self.records = []

    def seed(self, title, *, kind="task", due_date="today", body="", status="open"):
        item = {
            "record_id": f"private-record-{len(self.records) + 1}",
            "kind": kind,
            "title": title,
            "body": body,
            "due_date": self.resolve_date(due_date) if kind == "task" else None,
            "status": status,
            "version": 1,
        }
        self.records.append(item)
        return item

    def resolve_date(self, value):
        if value in ("", "none"):
            return None
        if value in ("today", "tomorrow"):
            return (self.today + timedelta(days=value == "tomorrow")).isoformat()
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as error:
            raise CoreToolError("invalid_arguments", "invalid calendar date") from error

    def execute_tool(self, tool, args):
        if not tool.startswith("organizer_"):
            return super().execute_tool(tool, args)
        self.calls.append({"tool": tool, "arguments": deepcopy(args)})
        if tool == "organizer_clock":
            data = {
                "local_date": self.today.isoformat(),
                "weekday": "Sunday",
                "local_time": "2026-10-18T12:00:00+03:00",
                "scheduled_notifications": False,
            }
        elif tool == "organizer_add":
            data = {"saved": True, "item": self.seed(**{"due_date": "none", **args})}
        elif tool == "organizer_list":
            period, status = args.get("period", "all"), args.get("status", "open")
            if args["kind"] == "note" and period != "all":
                raise CoreToolError("invalid_arguments", "notes require period all")
            rows = [
                r
                for r in self.records
                if r["kind"] == args["kind"]
                and (status == "all" or r["status"] == status)
            ]
            if period == "undated":
                rows = [r for r in rows if r["due_date"] is None]
            elif period == "overdue":
                rows = [
                    r
                    for r in rows
                    if r["due_date"] and r["due_date"] < self.today.isoformat()
                ]
            elif period != "all":
                rows = [r for r in rows if r["due_date"] == self.resolve_date(period)]
            words = args.get("query", "").casefold().split()
            rows = [
                r
                for r in rows
                if all(w in (r["title"] + " " + r["body"]).casefold() for w in words)
            ]
            offset = args.get("offset", 0)
            data = {
                "local_date": self.today.isoformat(),
                "period": period,
                "total": len(rows),
                "offset": offset,
                "next_offset": offset + 5 if offset + 5 < len(rows) else None,
                "items": rows[offset : offset + 5],
            }
        elif tool == "organizer_update":
            item = next(
                (r for r in self.records if r["record_id"] == args["record_id"]), None
            )
            if item is None or item["version"] != args["expected_version"]:
                raise CoreToolError("invalid_arguments", "stale personal item")
            for field in ("title", "body", "status", "due_date"):
                if field in args:
                    item[field] = (
                        self.resolve_date(args[field])
                        if field == "due_date"
                        else args[field]
                    )
            item["version"] += 1
            data = {"saved": True, "item": item}
        else:
            raise AssertionError(tool)
        return ToolResult("fixture", tool, "success", deepcopy(data), None)
