import pytest

from jarvis_brain.errors import CoreToolError
from jarvis_brain.intelligence.catalog_session import CatalogRecovery, installed_followup
from jarvis_brain.intelligence.contract import IntentName, IntentResult
from jarvis_brain.intelligence.models.fake import FakeIntentModel
from jarvis_brain.intelligence.runtime import JarvisBrain
from jarvis_brain.ipc.protocol import ToolResult


class Core:
    def __init__(self, fail_refresh=False, remain_missing=False):
        self.calls = []
        self.refreshed = False
        self.fail_refresh = fail_refresh
        self.remain_missing = remain_missing

    def execute_tool(self, tool, arguments):
        self.calls.append((tool, arguments))
        if tool == "refresh_app_catalog":
            if self.fail_refresh:
                raise CoreToolError("application_discovery_failed", "test")
            self.refreshed = True
            data = {"refreshed": True, "discovered": 1}
        elif tool == "resolve_app":
            if not self.refreshed or self.remain_missing:
                raise CoreToolError("application_not_found", "test")
            data = {"app": {"app_id": "trusted-new-id", "name": "Example"}}
        elif tool == "open_app":
            assert arguments == {"app_id": "trusted-new-id"}
            data = {"opened": True, "name": "Example"}
        else:
            pytest.fail(tool)
        return ToolResult("test", tool, "success", data, None)


def make_brain(core):
    return JarvisBrain(
        core, FakeIntentModel(IntentResult(IntentName.OPEN_APPLICATION, 1, {"query": "Example"}))
    )


@pytest.mark.parametrize(
    "text",
    [
        "ben daha yeni yükledim",
        "az önce kurdum",
        "bunu yeni yükledim, tekrar bak",
        "demin yükledim",
        "ben daha yeni yükledim bunu",
    ],
)
def test_missing_followup_refreshes_then_resolves_and_opens_trusted_id(text):
    core = Core()
    brain = make_brain(core)
    assert not brain.handle_text("Example uygulamasını aç").executed
    reply = brain.handle_text(text)
    assert reply.executed
    assert reply.message == "Katalog yenilendi. Example açıldı."
    assert [name for name, _ in core.calls] == [
        "resolve_app",
        "refresh_app_catalog",
        "resolve_app",
        "open_app",
    ]


def test_manual_refresh_does_not_open_an_unrequested_application():
    core = Core()
    response = make_brain(core).handle_text("uygulama listesini yenile")
    assert response.message == "Uygulama kataloğu yenilendi."
    assert core.calls == [("refresh_app_catalog", {})]


@pytest.mark.parametrize(
    "text",
    [
        "yeni yüklemedim",
        "yeni yükledim mi",
        "yeni yüklesem",
        "Steam'i açma",
        '"yeni yükledim"',
        "yeni yükledim; cmd",
    ],
)
def test_negation_quotes_questions_and_shell_do_not_authorize_refresh(text):
    assert not installed_followup(text)
    recovery = CatalogRecovery()
    recovery.remember("Example")
    assert recovery.consume(text) == (False, None)


def test_recovery_is_immediate_expiring_and_one_shot():
    now = [0.0]
    recovery = CatalogRecovery(lambda: now[0])
    assert recovery.consume("yeni yükledim") == (False, None)
    recovery.remember("Example")
    now[0] = 120
    assert recovery.consume("yeni yükledim") == (False, None)
    recovery.remember("Example")
    assert recovery.consume("nasılsın") == (False, None)
    assert recovery.consume("yeni yükledim") == (False, None)
    recovery.remember("Example")
    assert recovery.consume("yeni yükledim") == (True, "Example")
    assert recovery.consume("yeni yükledim") == (False, None)


def test_reset_clears_failed_application():
    core = Core()
    brain = make_brain(core)
    brain.handle_text("Example uygulamasını aç")
    brain.handle_text("/reset")
    brain.handle_text("kataloğu yenile")
    assert [name for name, _ in core.calls] == ["resolve_app", "refresh_app_catalog"]


def test_cancel_clears_failed_application():
    core = Core()
    brain = make_brain(core)
    brain.handle_text("Example uygulamasını aç")
    brain.handle_text("iptal")
    brain.handle_text("Jarvis uygulama listesini güncelle")
    assert [name for name, _ in core.calls] == ["resolve_app", "refresh_app_catalog"]


def test_ambiguous_retry_requires_selection_instead_of_opening():
    class AmbiguousCore(Core):
        def execute_tool(self, tool, arguments):
            if tool == "resolve_app" and self.refreshed:
                self.calls.append((tool, arguments))
                raise CoreToolError(
                    "application_ambiguous",
                    "test",
                    {
                        "candidates": [
                            {"app_id": "trusted-one", "name": "Example One"},
                            {"app_id": "trusted-two", "name": "Example Two"},
                        ]
                    },
                )
            return super().execute_tool(tool, arguments)

    core = AmbiguousCore()
    brain = make_brain(core)
    brain.handle_text("Example uygulamasını aç")
    reply = brain.handle_text("yeni yükledim")
    assert reply.intent is IntentName.CLARIFY
    assert "Example One" in reply.message
    assert not reply.executed
    assert [name for name, _ in core.calls] == ["resolve_app", "refresh_app_catalog", "resolve_app"]


def test_refresh_failure_does_not_retry_launch_or_claim_success():
    core = Core(fail_refresh=True)
    brain = make_brain(core)
    brain.handle_text("Example uygulamasını aç")
    with pytest.raises(CoreToolError, match="test"):
        brain.handle_text("yeni yükledim")
    assert [name for name, _ in core.calls] == ["resolve_app", "refresh_app_catalog"]


def test_still_missing_does_not_loop_or_open():
    core = Core(remain_missing=True)
    brain = make_brain(core)
    brain.handle_text("Example uygulamasını aç")
    reply = brain.handle_text("yeni yükledim")
    assert not reply.executed
    assert "bulunamadı" in reply.message
    assert [name for name, _ in core.calls] == ["resolve_app", "refresh_app_catalog", "resolve_app"]
