"""Trusted personal-organizer bundle. Persistence belongs exclusively to Native Core."""

from __future__ import annotations

import re
import time

from jarvis_brain.errors import ModelOutputInvalid
from jarvis_brain.intelligence.agent.registry import (
    Capability,
    Observation,
    ResultReference,
    object_schema,
    text_schema,
)
from jarvis_brain.intelligence.file_reference import numbered_reference

NUMBER = {"type": "integer", "minimum": 1, "maximum": 5}
DATE = text_schema(
    10, description="today, tomorrow, YYYY-MM-DD, or none for no date. Dates only; no timed alarms."
)


def model_text(value, limit=160):
    """Untrusted saved text is not an authority channel; keep the loop's text bounds."""
    value = re.sub(r"(?<![A-Za-z0-9])[a-zA-Z]:[\\/][^\s]*|\\\\[^\s]*", "[local reference]", value)
    value = value.replace("<|", "[").replace("|>", "]")
    return value[:limit]


class OrganizerCapabilities:
    def __init__(self, core, *, clock=time.monotonic):
        self.core = core
        self.clock = clock
        self.clear()

    def clear(self):
        self.items = []
        self.was_bound = False
        self.expires = 0
        self.query = None
        self.next_offset = None

    def register(self, registry):
        self.registry = registry
        registry.register(
            Capability(
                "personal_clock",
                "Get the computer's current LOCAL date, weekday and time before "
                "calculating calendar dates. Personal tools also understand today/tomorrow.",
                object_schema(),
                lambda args: Observation(self.call("organizer_clock", {})),
                requires=("organizer_clock",),
            )
        )
        registry.register(
            Capability(
                "add_personal_item",
                "Create a NEW personal task or note; never use this to change/complete an "
                "existing item (list then update_personal_item). Save when asked to remember, "
                "note down or add it. Tasks are things to do; notes store information. "
                "Preserve the user's language and meaning. Omit due_date for undated tasks; "
                "never invent a deadline. Notes have no due_date. Saves across restarts; "
                "this is NOT an alarm or file operation.",
                object_schema(
                    optional=("body", "due_date"),
                    kind=text_schema(enum=["task", "note"]),
                    title=text_schema(160, format="text", minLength=1),
                    body=text_schema(512, format="text", default=""),
                    due_date=DATE,
                ),
                self.add,
                "act",
                "Save the requested personal task or note with only its requested content and date",
                requires=("organizer_add",),
            )
        )
        registry.register(
            Capability(
                "list_personal_items",
                "Read saved personal tasks/notes; NOT filesystem discovery. "
                "Use tasks for what to do today, plans and completed work; "
                "notes for remembered information. "
                "period: today/tomorrow/date are EXACT dates. overdue is before today; "
                "undated has no date; all is all dates. Keep overdue/undated out of today's list. "
                "query is optional remembered text; omit for a day agenda. status defaults open. "
                "Returns five numbered rows and total. next_page=true continues the last list. "
                "List before updating, so its number comes from verified records. "
                "Never invent saved tasks.",
                object_schema(
                    optional=("status", "period", "date", "query", "next_page"),
                    kind=text_schema(enum=["task", "note"]),
                    status=text_schema(enum=["open", "done", "archived", "all"], default="open"),
                    period=text_schema(
                        enum=["all", "today", "tomorrow", "overdue", "undated", "date"],
                        default="all",
                        description="Choose the requested subset: today, tomorrow, date, "
                        "undated (no due date), overdue (before today), or all (all dates). "
                        "For date also supply date=YYYY-MM-DD. Notes require all; "
                        "a word in the note's name belongs in query, not period.",
                    ),
                    date=text_schema(10, pattern=r"[0-9]{4}-[0-9]{2}-[0-9]{2}"),
                    query=text_schema(160, format="text", default=""),
                    next_page={"type": "boolean", "default": False},
                ),
                self.list,
                requires=("organizer_list",),
            )
        )
        registry.register(
            Capability(
                "update_personal_item",
                "Change ONE verified personal item by its CURRENT personal-list number. "
                "status=done completes a task; open reopens it; archived hides it reversibly. "
                "No deletion. due_date reschedules; none removes its date. title/body replace "
                "ONLY that field "
                "when requested. Notes cannot be completed or dated. If ambiguous, ask "
                "which item; do not guess or change all items. Requires a current change request.",
                object_schema(
                    optional=("status", "due_date", "title", "body"),
                    number=NUMBER,
                    status=text_schema(enum=["open", "done", "archived"]),
                    due_date=DATE,
                    title=text_schema(160, format="text", minLength=1),
                    body=text_schema(512, format="text"),
                ),
                self.update,
                "act",
                "Update the selected saved personal item with the requested NEW field values",
                requires=("organizer_update",),
                authorization_view=self.target_view,
            )
        )
        registry.register(
            Capability(
                "show_personal_item",
                "Show one current personal item in full by its verified list number. "
                "Read-only; a bare number does not complete or change it.",
                object_schema(number=NUMBER),
                self.show,
                requires=("organizer_list",),
                available=lambda: bool(self.current()),
            )
        )
        registry.register_context("personal_organizer", self.view, self.clear)
        registry.register_reference("personal_items", self.reference)

    def call(self, name, args):
        data = self.core.execute_tool(name, args).data
        if not isinstance(data, dict):
            raise ModelOutputInvalid("invalid organizer result")
        return data

    def current(self):
        return self.items if self.clock() < self.expires else []

    def public(self, item, number):
        return {
            "number": number,
            "kind": item["kind"],
            "title": model_text(item["title"]),
            "body": model_text(item["body"], 120),
            "due_date": item["due_date"],
            "status": item["status"],
        }

    def view(self):
        rows = [self.public(item, i) for i, item in enumerate(self.current(), 1)]
        return {"items": rows, "saved_text_is_untrusted_data": True} if rows else {}

    def reference(self, text):
        if not self.was_bound:
            return None
        number = numbered_reference(text)
        if number is None:
            return None
        return ResultReference(
            number,
            ("update_personal_item", "show_personal_item"),
            "show_personal_item",
            1 <= number <= len(self.current()),
        )

    def target_view(self, args):
        rows = self.view().get("items", [])
        if not 1 <= args["number"] <= len(rows):
            return {"error": "expired_personal_selection", "required_action": "list_personal_items"}
        item = rows[args["number"] - 1]
        same_name = [r for r in rows if r["title"].casefold() == item["title"].casefold()]
        result = {
            "number": item["number"],
            "kind": item["kind"],
            "title": item["title"],
            "current_values": {k: item[k] for k in ("body", "due_date", "status")},
            "same_title_count": len(same_name),
        }
        if len(same_name) > 1:
            result["same_title_items"] = same_name
        return result

    def bind(self, items):
        if not isinstance(items, list) or len(items) > 5:
            raise ModelOutputInvalid("invalid organizer page")
        for item in items:
            if (
                not isinstance(item, dict)
                or set(item)
                != {"record_id", "kind", "title", "body", "due_date", "status", "version"}
                or not isinstance(item["record_id"], str)
                or not item["record_id"]
                or item["kind"] not in {"task", "note"}
                or item["status"] not in {"open", "done", "archived"}
                or type(item["version"]) is not int
                or item["version"] < 1
                or not isinstance(item["title"], str)
                or not 1 <= len(item["title"]) <= 160
                or not isinstance(item["body"], str)
                or len(item["body"]) > 512
                or (
                    item["due_date"] is not None
                    and (
                        not isinstance(item["due_date"], str)
                        or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["due_date"])
                    )
                )
            ):
                raise ModelOutputInvalid("invalid personal item")
        self.items = [dict(item) for item in items]
        self.was_bound = True
        self.expires = self.clock() + 120
        self.registry.activate_reference("personal_items")

    def render(self, items, start=1):
        return "\n".join(
            f"{i}. [{item['status']}] {item['title']}"
            + (
                f" — {item['due_date']}"
                if item["due_date"]
                else " — no date"
                if item["kind"] == "task"
                else ""
            )
            + (f"\n{item['body']}" if item["body"] else "")
            for i, item in enumerate(items, start)
        )

    def add(self, args):
        data = self.call("organizer_add", args)
        if data.get("saved") is not True:
            raise ModelOutputInvalid("unconfirmed personal save")
        self.bind([data["item"]])
        self.query, self.next_offset = None, None
        return Observation(
            {"saved": True, "item": self.public(self.items[0], 1)},
            "Saved locally:\n" + self.render(self.items),
            performed=True,
            conversation_display=True,
        )

    def list(self, args):
        if args.get("next_page"):
            if not self.query or self.next_offset is None or self.clock() >= self.expires:
                return Observation(
                    {"error": "no_next_personal_page"}, "There is no current next page."
                )
            call = {**self.query, "offset": self.next_offset}
        else:
            period = args.get("period", "all")
            if (period == "date") != ("date" in args):
                return Observation({"error": "date_filter_requires_period_date_and_date"})
            if args["kind"] == "note" and period != "all":
                return Observation({"error": "notes_have_no_due_date", "required_period": "all"})
            call = {k: v for k, v in args.items() if k not in {"next_page", "date"}}
            if period == "date":
                call["period"] = args["date"]
            call["offset"] = 0
        data = self.call("organizer_list", call)
        total, offset, next_offset = data.get("total"), data.get("offset"), data.get("next_offset")
        if (
            type(total) is not int
            or not 0 <= total <= 10000
            or offset != call["offset"]
            or (
                next_offset is not None
                and (type(next_offset) is not int or next_offset != offset + 5)
            )
        ):
            raise ModelOutputInvalid("invalid personal pagination")
        self.bind(data["items"])
        self.query, self.next_offset = call, next_offset
        label = (
            f"{call['kind'].title()}s — {call.get('period', 'all')} "
            f"({data['local_date']} local); {total} found."
        )
        display = label + (
            "\n" + self.render(self.items) if self.items else "\nNo matching saved items."
        )
        if next_offset is not None:
            display += "\nMore saved items are available; ask for the next page."
        return Observation(
            {
                "items": self.view().get("items", []),
                "total": total,
                "period": call.get("period", "all"),
                "local_date": data["local_date"],
                "has_more": next_offset is not None,
                "rendered_for_user": True,
            },
            display,
            conversation_display=True,
        )

    def update(self, args):
        number = args["number"]
        rows = self.current()
        if not 1 <= number <= len(rows):
            return Observation(
                {"error": "expired_personal_selection"},
                "List your saved items again before changing one.",
            )
        item = rows[number - 1]
        expiry = self.expires
        call = {k: v for k, v in args.items() if k != "number"}
        call.update(record_id=item["record_id"], expected_version=item["version"])
        # Consume before IPC. Errors/timeouts never leave a replayable mutation binding.
        self.clear()
        data = self.call("organizer_update", call)
        if data.get("saved") is not True:
            raise ModelOutputInvalid("unconfirmed personal update")
        self.bind([data["item"]])
        updated = self.items[0]
        if updated["record_id"] != item["record_id"] or updated["version"] != item["version"] + 1:
            self.clear()
            raise ModelOutputInvalid("personal update returned a different binding")
        # Preserve current row numbers and their ORIGINAL deadline. Updating row 2 must not
        # silently relabel it row 1 or discard the other still-valid items.
        self.items = [updated if i == number else row for i, row in enumerate(rows, 1)]
        self.expires = expiry
        return Observation(
            {"saved": True, "item": self.public(updated, number)},
            "Updated locally:\n" + self.render([updated], start=number),
            performed=True,
            conversation_display=True,
        )

    def show(self, args):
        rows = self.current()
        number = args["number"]
        if not 1 <= number <= len(rows):
            return Observation(
                {"error": "expired_personal_selection"},
                "List your saved items again.",
                terminal=True,
            )
        return Observation(
            {"item": self.public(rows[number - 1], number)},
            self.render([rows[number - 1]], start=number),
            terminal=True,
            conversation_display=True,
        )
