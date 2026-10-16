"""Built-in adapters. All machine access goes through CoreToolClient, never OS APIs."""

from __future__ import annotations

from dataclasses import asdict

from jarvis_brain.errors import CoreToolError, ModelOutputInvalid
from jarvis_brain.intelligence.agent.presentation import file_page, operation_failure
from jarvis_brain.intelligence.agent.registry import (
    Capability,
    CapabilityRegistry,
    Observation,
    ResultReference,
    object_schema,
    text_schema,
)
from jarvis_brain.intelligence.contract import IntentName, IntentResult
from jarvis_brain.intelligence.file_reference import numbered_reference
from jarvis_brain.intelligence.file_session import FileSession, normalized
from jarvis_brain.intelligence.orchestrator import IntentOrchestrator
from jarvis_brain.intelligence.session import SelectionSession

NUMBER = {"type": "integer", "minimum": 1, "maximum": 20}


class BuiltinCapabilities:
    def __init__(self, core, files=None):
        self.core = core
        self.files = files or FileSession(core)
        self.apps = IntentOrchestrator(core)
        self.app_choices = SelectionSession(clock=self.files._clock)
        self._last_discovery = {}
        self.clear_app_context()

    def registry(self):
        """A future trusted capability bundle registers the same objects; no loop edits."""
        registry = CapabilityRegistry(
            [
                Capability(
                    "find_files",
                    "Search local file/folder NAMES in permitted catalog roots, not contents. "
                    "All filters are optional but a name, folder, type or sorting clue is needed. "
                    "query is short dictionary-form name/topic words, spelling corrected "
                    "if needed. "
                    "For unknown filenames omit query and use known folder/type clues, not a "
                    "guessed filename. Do not guess folders/extensions from topic. location is a "
                    "human folder name; "
                    "current uses a bound folder. Default: ALL permitted roots in ONE call, no "
                    "inventory prerequisite. recursive defaults to true; false means direct "
                    "children. "
                    "sort=name/newest/largest. exclude_previous omits rejected results. "
                    "ALL query words must match; zero results: retry fewer words/remove inferred "
                    "filters, retaining explicit scope. Does not open files.",
                    object_schema(
                        optional=(
                            "query",
                            "location",
                            "kind",
                            "extension",
                            "category",
                            "recursive",
                            "sort",
                            "exclude_previous",
                        ),
                        query=text_schema(default=""),
                        location=text_schema(),
                        kind=text_schema(enum=["file", "directory", "any"], default="file"),
                        extension=text_schema(16, pattern=r"[a-zA-Z0-9]{0,16}"),
                        category=text_schema(
                            enum=["any", "text", "document", "image", "spreadsheet", "presentation"]
                        ),
                        recursive={"type": "boolean", "default": True},
                        sort=text_schema(enum=["name", "newest", "largest"], default="name"),
                        exclude_previous={
                            "type": "boolean",
                            "description": (
                                "Set true when the user rejects the displayed matches. "
                                "Search for other candidates without reintroducing those results."
                            ),
                        },
                    ),
                    self.find_files,
                    requires=("search_files",),
                ),
                Capability(
                    "list_folder",
                    "List a folder's direct children. number is its current result number; "
                    "alternatively location is a known human folder name or current bound folder.",
                    object_schema(
                        optional=("number", "location"), number=NUMBER, location=text_schema()
                    ),
                    self.list_folder,
                    requires=("list_directory", "search_files"),
                ),
                Capability(
                    "open_result",
                    "Open an item by its current result number. Requires a current opening "
                    "request. A pronoun may refer to a single result. Omit application for the "
                    "Windows default; include it only for an explicitly requested app. "
                    "parent=true opens the containing folder instead of the item.",
                    object_schema(
                        optional=("application", "parent"),
                        number=NUMBER,
                        application=text_schema(
                            default="",
                            description=(
                                "Omit/empty: Windows default for supported documents/media. "
                                "Explicit override: local PDF with Chrome or Microsoft Edge. "
                                "Provide only the human app name requested by the user."
                            ),
                        ),
                        parent={"type": "boolean", "default": False},
                    ),
                    self.open_result,
                    "act",
                    "Open the requested file or folder now",
                    requires=("open_file", "open_directory"),
                    authorization_view=self.opening_view,
                ),
                Capability(
                    "next_results",
                    "Fetch the next page of the current results.",
                    object_schema(),
                    self.next_results,
                    requires=("search_files",),
                    available=lambda: bool(self.files.model_candidates() and self.files._page),
                ),
                Capability(
                    "open_app",
                    "Resolve an installed application's human name through Rust and open it.",
                    object_schema(query=text_schema()),
                    self.open_app,
                    "act",
                    "Open the requested installed application now",
                    requires=("resolve_app", "open_app"),
                ),
                Capability(
                    "choose_app",
                    "Open the selected current application candidate by original number. "
                    "Use only for the pending application-opening choice, not file results.",
                    object_schema(number=NUMBER),
                    self.choose_app,
                    "act",
                    "Open the selected pending installed application now",
                    requires=("resolve_app", "open_app"),
                    authorization_view=self.app_choice_view,
                    available=lambda: bool(self.app_choices.pending_candidates()),
                ),
                Capability(
                    "system_status",
                    "Inspect this computer's live CPU, memory and disk status.",
                    object_schema(),
                    self.system_status,
                    requires=("system_status",),
                ),
                Capability(
                    "file_inventory",
                    "Answer questions about catalog scope and file/folder counts. "
                    "Not needed before find_files.",
                    object_schema(),
                    self.inventory,
                    requires=("file_catalog_status",),
                ),
                Capability(
                    "refresh_files",
                    "Refresh the file catalog when requested.",
                    object_schema(),
                    self.refresh_files,
                    "act",
                    "Refresh the file catalog",
                    requires=("refresh_file_catalog",),
                ),
                Capability(
                    "retry_missing_app",
                    "Resume the already requested missing app after a current newly-installed "
                    "follow-up. Refresh once and resolve/open that SAME pending app.",
                    object_schema(),
                    self.retry_missing_app,
                    "act",
                    "Resume the pending app opening after the current installation update",
                    requires=("refresh_app_catalog", "resolve_app", "open_app"),
                    authorization_view=lambda args: {
                        "pending_requested_action": "open_app",
                        "query": self._missing_app,
                    },
                    available=lambda: self.has_missing_app() and not self._created_missing,
                ),
                Capability(
                    "cancel_task",
                    "Cancel the current file task and discard its result bindings.",
                    object_schema(),
                    self.cancel_task,
                ),
                Capability(
                    "refresh_apps",
                    "Refresh the application catalog only; does not resume an opening. "
                    "For an active missing-app installation follow-up use retry_missing_app.",
                    object_schema(),
                    self.refresh_apps,
                    "act",
                    "Refresh the application catalog",
                    requires=("refresh_app_catalog",),
                ),
            ]
        )
        registry.register_context("files", self.context_view, self.clear_files)
        registry.register_context(
            "apps",
            self.app_context,
            self.clear_app_context,
            begin=self.begin_app_turn,
            finish=self.finish_app_turn,
        )
        registry.register_reference("builtin_results", self.result_reference)
        return registry

    def result_reference(self, text):
        number = numbered_reference(text)
        if number is None:
            return None
        apps = self.app_choices.pending_candidates()
        if apps:
            return ResultReference(number, ("choose_app",), "choose_app", 1 <= number <= len(apps))
        return ResultReference(
            number, ("open_result", "list_folder"), "open_result", self.files.accepts_number(number)
        )

    def context_view(self):
        candidates = [asdict(c) for c in self.files.model_candidates()]
        scope = self.files._scope
        result = {"current_results": candidates} if candidates else {}
        if scope and self.files._clock() < self.files._scope_expires:
            result["active_folder"] = scope["name"]
        if self.files._pending is not None and self.files._clock() < self.files._expires:
            result["applied_discovery"] = self._last_discovery
        return result

    def clear_files(self):
        self.files.clear()
        self._last_discovery = {}

    def _folder(self, location):
        if normalized(location) == "current":
            current = self.files._scope
            if current and self.files._clock() < self.files._scope_expires:
                return current, None
            entries = self.files._entries if self.files.model_candidates() else ()
            if len(entries) == 1 and entries[0]["kind"] == "directory":
                return entries[0], None
            return None, Observation({"error": "ambiguous_folder", "message": "Which folder?"})
        if not location:
            return None, None
        result = self.files._call(
            "search_files", {"query": location, "kind": "directory", "limit": 20}
        )
        entries = self.files._validate_entries(result)
        if not entries:
            return None, Observation(
                {
                    "error": "folder_not_found",
                    "requested_folder": location,
                    "message": (
                        "The requested folder was not found in the scanned catalog. "
                        "Do not substitute another folder or global scope; "
                        "ask for a corrected scope."
                    ),
                }
            )
        exact = [e for e in entries if normalized(e["name"]) == normalized(location)]
        matches = exact or list(entries)
        if (
            len(matches) != 1
            or (not exact and result["total"] != 1)
            or result["total"] > len(entries)
        ):
            return None, Observation(
                {
                    "error": "folder_not_unique",
                    "requested_folder": location,
                    "candidates": [{"name": e["name"], "kind": "directory"} for e in entries],
                }
            )
        return matches[0], None

    def _page(self, response, data):
        return Observation(
            {
                "status": "ok",
                "results": [asdict(c) for c in self.files.model_candidates()],
                "scope": self.files._scope["name"] if self.files._scope else "permitted_roots",
                "has_more": bool(self.files._page),
                "applied_filters": self._last_discovery,
            },
            file_page(data, self.files._scope),
            response.executed,
        )

    def find_files(self, args):
        self.app_choices.clear()
        query = args.get("query", "") or "*"
        if query == "*" and not (
            args.get("location")
            or args.get("extension")
            or args.get("category", "any") != "any"
            or args.get("sort", "name") in {"newest", "largest"}
        ):
            return Observation(
                {"error": "missing_clue", "message": "A topic, folder or file type clue is needed."}
            )
        folder, error = self._folder(args.get("location", ""))
        if error:
            return error
        excluded = (
            [e["entry_id"] for e in self.files._entries] if args.get("exclude_previous") else []
        )
        call = {
            "query": query,
            "kind": args.get("kind", "file"),
            "sort": args.get("sort", "name"),
            "limit": 20,
        }
        if call["kind"] == "any":
            call.pop("kind")
        for field in ("extension", "category"):
            if args.get(field) and args[field] != "any":
                call[field] = args[field]
        if folder:
            call["folder_id"] = folder["entry_id"]
            call["recursive"] = args.get("recursive", True)
        elif args.get("recursive") is False:
            return Observation(
                {"error": "folder_required", "message": "Direct-child search requires a folder."}
            )
        if excluded:
            call["exclude_ids"] = excluded
        self.files._clear_selection()
        if folder:
            self.files._set_scope(folder)
        else:
            self.files._scope = None
        data = self.files._call("search_files", call)
        self._last_discovery = {
            "query": query,
            "kind": args.get("kind", "file"),
            "folder_name": folder["name"] if folder else "all_permitted_roots",
            "recursive": args.get("recursive", True),
            "sort": args.get("sort", "name"),
            "category": args.get("category", "any"),
            "extension": args.get("extension", ""),
            "excluded_count": len(excluded),
        }
        response = self.files._observe(data, IntentName.SEARCH_FILES, ("search_files", call))
        observation = self._page(response, data)
        observation.data.update(query=query, total=data["total"], partial=bool(data.get("partial")))
        if not data["total"]:
            observation.data["search_semantics"] = (
                "Filename words/prefixes, not content. A long/inflected query or "
                "an inferred format/category can hide a match; retry fewer topic words, preserving "
                "explicit scope. Zero is not proof of absence."
            )
        return observation

    def list_folder(self, args):
        self.app_choices.clear()
        if "number" in args:
            entry = self._entry(args["number"])
            if entry is None:
                return Observation({"error": "expired_or_invalid_result"})
        else:
            entry, error = self._folder(args.get("location", "current"))
            if error:
                return error
        if not entry or entry["kind"] != "directory":
            return Observation({"error": "directory_required"})
        call = {"entry_id": entry["entry_id"], "limit": 20}
        data = self.files._call("list_directory", call)
        self.files._set_scope(entry)
        response = self.files._observe(data, IntentName.SEARCH_FILES, ("list_directory", call))
        self._last_discovery = {"folder_name": entry["name"], "recursive": False, "kind": "any"}
        return self._page(response, data)

    def _entry(self, number):
        return self.files._entries[number - 1] if self.files.accepts_number(number) else None

    def opening_view(self, args):
        entry = self._entry(args["number"])
        if entry is None:
            return {"error": "expired_or_invalid_result"}
        return {
            "number": args["number"],
            "name": entry["name"],
            "kind": entry["kind"],
            "binding": "unexpired_current_page",
            "candidate_count": len(self.files._entries),
            "application": args.get("application", ""),
            "parent": args.get("parent", False),
        }

    def open_result(self, args):
        entry = self._entry(args["number"])
        if entry is None:
            return Observation({"error": "expired_or_invalid_result"})
        if normalized(args.get("application", "")) == "google":
            concrete = {**args, "application": "Google Chrome"}
            return Observation(
                {"status": "confirmation_required", "application": "Google Chrome"},
                "Open the selected file locally with Google Chrome?",
                terminal=True,
                confirmation=lambda: self.open_result(concrete),
            )
        response = self.files.select_displayed(
            IntentResult(
                IntentName.SELECT_FILE,
                1,
                {
                    "number": args["number"],
                    "action": "parent" if args.get("parent") else "open",
                    "application": args.get("application", ""),
                },
            )
        )
        code = response.data.get("error") if isinstance(response.data, dict) else None
        if response.executed:
            display = (
                f"Opened the folder containing {entry['name']}."
                if args.get("parent")
                else f"Opened {entry['name']}."
            )
        else:
            display = (
                operation_failure(code)
                if code
                else (
                    "This explicit app override is unavailable. Local PDFs support Chrome or Edge; "
                    "omit the app to use the Windows default."
                )
            )
        return Observation(
            {
                "status": "opened" if response.executed else "not_opened",
                **({"error": code} if code else {}),
            },
            display,
            response.executed,
            terminal=True,
        )

    def next_results(self, args):
        if not self.files.model_candidates() or not self.files._page:
            return Observation({"error": "no_next_page"})
        tool, previous = self.files._page
        call = {**previous, "offset": previous.get("offset", 0) + 20}
        data = self.files._call(tool, call)
        return self._page(self.files._observe(data, IntentName.SEARCH_FILES, (tool, call)), data)

    def open_app(self, args):
        self.clear_files()
        self.app_choices.clear()
        response = self.app_choices.observe(
            self.apps.execute(IntentResult(IntentName.OPEN_APPLICATION, 1, args), route="agent")
        )
        self._created_choices = bool(self.app_choices.pending_candidates())
        data = {
            "status": "opened" if response.executed else "not_found_or_ambiguous",
            "query": args["query"],
        }
        if response.intent is IntentName.UNSUPPORTED:
            self._missing_app = args["query"]
            self._missing_expires = self.files._clock() + 120
            self._created_missing = True
        if isinstance(response.data, dict) and isinstance(response.data.get("candidates"), list):
            data["candidates"] = [
                {"name": c["name"]}
                for c in response.data["candidates"]
                if isinstance(c, dict) and isinstance(c.get("name"), str)
            ][:20]
        if response.executed:
            display = f"Opened {args['query']}."
        elif data.get("candidates"):
            display = "Which application?\n" + "\n".join(
                f"{i}. {c['name']}" for i, c in enumerate(data["candidates"], 1)
            )
        else:
            display = f"Application not found in the catalog: {args['query']}."
        return Observation(data, display, response.executed, terminal=response.executed)

    def app_choice_view(self, args):
        choices = self.app_choices.pending_candidates()
        number = args["number"]
        if not 1 <= number <= len(choices):
            return {"error": "expired_or_invalid_application"}
        return {
            "number": number,
            "name": choices[number - 1].name,
            "binding": "unexpired_current_applications",
            "candidate_count": len(choices),
            "pending_requested_action": "open_app",
        }

    def choose_app(self, args):
        choices = self.app_choices.pending_candidates()
        number = args["number"]
        if not 1 <= number <= len(choices):
            return Observation({"error": "expired_or_invalid_application"})
        selected = choices[number - 1]
        self.app_choices.clear()
        response = self.apps.open_selected(selected.name, selected.app_id)
        return Observation(
            {"status": "opened" if response.executed else "not_opened"},
            f"Opened {selected.name}."
            if response.executed
            else operation_failure("application_selection_stale"),
            response.executed,
            terminal=True,
        )

    def system_status(self, args):
        response = self.apps.execute(IntentResult(IntentName.SYSTEM_STATUS, 1, {}), route="agent")
        # Only known numeric status fields enter model feedback, never the full Core envelope.
        raw = response.data.get("data", {}) if isinstance(response.data, dict) else {}
        summary = "System status received from Rust Core."
        if isinstance(raw, dict):
            cpu = raw.get("cpu_usage_percent")
            memory = raw.get("memory", {})
            percent = memory.get("usage_percent") if isinstance(memory, dict) else None
            if type(cpu) in (int, float) and type(percent) in (int, float):
                summary = f"CPU usage {cpu:.1f}%, memory usage {percent:.1f}%."
        data = {"status": "ok", "summary": summary}
        if isinstance(raw, dict):
            for key in ("cpu_usage_percent", "memory"):
                if key in raw:
                    data[key] = raw[key]
        return Observation(data, summary, response.executed)

    def inventory(self, args):
        return self._inventory("file_catalog_status")

    def refresh_files(self, args):
        self.clear_files()
        return self._inventory("refresh_file_catalog")

    def _inventory(self, tool):
        data = self.files._call(tool, {})
        self.files._validate_status(data)
        safe = {key: data[key] for key in ("files", "directories")}
        safe.update(roots=[r["name"] for r in data["roots"]], partial=bool(data.get("partial")))
        return Observation(
            safe, f"Catalog: {safe['files']} files, {safe['directories']} folders.", True
        )

    def refresh_apps(self, args):
        self.core.execute_tool("refresh_app_catalog", {})
        return Observation({"status": "refreshed"}, "Application catalog refreshed.", True)

    def cancel_task(self, args):
        self.clear_files()
        self.clear_app_context()
        return Observation({"status": "cancelled"}, "Pending task cancelled.", terminal=True)

    def clear_app_context(self):
        self.app_choices.clear()
        self._created_choices = False
        self._missing_app = None
        self._missing_expires = 0
        self._created_missing = False

    def has_missing_app(self):
        return bool(self._missing_app and self.files._clock() < self._missing_expires)

    def app_context(self):
        result = {"pending_requested_app": self._missing_app} if self.has_missing_app() else {}
        choices = self.app_choices.pending_candidates()
        if choices:
            result["current_applications"] = [
                {"number": i, "name": c.name} for i, c in enumerate(choices, 1)
            ]
        return result

    def begin_app_turn(self):
        self._created_missing = False
        self._created_choices = False

    def finish_app_turn(self):
        if not self._created_missing:
            self._missing_app = None
            self._missing_expires = 0
        if not self._created_choices:
            self.app_choices.clear()

    def retry_missing_app(self, args):
        query = self._missing_app if self.has_missing_app() else None
        self.clear_app_context()  # Consume the one retry before any Core request.
        if query is None:
            return Observation({"error": "no_pending_application"}, terminal=True)
        self.core.execute_tool("refresh_app_catalog", {})
        result = self.open_app({"query": query})
        self.clear_app_context()
        return result


def execute_capability(capability, arguments):
    """Typed Core errors become bounded model feedback; never expose exception payloads."""
    try:
        observation = capability.handler(arguments)
    except CoreToolError as error:
        return Observation({"error": error.code}, operation_failure(error.code), terminal=True)
    if (
        not isinstance(observation, Observation)
        or type(observation.performed) is not bool
        or type(observation.terminal) is not bool
        or not isinstance(observation.display, str)
        or (
            observation.confirmation is not None
            and (
                not callable(observation.confirmation)
                or not observation.terminal
                or observation.performed
            )
        )
    ):
        raise ModelOutputInvalid("capability returned invalid observation")
    return observation
