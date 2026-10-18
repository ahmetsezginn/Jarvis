"""Core-backed file operations and a bounded selection list; no Python filesystem access."""

from __future__ import annotations

import re
import time
from collections.abc import Callable

from jarvis_brain.errors import CoreToolError, ModelOutputInvalid
from jarvis_brain.intelligence.contract import (
    BrainResponse,
    FileCandidate,
    IntentName,
    IntentResult,
)
from jarvis_brain.intelligence.orchestrator import CoreToolClient

FILE_INTENTS = frozenset(
    {
        IntentName.SEARCH_FILES,
        IntentName.SELECT_FILE,
        IntentName.LIST_FOLDER,
        IntentName.OPEN_FILE,
        IntentName.OPEN_DIRECTORY,
        IntentName.FILE_CATALOG_STATUS,
        IntentName.REFRESH_FILE_CATALOG,
    }
)


def normalized(text: str) -> str:
    return " ".join(
        text.casefold().replace("\u0307", "").translate(str.maketrans("çğıöşü", "cgiosu")).split()
    ).rstrip(".!?")


def negative_open(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:acma|acmayin|acmayalim|acmani istemiyorum|acma lutfen|"
            r"goruntuleme|goruntulemeyin|gosterme|gostermeyin|baslatma|calistirma|"
            r"(?:ac|goruntule|goster|baslat|calistir)(?:mani|meni|mayi|meyi|mak|mek) "
            r"istem(?:iyorum|em)|"
            r"(?:don't|do not|never) (?:open|launch|view|display|show|start|run)|"
            r"cancel|iptal|vazgec)\b",
            normalized(text),
        )
    )


def positive_open(text: str) -> bool:
    """Opening is a side effect: an identity/ownership statement cannot authorize it.

    This checks the current caller's operation words, not target names or model prose.
    Target resolution and the semantic operation decision remain separate requirements.
    Bare numbered UI choices and concrete confirmations have their own bounded contracts.
    """
    if negative_open(text):
        return False
    return bool(
        re.search(
            r"\b(?:ac(?:ar[a-z]*|abilir[a-z]*|man[a-z]*|mak|mayi|sana|in[a-z]*|alim|iver[a-z]*|tir[a-z]*)?"
            r"|goruntule[a-z]*|goster(?:ir[a-z]*|ebilir[a-z]*|men[a-z]*|sene|in[a-z]*|elim)?"
            r"|baslat(?:ir[a-z]*|abilir[a-z]*|man[a-z]*|in[a-z]*)?"
            r"|calistir(?:ir[a-z]*|abilir[a-z]*|man[a-z]*|in[a-z]*)?"
            r"|open|launch|view|display|show|start|run)\b",
            normalized(text),
        )
    )


def name_tokens(text: str) -> set[str]:
    # Match human names without treating punctuation/extensions as authority.
    value = re.sub(r"\.(?:pdf|docx|xlsx|txt|png|jpg|jpeg)$", "", normalized(text))
    value = re.sub(r"\b(?:yi|yu|ni|nu|olan|olani|dosyasi|dosyasini|klasoru|klasorunu)\b", "", value)
    return set(re.findall(r"[a-z0-9]+", value))


class FileSession:
    def __init__(self, core: CoreToolClient, clock: Callable[[], float] = time.monotonic):
        self._core = core
        self._clock = clock
        self.clear()

    def clear(self) -> None:
        self._entries: tuple[dict, ...] = ()
        self._expires = 0.0
        self._pending = IntentName.OPEN_FILE
        self._page: tuple[str, dict] | None = None
        self._page_info: dict = {}
        self._scope: dict | None = None
        self._scope_expires = 0.0
        self._application: str | None = None
        self._confirmation: dict | None = None

    def _clear_selection(self) -> None:
        self._entries = ()
        self._expires = 0.0
        self._page = None
        self._page_info = {}
        self._application = None
        self._confirmation = None

    def _set_scope(self, entry: dict) -> None:
        self._scope = entry
        self._scope_expires = self._clock() + 120

    def _call(self, tool: str, arguments: dict) -> dict:
        value = self._core.execute_tool(tool, arguments).data
        if not isinstance(value, dict):
            raise ModelOutputInvalid("invalid Core file result")
        return value

    def model_candidates(self) -> tuple[FileCandidate, ...]:
        if self._clock() >= self._expires:
            self._clear_selection()
        candidates = []
        budget = 1200
        for number, entry in enumerate(self._entries, 1):
            name = entry["name"]
            if len(name) > 256 or len(name) > budget:
                continue
            candidates.append(FileCandidate(name, entry["kind"], number))
            budget -= len(name)
        return tuple(candidates)

    def accepts_number(self, number: int) -> bool:
        return (
            type(number) is int
            and self._clock() < self._expires
            and 1 <= number <= len(self._entries)
        )

    def select_displayed(self, result: IntentResult) -> BrainResponse:
        number = result.arguments["number"]
        if not self.accepts_number(number):
            return self._reply(
                "Bu numara için geçerli bir sonuç listesi yok. "
                "Dosyaları yeniden bulalım veya listedeki geçerli numarayı seç."
            )
        entry = self._entries[number - 1]
        action = result.arguments["action"]
        if action not in {"open", "list", "parent"}:
            raise ModelOutputInvalid("invalid displayed file operation")
        application = str(result.arguments["application"]) or None
        if action == "open":
            application, error = self._file_application(entry, application)
            if error:
                # No Core call or effect has occurred. Preserve identity and original TTL
                # so a later valid request can still select the same displayed item.
                return error
        self._clear_selection()  # Consume the exact current-page binding before any IPC.
        try:
            if action == "parent":
                return self._open_parent(entry)
            if action == "list":
                if entry["kind"] != "directory":
                    return self._reply("İçini listelemek için bir klasör seç; seçilen sonuç dosya.")
                return self._list(entry)
            return self._open_with(entry, application)
        except CoreToolError as error:
            return self._failure(error)

    @staticmethod
    def is_relative(text: str) -> bool:
        return bool(
            re.search(r"\b(?:orada|oradaki|onun icinde|bu klasorde|o klasorde)\b", normalized(text))
        )

    def handle(self, text: str, *, preserve_unmatched: bool = False) -> BrainResponse | None:
        if self._clock() >= self._scope_expires:
            self._scope = None
        if self._clock() >= self._expires:
            self._clear_selection()
        value = normalized(text)
        relative = self.is_relative(text)
        if relative and len(self._entries) == 1 and self._entries[0]["kind"] == "directory":
            self._set_scope(self._entries[0])
        elif relative and any(e["kind"] == "directory" for e in self._entries):
            self._pending = IntentName.LIST_FOLDER
            return self._reply(
                "Hangi klasörün içinde arayayım? Listedeki klasörün numarasını veya adını seç."
            )
        if relative and not self._scope:
            return self._reply(
                "Hangi klasörün içinde arayayım? Önce klasörü adıyla bulalım veya açalım."
            )
        if (self._entries or self._scope) and (
            negative_open(text) or value in {"iptal", "bosver", "cancel"}
        ):
            self.clear()
            return self._reply("Bekleyen dosya işlemi iptal edildi.")
        if self._confirmation and value in {"evet", "aynen", "tamam", "yes"}:
            entry, application = self._confirmation, self._application
            self._clear_selection()
            try:
                return self._open_with(entry, application)
            except CoreToolError as error:
                return self._failure(error)
        if self._confirmation and value in {"hayir", "no"}:
            self._confirmation = None
            self._application = None
            return self._reply(
                "Uygulamayla açma isteği iptal edildi. Dosya listesi hâlâ seçilebilir."
            )
        self._confirmation = None  # A changed request cannot confirm an older target later.
        if not self._entries:
            return None
        if (
            value in {"devamini goster", "sonraki sayfa", "diger sonuclar", "next page"}
            and self._page
        ):
            tool, arguments = self._page
            arguments = {**arguments, "offset": arguments.get("offset", 0) + 20}
            pending = self._pending
            self._clear_selection()
            try:
                data = self._call(tool, arguments)
                return self._observe(data, pending, (tool, arguments))
            except CoreToolError as error:
                return self._failure(error)
        if relative:
            return None  # The validated model query is scoped by execute below.
        app_match = re.fullmatch(
            r"(?:(.+?)\s+)?(google chrome|chrome|google|microsoft edge|edge|google docs)"
            r"\s+ile\s+(?:ac|acar misin)",
            value,
        )
        application = self._application
        if app_match:
            value, requested = app_match.groups()
            value = value or "onu"
            if requested == "google docs":
                self._application = None
                self._confirmation = None
                return self._reply(
                    "Google Docs'a dosya yükleme henüz desteklenmiyor. "
                    "Listeden bir dosya seçerek yerel uygulamayla açabilirsin."
                )
            application = (
                "Google Chrome"
                if requested in {"google", "chrome", "google chrome"}
                else "Microsoft Edge"
            )
        parent = re.fullmatch(r"(.+?) (?:bulundugu klasoru ac|klasorunu ac)", value)
        listing = re.fullmatch(
            r"(.+?) (?:icini goster|icerigini listele|alt klasorlerini goster)", value
        )
        choice = (
            parent[1]
            if parent
            else listing[1]
            if listing
            else re.sub(r"\s+(?:ac|acar misin)$", "", value)
        )
        ordinals = {
            "ilk": 0,
            "ilki": 0,
            "ilkini": 0,
            "ilkinin": 0,
            "birinci": 0,
            "birincisi": 0,
            "ikinci": 1,
            "ikincisi": 1,
            "ikincisini": 1,
            "ikincisinin": 1,
            "ucuncu": 2,
            "ucuncusu": 2,
            "sonuncu": -1,
        }
        index = ordinals.get(choice)
        if choice in {"onu", "bunu", "dosyayi", "o dosyayi"}:
            if len(self._entries) == 1:
                index = 0
            else:
                self._application = application
                return self._reply(
                    "Hangi dosyayı açayım? Listedeki numarayı veya dosya adını söyle."
                )
        if choice.isdigit():
            index = int(choice) - 1
            if index < 0:
                return self._reply("Listedeki geçerli bir numarayı seç.")
        if index is not None:
            if not -len(self._entries) <= index < len(self._entries):
                return self._reply("Bu numarada sonuç yok; listedeki numaralardan birini seç.")
            entry = self._entries[index]
        else:
            matches = [e for e in self._entries if normalized(e["name"]) == choice]
            if not matches and (
                app_match or parent or listing or re.search(r"\b(?:ac|acar misin|olani)$", value)
            ):
                tokens = name_tokens(choice)
                matches = [e for e in self._entries if tokens and tokens <= name_tokens(e["name"])]
            if len(matches) > 1:
                self._application = application
                return self._observe(
                    {"entries": matches, "total": len(matches)},
                    IntentName.OPEN_FILE,
                    executed=False,
                )
            if len(matches) != 1:
                if value in {"evet", "aynen", "tamam"}:
                    return self._reply(
                        "Hangi dosyayı açayım? Listedeki numarayı veya dosya adını söyle."
                    )
                if not preserve_unmatched:
                    self._clear_selection()
                    self._scope = None
                return None
            entry = matches[0]
        if app_match and app_match[2] == "google":
            self._application = application
            self._confirmation = entry
            return self._reply(
                f"{entry['name']} dosyasını Google Chrome ile yerel olarak açmamı mı istiyorsun? "
                "Evet diyebilirsin. Google Docs'a yükleme desteklenmiyor."
            )
        pending = self._pending
        self._clear_selection()  # Consume before IPC; never retain a failed executable selection.
        try:
            if parent:
                return self._open_parent(entry)
            if listing or pending is IntentName.LIST_FOLDER:
                return self._list(entry)
            return self._open_with(entry, application) if application else self._open(entry)
        except CoreToolError as error:
            return self._failure(error)

    def execute(self, result: IntentResult, text: str) -> BrainResponse:
        if result.intent is IntentName.SELECT_FILE:
            if negative_open(text):
                self.clear()
                return self._reply("Açma isteği iptal edildi; dosya veya klasör açılmadı.")
            return self.select_displayed(result)
        scope = self._scope if self._clock() < self._scope_expires else None
        relative = self.is_relative(text)
        available = self._entries if self._clock() < self._expires else ()
        application = str(result.arguments.get("application", "")) or None
        if application:
            aliases = {
                "chrome": "Google Chrome",
                "google chrome": "Google Chrome",
                "edge": "Microsoft Edge",
                "microsoft edge": "Microsoft Edge",
            }
            application = aliases.get(normalized(application), application)
        query = str(result.arguments.get("query", ""))
        matches = [e for e in available if normalized(e["name"]) == normalized(query)]
        if not matches and query:
            tokens = name_tokens(query)
            matches = [e for e in available if tokens and tokens <= name_tokens(e["name"])]
        if result.intent is IntentName.OPEN_FILE:
            matches = [e for e in matches if e["kind"] == "file"]
        elif result.intent in {IntentName.OPEN_DIRECTORY, IntentName.LIST_FOLDER}:
            matches = [e for e in matches if e["kind"] == "directory"]
        if not relative:
            self._scope = None
        if result.intent in {IntentName.OPEN_FILE, IntentName.OPEN_DIRECTORY} and negative_open(
            text
        ):
            self.clear()
            return self._reply("Açma isteği iptal edildi; dosya veya klasör açılmadı.")
        try:
            if matches and result.intent in {
                IntentName.OPEN_FILE,
                IntentName.OPEN_DIRECTORY,
                IntentName.LIST_FOLDER,
            }:
                self._clear_selection()
                if len(matches) > 1:
                    self._application = application
                    return self._observe(
                        {"entries": matches, "total": len(matches)}, result.intent, executed=False
                    )
                return (
                    self._list(matches[0])
                    if result.intent is IntentName.LIST_FOLDER
                    else self._open_with(matches[0], application)
                )
            self._clear_selection()
            if result.intent in {IntentName.FILE_CATALOG_STATUS, IntentName.REFRESH_FILE_CATALOG}:
                self.clear()
                data = self._call("file_catalog_status", {})
                if result.intent is IntentName.REFRESH_FILE_CATALOG or not data.get("indexed"):
                    data = self._call("refresh_file_catalog", {})
                self._validate_status(data)
                roots = ", ".join(r["name"] for r in data["roots"]) or "yapılandırılmış klasör yok"
                message = (
                    f"Tarama kapsamı: {roots}. Katalogda {data['files']} dosya "
                    f"ve {data['directories']} klasör var. Dosya içerikleri okunmadı."
                )
                message += (
                    " Tarama kısmi; tüm dosyaları kapsamayabilir." if data.get("partial") else ""
                )
                return BrainResponse(result.intent, result.confidence, "files", True, message, data)
            kind = (
                "file"
                if result.intent is IntentName.OPEN_FILE
                else "directory"
                if result.intent in {IntentName.OPEN_DIRECTORY, IntentName.LIST_FOLDER}
                else None
            )
            arguments = {
                **{k: v for k, v in result.arguments.items() if k != "application"},
                "kind": result.arguments.get("kind", kind),
                "limit": 20,
            }
            if arguments["kind"] == "any":
                arguments["kind"] = None
            if arguments.get("extension") == "":
                arguments.pop("extension")
            if relative and scope:
                arguments["folder_id"] = scope["entry_id"]
            data = self._call("search_files", arguments)
            entries = self._validate_entries(data)
            if not entries:
                suffix = " Tarama kısmi." if data.get("partial") else ""
                return self._reply(
                    "Taranan klasörlerde eşleşme bulunamadı. "
                    "Yeni dosyalar için dosya kataloğunu yenileyebilirsin." + suffix
                )
            if result.intent is IntentName.SEARCH_FILES or data["total"] > 1:
                self._application = application
                return self._observe(data, result.intent, ("search_files", arguments))
            if result.intent is IntentName.LIST_FOLDER:
                return self._list(entries[0])
            return self._open_with(entries[0], application)
        except CoreToolError as error:
            return self._failure(error)

    def _list(self, entry: dict) -> BrainResponse:
        arguments = {"entry_id": entry["entry_id"], "limit": 20}
        data = self._call("list_directory", arguments)
        self._set_scope(entry)
        return self._observe(data, IntentName.SEARCH_FILES, ("list_directory", arguments))

    def _open_parent(self, entry: dict) -> BrainResponse:
        data = self._call("open_containing_folder", {"entry_id": entry["entry_id"]})
        if (
            data.get("opened") is not True
            or not isinstance(data.get("entry"), dict)
            or not isinstance(data["entry"].get("name"), str)
        ):
            raise ModelOutputInvalid("Core did not confirm containing-folder opening")
        return self._reply(f"{data['entry']['name']} klasörü açıldı.", True)

    def _file_application(
        self, entry: dict, application: str | None
    ) -> tuple[str | None, BrainResponse | None]:
        """Validate an override without consuming bindings or calling Core."""
        if not application:
            return None, None
        application = {
            "chrome": "Google Chrome",
            "google chrome": "Google Chrome",
            "edge": "Microsoft Edge",
            "microsoft edge": "Microsoft Edge",
        }.get(normalized(application), application)
        if application not in {"Google Chrome", "Microsoft Edge"}:
            return application, self._reply(
                "Bu uygulamayla dosya açma henüz desteklenmiyor. "
                "Uygulama belirtmeden dosyayı varsayılan uygulamayla açabilirsin."
            )
        if entry["kind"] != "file":
            return application, self._reply("Uygulamayla açmak için bir dosya seç.")
        return application, None

    def _open_with(self, entry: dict, application: str | None) -> BrainResponse:
        application, error = self._file_application(entry, application)
        if error:
            return error
        if not application:
            return self._open(entry)
        resolved = self._call("resolve_app", {"query": application})
        app = resolved.get("app")
        if (
            resolved.get("resolved") is not True
            or not isinstance(app, dict)
            or not isinstance(app.get("app_id"), str)
        ):
            raise ModelOutputInvalid("invalid resolved file application")
        data = self._call(
            "open_file_with_app", {"entry_id": entry["entry_id"], "app_id": app["app_id"]}
        )
        if data.get("opened") is not True:
            raise ModelOutputInvalid("Core did not confirm application file opening")
        return self._reply(f"{entry['name']} {application} ile açıldı.", True)

    def _open(self, entry: dict) -> BrainResponse:
        tool = "open_directory" if entry["kind"] == "directory" else "open_file"
        data = self._call(tool, {"entry_id": entry["entry_id"]})
        if data.get("opened") is not True:
            raise ModelOutputInvalid("Core did not confirm file opening")
        if entry["kind"] == "directory":
            self._set_scope(entry)
        return BrainResponse(
            IntentName.OPEN_DIRECTORY if tool == "open_directory" else IntentName.OPEN_FILE,
            1,
            "files",
            True,
            f"{entry['name']} açıldı.",
        )

    @staticmethod
    def _validate_status(data: dict) -> None:
        if (
            not isinstance(data.get("roots"), list)
            or len(data["roots"]) > 16
            or any(
                not isinstance(root, dict) or not isinstance(root.get("name"), str)
                for root in data["roots"]
            )
            or any(
                type(data.get(key)) is not int or data[key] < 0 for key in ("files", "directories")
            )
        ):
            raise ModelOutputInvalid("invalid Core file catalog status")

    @staticmethod
    def _validate_entries(data: dict) -> tuple[dict, ...]:
        entries = data.get("entries")
        if (
            not isinstance(entries, list)
            or len(entries) > 20
            or type(data.get("total")) is not int
            or data["total"] < len(entries)
        ):
            raise ModelOutputInvalid("invalid Core file list")
        for e in entries:
            if (
                not isinstance(e, dict)
                or e.get("kind") not in {"file", "directory"}
                or any(
                    not isinstance(e.get(k), str) or not e[k]
                    for k in ("entry_id", "name", "location")
                )
            ):
                raise ModelOutputInvalid("invalid Core file entry")
        if len({entry["entry_id"] for entry in entries}) != len(entries):
            raise ModelOutputInvalid("duplicate Core file catalog IDs")
        return tuple(entries)

    def _observe(
        self,
        data: dict,
        pending: IntentName,
        page: tuple[str, dict] | None = None,
        *,
        executed: bool = True,
    ) -> BrainResponse:
        entries = self._validate_entries(data)
        self._entries = entries
        self._page_info = {
            "total": data["total"],
            "offset": data.get("offset", 0),
            "partial": bool(data.get("partial")),
        }
        self._expires = self._clock() + 120
        self._pending = pending
        self._page = page if data.get("offset", 0) + len(entries) < data["total"] else None
        lines = [
            f"{i}. {e['name']} ({'klasör' if e['kind'] == 'directory' else 'dosya'}) "
            f"— {e['location']}"
            + (
                f" — {e['size_bytes']} bayt"
                if e.get("kind") == "file" and "size_bytes" in e
                else ""
            )
            for i, e in enumerate(entries, 1)
        ]
        start = data.get("offset", 0) + 1
        message = (
            f"{data['total']} sonuç; {start}–{start + len(entries) - 1} arası gösteriliyor.\n"
            + "\n".join(lines)
            if entries
            else "Bu klasörde/sonuç sayfasında kayıt yok."
        )
        message += (
            "\nTarama kısmi; kapsam dışında veya taranmamış dosyalar olabilir."
            if data.get("partial")
            else ""
        )
        if entries:
            message += (
                "\nNumara/ad seçebilir, ‘ikincisini aç’ veya "
                "‘ikincisinin bulunduğu klasörü aç’ diyebilirsin."
            )
        if self._scope:
            message += f"\nAktif arama klasörü: {self._scope['name']}."
        if self._application:
            message += f"\nSeçilen dosya {self._application} ile yerel olarak açılacak."
        if self._page:
            message += "\nDiğer sonuçlar için ‘sonraki sayfa’ diyebilirsin."
        return BrainResponse(
            IntentName.CLARIFY, 1, "files", executed, message, {"file_entries": True}
        )

    @staticmethod
    def _reply(message: str, executed: bool = False) -> BrainResponse:
        return BrainResponse(IntentName.CLARIFY, 1, "files", executed, message)

    @staticmethod
    def _failure(error: CoreToolError) -> BrainResponse:
        from dataclasses import replace

        return replace(FileSession._failure_message(error), data={"error": error.code})

    @staticmethod
    def _failure_message(error: CoreToolError) -> BrainResponse:
        if error.code in {"application_not_found", "application_ambiguous"}:
            return FileSession._reply(
                "Dosya açılmadı; seçilen uygulama katalogda bulunamadı "
                "veya birden fazla uygulama eşleşti."
            )
        if error.code == "unknown_tool":
            return FileSession._reply(
                "Çalışan Core dosya araçlarını desteklemiyor; yeni Core sürümünü başlat."
            )
        if error.code == "policy_denied":
            return FileSession._reply(
                "Bu hedefe erişim veya bu dosya türünü açma Core tarafından reddedildi."
            )
        if error.code == "permission_denied":
            return FileSession._reply("Bu dosya işlemine erişim izni verilmedi.")
        if error.code == "execution_failed":
            return FileSession._reply(
                "İşletim sistemi dosya işlemini tamamlayamadı. "
                "Dosyaya erişimi ve dosyanın ilişkilendirildiği uygulamayı kontrol et."
            )
        return FileSession._reply(
            "Dosya işlemi tamamlanamadı. Katalog değişmiş olabilir; yenileyip yeniden ara."
        )
