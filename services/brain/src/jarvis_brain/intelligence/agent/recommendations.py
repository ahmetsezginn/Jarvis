"""Session-only presentation bindings. The model ranks metadata; this stores its choice."""

import re

from jarvis_brain.intelligence.agent.registry import Observation


class Recommendations:
    def __init__(self, files, apps):
        self.files, self.apps = files, apps
        self.clear()

    def clear(self):
        self.rejected = {}
        self.mode = "none"
        self.selected = None
        self.needs_presentation = False

    def begin_turn(self):
        self.needs_presentation = False

    def answer_feedback(self, message=""):
        # A prose enumeration cannot silently change the visible recommendation into a list.
        # This checks presentation syntax and actual catalog names, not the user's intent.
        rows = self.remaining()
        lines = [
            line
            for line in message.splitlines()
            if re.match(r"\s*(?:[0-9]+[.)]|[-*\u2022])\s+", line)
        ]
        listed = {
            r["key"] for r in rows if any(r["name"].casefold() in line.casefold() for line in lines)
        }
        folded = message.casefold()
        spans = sorted(
            (folded.find(name.casefold()), len(name.casefold()))
            for name in {row["name"] for row in rows}
            if name.casefold() in folded
        )
        inline_list = any(
            ("," in separator or ";" in separator) and re.fullmatch(r"[\s,;]+", separator)
            for (start, length), (next_start, _) in zip(spans, spans[1:], strict=False)
            if (separator := folded[start + length : next_start])
        )
        if self.mode != "all" and (inline_list or (len(lines) > 1 and len(listed) > 1)):
            self.needs_presentation = True
        if self.needs_presentation and rows:
            return {
                "error": "presentation_selection_required",
                "required_actions": ["suggest_result", "show_results"]
                + (["reject_suggestion"] if self.proposed() else []),
                "instruction": "If the CURRENT request asks for a list, all options or folder "
                "contents, choose show_results. Otherwise choose suggest_result(number) for one "
                "best tentative match, not a prose enumeration. If replacing a rejected "
                "suggestion, first record its rejection with reject_suggestion.",
            }
        return None

    def confirm(self, args):
        row = self.proposed()
        if row is None or row["number"] != args["number"]:
            return Observation({"error": "no_matching_suggestion"})
        return Observation(
            {"status": "identified", "identified": self.metadata(row)},
            f"Found it: {row['name']}.",
            terminal=True,
        )

    def new_page(self):
        self.mode = "none"
        self.selected = None

    def _prune(self):
        now = self.files._clock()
        self.rejected = {key: value for key, value in self.rejected.items() if now < value[1]}

    def records(self):
        self._prune()
        apps = self.apps.pending_candidates()
        if apps:
            return [
                {
                    "number": i,
                    "name": c.name,
                    "kind": "application",
                    "location": "Installed app",
                    "key": ("app", c.app_id),
                    "expires": self.apps._expires,
                }
                for i, c in enumerate(apps, 1)
            ]
        self.files.model_candidates()  # Expire the private page before any UI binding.
        return [
            {
                "number": number,
                "name": entry["name"],
                "kind": entry["kind"],
                "location": entry["location"],
                "key": ("file", entry["entry_id"]),
                "expires": self.files._expires,
            }
            for number, entry in enumerate(self.files._entries, 1)
        ]

    def remaining(self):
        return [r for r in self.records() if r["key"] not in self.rejected]

    @staticmethod
    def metadata(record):
        return {key: record[key] for key in ("number", "name", "kind")}

    def candidates(self):
        allowed = {c.number for c in self.files.model_candidates()}
        return [
            self.metadata(r)
            for r in self.remaining()
            if r["kind"] == "application" or r["number"] in allowed
        ]

    def proposed(self):
        if not self.selected:
            return None
        key, expiry = self.selected
        if self.files._clock() >= expiry:
            self.new_page()
            return None
        return next((r for r in self.remaining() if r["key"] == key), None)

    def view(self):
        proposed = self.proposed()
        names = []
        budget = 1000
        for name, _expiry in reversed(list(self.rejected.values())):
            if len(names) >= 20 or len(name) > budget:
                break
            names.append(name)
            budget -= len(name)
        return {
            "presentation": self.mode,
            **({"suggested": self.metadata(proposed)} if proposed else {}),
            "rejected_names": names,
            "identity_confirmation_is_not_opening_permission": True,
        }

    def notice(self):
        lines = []
        if self.files._page_info.get("partial"):
            lines.append("Partial catalog: files outside the scanned scope may be missing.")
        if self.files._scope and self.files._clock() < self.files._scope_expires:
            lines.append(f"Search folder: {self.files._scope['name']}.")
        return "\n".join(lines)

    def suggest(self, args):
        previous = self.proposed()
        if previous and previous["number"] != args["number"]:
            self.needs_presentation = True
            return Observation(
                {
                    "error": "suggestion_transition_required",
                    "instruction": "If the user rejected the previous suggestion, first call "
                    "reject_suggestion for its number. Do not silently replace or forget it.",
                    "previous": self.metadata(previous),
                },
                retryable=True,
            )
        row = next((r for r in self.remaining() if r["number"] == args["number"]), None)
        if row is None:
            return Observation({"error": "expired_or_rejected_result"})
        self.selected = (row["key"], row["expires"])
        self.mode = "single"
        self.needs_presentation = False
        question = f"Could {row['name']} be the one you're looking for?"
        notice = self.notice()
        return Observation(
            {"status": "suggested", "suggested": self.metadata(row)},
            question + ("\n" + notice if notice else ""),
            terminal=True,
            memory_message=question,
        )

    def reject(self, args):
        row = self.proposed()
        if row is None or row["number"] != args["number"]:
            return Observation({"error": "no_matching_suggestion"})
        if not self._reject(row):
            return Observation(
                {"error": "rejection_limit", "message": "Refine or reset this search."}
            )
        self.new_page()
        self.needs_presentation = True
        remaining = self.candidates()
        data = {"status": "rejected", "name": row["name"], "remaining": remaining}
        if not remaining:
            data["page_exhausted"] = True
            data["search_performed"] = False
            data["recovery"] = (
                "This only removed one suggestion from the OLD result page; it did not search "
                "with the current user's new clues. Empty remaining results are not evidence "
                "that no other files exist. If the user changed filename assumptions or supplied "
                "location/type clues, search again using those clues, dropping invalid old name "
                "filters while retaining explicit scope and rejected identities."
            )
        return Observation(data)

    def _reject(self, row):
        if len(self.rejected) >= 100 and row["key"] not in self.rejected:
            return False
        self.rejected[row["key"]] = (row["name"], row["expires"])
        return True

    def excluded_files(self, reject_previous=False):
        if reject_previous:
            proposed = self.proposed()
            for row in [proposed] if proposed else self.visible_records():
                if row and not self._reject(row):
                    return None
        self._prune()
        return [key[1] for key in self.rejected if key[0] == "file"]

    def visible_records(self):
        if self.mode == "all":
            return self.remaining()
        proposed = self.proposed()
        return [proposed] if self.mode == "single" and proposed else []

    def items(self):
        return [
            {key: row[key] for key in ("number", "name", "kind", "location")}
            for row in self.visible_records()
        ]
