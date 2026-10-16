"""Bounded file-goal dialogue with trusted Core discovery and explicit result feedback."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, replace

from jarvis_brain.errors import CoreToolError
from jarvis_brain.intelligence.contract import BrainResponse, IntentName, IntentResult
from jarvis_brain.intelligence.dialogue import TurnPlan
from jarvis_brain.intelligence.file_session import FileSession, normalized


@dataclass
class FileGoal:
    query: str = ""
    location: str = ""
    depth: str = "default"
    category: str = "any"
    extension: str = ""
    sort: str = "name"
    operation: str = "find"
    kind: str = "file"
    application: str = ""
    name_unknown: bool = False


class AssistantSession:
    def __init__(self, files: FileSession, clock=time.monotonic):
        self.files = files
        self.clock = clock
        self.clear()

    def clear(self):
        self.finish_task()
        self.outcome = ""

    def finish_task(self):
        """Discard all task bindings while retaining the last verified outcome."""
        self.goal = None
        self.expires = 0
        self.rejected = []
        self.scope = None
        self.question = ""
        self.question_slot = ""
        self.last_search = None

    def view(self):
        if self.clock() >= self.expires:
            self.finish_task()
        g = self.goal
        return {
            "goal": (
                {
                    "query": g.query,
                    "location": g.location,
                    "depth": g.depth,
                    "category": g.category,
                    "extension": g.extension,
                    "sort": g.sort,
                    "kind": g.kind,
                    "operation": g.operation,
                    "name_unknown": g.name_unknown,
                }
                if g
                else None
            ),
            "rejected_count": len(self.rejected),
            "pending_question": self.question,
            "pending_slot": self.question_slot,
            "last_outcome": self.outcome[:400],
        }

    def explain(self):
        return self.reply(
            (self.outcome or "Henüz bir dosya işlemi yapılmadı.")
            + " Dosya içeriklerini okumuyorum; ad, tür ve klasör "
            "bilgisiyle arıyorum. İsmi bilinmiyorsa klasör ve türle daraltabiliriz."
        )

    def record_outcome(self, response, action):
        # User-facing listings include paths. Keep only an internally chosen action
        # and verified status in model feedback, never the rendered result body.
        self.outcome = action + (
            " tamamlandı." if response.executed else " tamamlanmadı; ek bilgi gerekiyor."
        )

    @staticmethod
    def reply(message, executed=False):
        return BrainResponse(IntentName.CLARIFY, 1, "assistant", executed, message)

    def ask(self, question, slot=""):
        self.question = question
        self.question_slot = slot
        return self.reply(question)

    def file_turn(self, plan: TurnPlan, text: str):
        self.view()
        a = plan.arguments
        prior = self.goal
        if a["relation"] == "new" or prior is None:
            self.goal = FileGoal()
            self.rejected = []
            self.scope = None
        g = self.goal
        if a["relation"] == "reject":
            for e in self.files._entries:
                if e["entry_id"] not in self.rejected:
                    self.rejected.append(e["entry_id"])
            self.rejected = self.rejected[-100:]
            g.query = ""  # A rejected name hypothesis is not evidence for another identical search.
        if a["query"]:
            if a["query"] != g.query and not a["name_unknown"]:
                self.rejected = []
            g.query = a["query"]
        if a["name_unknown"]:
            g.query = ""
        if a["query"] or a["name_unknown"] or a["relation"] == "new":
            g.name_unknown = a["name_unknown"]
        if a["location"]:
            location = "relative" if self.files.is_relative(a["location"]) else a["location"]
            if normalized(location) != normalized(g.location):
                self.scope = None
            g.location = location
        if a["depth"] not in {"keep", "default"} or a["relation"] == "new":
            g.depth = a["depth"]
        if a["category"] != "any" or a["relation"] == "new":
            g.category = a["category"]
        if a["extension"] or a["relation"] == "new":
            g.extension = a["extension"]
        if a["sort"] != "keep":
            g.sort = a["sort"]
        g.application = a["application"]
        if a["relation"] == "reject":
            g.operation = "find"
        elif a["operation"] != "keep":
            g.operation = a["operation"]
        elif g.operation == "open":
            g.operation = "find"
        if a["kind"] != "any" or a["relation"] == "new":
            g.kind = a["kind"]
        self.expires = self.clock() + 120
        self.question = ""
        self.question_slot = ""
        # For a relative reference bind only a current trusted directory, never a guessed path.
        if normalized(g.location) == "relative":
            entries = self.files._entries
            if len(entries) == 1 and entries[0]["kind"] == "directory":
                self.scope = entries[0]
            elif self.files._scope and self.clock() < self.files._scope_expires:
                self.scope = self.files._scope
            if not self.scope:
                return self.ask("Hangi klasörün içinde arayayım? Klasörün adını söyler misin?")
        if self.scope is None:
            # A new unscoped goal cannot advertise or reuse an older task's directory.
            # Explicit relative requests above are the only way to inherit that binding.
            self.files._scope = None
            self.files._scope_expires = 0
        if not g.query and not g.location and not g.extension and g.sort == "name":
            self.files._clear_selection()
            return self.ask(
                "İsmini hatırlaman gerekmiyor. Hangi klasöre kaydetmiş olabilirsin: "
                "masaüstü, indirilenler veya başka bir klasör mü?",
                "location",
            )
        if (
            not g.query
            and g.category == "any"
            and not g.extension
            and g.sort == "name"
            and g.operation != "list"
            and not (g.operation == "open" and g.kind == "directory")
        ):
            self.files._clear_selection()
            return self.ask(
                "Nasıl bir dosyaydı: metin notu, PDF, tablo, sunum veya fotoğraf mı?", "category"
            )
        try:
            self.files._clear_selection()
            return self._discover(g)
        except CoreToolError as error:
            self.files._clear_selection()
            self.scope = None
            self.outcome = "Son dosya işlemi tamamlanamadı; açıldığı doğrulanmadı."
            return self.files._failure(error)

    def _resolve_location(self, name):
        aliases = {
            "desktop": "Masaüstü",
            "masa ustu": "Masaüstü",
            "masaustu": "Masaüstü",
            "downloads": "İndirilenler",
            "download": "İndirilenler",
            "documents": "Belgeler",
            "document": "Belgeler",
        }
        value = normalized(name)
        if re.fullmatch(r"masa\s*ustu(?:nde|ne|ndeki|mde|mdeki|m|me)?", value):
            name = "Masaüstü"
        elif re.fullmatch(r"indirilenler(?:de|e|deki|im|imde)?", value):
            name = "İndirilenler"
        elif re.fullmatch(r"belgeler(?:de|e|deki|im|imde)?", value):
            name = "Belgeler"
        query = aliases.get(normalized(name), name)
        data = self.files._call("search_files", {"query": query, "kind": "directory", "limit": 20})
        entries = [e for e in self.files._validate_entries(data) if e["kind"] == "directory"]
        exact = [e for e in entries if normalized(e["name"]) == normalized(query)]
        matches = exact or list(entries)
        if len(matches) == 1:
            return matches[0]
        self.files._clear_selection()
        return None

    def _discover(self, g):
        if g.location and self.scope is None:
            self.scope = self._resolve_location(g.location)
            if self.scope is None:
                self.outcome = f"{g.location} klasörünü tek bir hedef olarak belirleyemedim."
                return self.ask(self.outcome + " Klasörün daha ayırt edici adını söyler misin?")
        opening_folder = g.operation == "open" and g.kind == "directory"
        if (g.operation == "list" or opening_folder) and self.scope is None:
            # A named folder can be the query rather than an explicit location slot.
            self.scope = self._resolve_location(g.query)
            if self.scope is None:
                return self.ask("Hangi klasör? Birden fazla eşleşme olabilir; adını netleştirelim.")
        if self.scope:
            self.files._set_scope(self.scope)
        if opening_folder:
            result = self.files._open(self.scope)
            self.record_outcome(result, "Klasör açma")
            self.finish_task()
            return result
        if g.operation == "list":
            result = self.files._list(self.scope)
            self.outcome = f"{self.scope['name']} klasörünün doğrudan içeriğini listeledim."
            return replace(result, message=self.outcome + "\n" + result.message)
        args = {
            "query": g.query or "*",
            "sort": g.sort,
            "kind": None if g.kind == "any" else g.kind,
            "limit": 20,
        }
        if g.extension:
            args["extension"] = g.extension
        elif g.category != "any" and g.kind != "directory":
            args["category"] = g.category
        if self.scope:
            args["folder_id"] = self.scope["entry_id"]
            args["recursive"] = g.depth == "recursive" or (
                g.depth in {"default", "keep"}
                and normalized(self.scope["name"]) not in {"masaustu", "masa ustu", "desktop"}
            )
        elif g.depth == "direct":
            return self.ask("Alt klasörlere girmeden bakmam için hangi klasörü kullanayım?")
        if self.rejected:
            args["exclude_ids"] = list(self.rejected)
        signature = repr(sorted(args.items()))
        if signature == self.last_search and g.name_unknown:
            return self.ask(
                self.outcome + " " + "Arama adı yerine klasör veya türü değiştirebiliriz. "
                "Başka bir klasöre bakmamı ister misin?",
                "clue",
            )
        self.last_search = signature
        self.files._clear_selection()
        data = self.files._call("search_files", args)
        entries = self.files._validate_entries(data)
        # One bounded read-only recovery: topic may not be in the filename. Never auto-open.
        recovered = False
        if not entries and g.query and self.scope and (g.category != "any" or g.extension):
            args["query"] = "*"
            data = self.files._call("search_files", args)
            entries = self.files._validate_entries(data)
            recovered = True
        place = self.scope["name"] if self.scope else "izinli klasörler"
        depth = " (alt klasörler dahil)" if args.get("recursive") else ""
        self.outcome = (
            f"{place}{depth} içinde "
            + (f"‘{g.query}’ adıyla" if g.query and not recovered else "dosya türüne göre")
            + f" aradım; {data['total']} sonuç bulundu."
        )
        if not entries:
            self.question = "Başka bir klasör veya dosya türü hatırlıyor musun?"
            self.question_slot = "clue"
            return self.reply(
                self.outcome
                + (" Tarama kısmi." if data.get("partial") else "")
                + " "
                + self.question,
                True,
            )
        # Opening requires a positive current operation and a unique explicit filename clue.
        if g.operation == "open" and g.query and not recovered and data["total"] == 1:
            result = self.files._open_with(entries[0], g.application or None)
            self.record_outcome(result, "Dosya açma")
            self.finish_task()
            return result
        self.files._pending = IntentName.OPEN_FILE
        if g.operation == "open":
            self.files._application = g.application or None
        result = self.files._observe(data, IntentName.SEARCH_FILES, ("search_files", args))
        prefix = self.outcome
        if recovered:
            prefix += " Ad eşleşmediği için aynı klasörde türüne göre de baktım."
        if g.sort == "newest":
            prefix += " Sıralama değiştirilme zamanına göre; indirilme zamanını doğrulayamıyorum."
        return replace(result, message=prefix + "\n" + result.message)

    def select(self, plan, text):
        a = plan.arguments
        if a["number"] == 0:
            # Affirmation may confirm only a concrete retained browser choice.
            if self.files._confirmation:
                result = self.files.handle(text, preserve_unmatched=True)
                if result is not None:
                    self.record_outcome(result, "Seçili dosyayı açma")
                    return result
            if len(self.files.model_candidates()) != 1:
                return self.ask("Hangisini kastettin? Geçerli listedeki numarayı veya adı seç.")
            a = {**a, "number": self.files.model_candidates()[0].number}
        result = IntentResult(IntentName.SELECT_FILE, plan.confidence, a)
        if a["action"] == "show":
            if not self.files.accepts_number(a["number"]):
                return self.ask("Bu seçim için geçerli sonuç yok; önce dosyayı bulalım.")
            entry = self.files._entries[a["number"] - 1]
            response = self.files._observe(
                {"entries": [entry], "total": 1}, IntentName.SEARCH_FILES
            )
            return replace(response, executed=False)
        # Existing Google-to-Chrome clarification remains a concrete selection, not a global app.
        if normalized(a["application"]) == "google" and self.files.accepts_number(a["number"]):
            self.files._confirmation = self.files._entries[a["number"] - 1]
            self.files._application = "Google Chrome"
            return self.ask("Bu dosyayı Google Chrome ile yerel olarak açmamı mı istiyorsun?")
        response = self.files.select_displayed(result)
        self.record_outcome(
            response,
            {"open": "Seçili öğeyi açma", "parent": "Üst klasörü açma", "list": "Klasör listeleme"}[
                a["action"]
            ],
        )
        self.finish_task()
        return response
