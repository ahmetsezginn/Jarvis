"""Opt-in Qt lifecycle tests using an offscreen surface and fake Core replies."""

import importlib.util
import os
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "jarvis_desktop", ROOT / "services/desktop/main.py"
)
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


@pytest.fixture(scope="module")
def app():
    application = QGuiApplication.instance() or QGuiApplication([])
    desktop.configure_appearance(application)
    return application


def controller(app):
    value = desktop.Controller(launch_worker=False)
    calls = []
    value.core = lambda tool, args, callback: calls.append((tool, args, callback))
    sent = []
    value.send = sent.append
    return value, calls, sent


def test_frozen_desktop_uses_fixed_bundled_worker_instead_of_a_python_install(
    app, monkeypatch, tmp_path
):
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Jarvis.exe"))
    value = desktop.Controller(launch_worker=False)
    assert value.worker.program() == str(tmp_path / "JarvisWorker.exe")
    assert value.worker.arguments() == ["--brain-worker"]


def barge_controller(app, *, acknowledge=True):
    value, calls, sent = controller(app)
    value._automatic = True
    value.speak_text("Here is the explanation you requested.")
    assert calls[-1][:2] == ("speech_start", {"automatic": True, "barge_in": True})
    calls[-1][2]({"recording_id": "barge", "echo_cancelled": True}, None)
    assert calls[-1][0] == "speech_speak"
    if acknowledge:
        calls[-1][2]({"queued": True}, None)
    return value, calls, sent


def test_barge_arms_verified_echo_capture_before_sapi_and_retains_one_microphone(app):
    value, calls, sent = barge_controller(app)
    value.pollVoice()
    calls[-1][2]({"phase": "waiting", "speaking": True, "level": 0.002}, None)
    assert value.voicePhase == "speaking" and value.recording and not sent
    value.resume_automatic()
    assert sum(tool == "speech_start" for tool, _, _ in calls) == 1
    value.pollVoice()
    calls[-1][2]({"phase": "waiting", "speaking": False}, None)
    assert value.voicePhase == "waiting" and value.recording and not sent
    value.cancelVoice()


@pytest.mark.parametrize("late_ack", [False, True])
def test_barge_interrupt_rejects_old_ack_and_submits_only_complete_new_turn(
    app, late_ack
):
    value, calls, sent = barge_controller(app, acknowledge=not late_ack)
    speech = next(call for call in calls if call[0] == "speech_speak")
    value.pollVoice()
    calls[-1][2](
        {"phase": "listening", "interrupted": True, "speaking": False, "level": 0.6},
        None,
    )
    speech[2]({"queued": True}, None)
    assert value.voicePhase == "listening" and not value._speaking and not sent
    value.pollVoice()
    calls[-1][2]({"phase": "complete", "interrupted": True}, None)
    assert calls[-1][0] == "speech_finish"
    assert any(call[0] == "speech_stop" for call in calls)
    calls[-1][2](
        {"text": "Actually, show tomorrow's tasks instead.", "language": "en"}, None
    )
    assert sent == ["Actually, show tomorrow's tasks instead."]
    assert not value.recording and not value._barge_capture


def test_barge_user_onset_before_output_queue_never_resurrects_old_explanation(app):
    value, calls, sent = barge_controller(app, acknowledge=False)
    calls[-1][2]({"queued": False, "interrupted": True}, None)
    assert value.voicePhase == "listening" and not value._speaking and value.recording
    assert not sent
    value.cancelVoice()


@pytest.mark.parametrize("action", ["end", "shutdown", "stop"])
def test_barge_cancel_during_aec_open_discards_late_capture_without_speaking(
    app, action
):
    value, calls, sent = controller(app)
    value._automatic = True
    value.speak_text("An obsolete explanation")
    start = calls[-1]
    if action == "end":
        value.setAutomatic(False, -1)
    elif action == "shutdown":
        value.shutdown()
    else:
        value.stopSpeaking()
    start[2]({"recording_id": "late-barge", "echo_cancelled": True}, None)
    assert calls[-1][:2] == ("speech_cancel", {"recording_id": "late-barge"})
    calls[-1][2]({"cancelled": True}, None)
    assert not any(tool == "speech_speak" for tool, _, _ in calls)
    assert not value._barge_capture and not value.recording and not sent


def test_barge_aec_open_failure_is_visible_and_uses_existing_turn_by_turn_voice(app):
    value, calls, sent = controller(app)
    messages = []
    value.message.connect(lambda role, text: messages.append((role, text)))
    value._automatic = True
    value.speak_text("A response")
    calls[-1][2](None, "AEC endpoint unavailable")
    assert calls[-1][0] == "speech_speak"
    assert not value.recording and not value._barge_available
    assert any(
        role == "system" and "Voice interruption unavailable" in text
        for role, text in messages
    )
    calls[-1][2]({"queued": True}, None)
    value.pollVoice()
    calls[-1][2]({"speaking": False}, None)
    value.resume_automatic()
    assert calls[-1][:2] == ("speech_start", {"automatic": True})
    assert not sent
    value.cancelVoice()


def test_barge_missing_native_echo_confirmation_never_queues_voice(app):
    value, calls, sent = controller(app)
    value._automatic = True
    value.speak_text("A response")
    calls[-1][2]({"recording_id": "unprotected"}, None)
    assert not any(tool == "speech_speak" for tool, _, _ in calls)
    assert any(tool == "speech_cancel" for tool, _, _ in calls)
    assert not value.automatic and not sent


@pytest.mark.parametrize("reason", ["device", "fatal", "end"])
def test_barge_teardown_stops_output_and_never_sends_partial_audio(app, reason):
    value, calls, sent = barge_controller(app)
    if reason == "end":
        value.setAutomatic(False, -1)
    else:
        value.pollVoice()
        status = {"phase": "error", "error": "lost capture"}
        if reason == "device":
            status["input_changed"] = True
        calls[-1][2](status, None)
    assert any(tool == "speech_stop" for tool, _, _ in calls)
    assert calls[-1][0] == "speech_cancel"
    assert not any(tool == "speech_finish" for tool, _, _ in calls)
    assert not sent
    if reason == "device":
        value.setAutomatic(False, -1)


def test_barge_cancel_during_transcription_discards_late_new_command(app):
    value, calls, sent = barge_controller(app)
    value.finishVoice()
    finish = calls[-1]
    value.setAutomatic(False, -1)
    finish[2]({"text": "A cancelled instruction"}, None)
    assert not sent and not value.automatic


def test_barge_explicit_audio_devices_share_one_registered_reference_and_change_cancels(
    app,
):
    value, calls, _ = controller(app)
    value._automatic, value._device, value._output_device = True, 2, 1
    value.speak_text("An explanation")
    assert calls[-1][1] == {
        "automatic": True,
        "barge_in": True,
        "device_index": 2,
        "output_device_index": 1,
    }
    calls[-1][2]({"recording_id": "selected", "echo_cancelled": True}, None)
    assert calls[-1][1]["output_device_index"] == 1
    value.setOutputDevice(0)
    assert calls[-1][:2] == ("speech_cancel", {"recording_id": "selected"})
    assert not value.automatic


def test_startup_welcome_remains_microphone_closed_until_actual_output_completion(app):
    value, calls, _, _ = startup_controller(app)
    value._startup_devices_ready = True
    value.announce_startup()
    assert calls[-1][0] == "speech_speak"
    assert not any(tool == "speech_start" for tool, _, _ in calls)
    calls[-1][2]({"queued": True}, None)
    value.pollVoice()
    calls[-1][2]({"speaking": False}, None)
    assert not value._startup_greeting
    value.resume_automatic()
    assert calls[-1][:2] == ("speech_start", {"automatic": True})
    value.cancelVoice()


@pytest.mark.skipif(
    os.environ.get("JARVIS_RUN_BARGE_LIVE") != "1",
    reason="real QML/Core/default microphone/SAPI; quiet room, pause wake service, no desktop",
)
def test_real_qml_reply_arms_aec_and_waits_without_responding_to_itself(app):
    value = desktop.Controller(launch_worker=False)
    value._automatic = True
    value._reply_language = "tr"
    sent, messages, phases = [], [], []
    value.send = sent.append  # Test audio can never dispatch a machine action to Brain.
    value.message.connect(lambda role, text: messages.append((role, text)))
    value.changed.connect(lambda: phases.append(value.voicePhase))
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("jarvis", value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "services/desktop/Main.qml")))
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    try:
        worker_event(
            value,
            {
                "event": "response",
                "text": "Bu bir konuşma denemesi. Jarvis konuşurken sizi de dinleyebilir. Bu denemede yalnızca kendi sesinin yankısı kontrol ediliyor; hiçbir görev çalıştırılmayacak.",
            },
        )
        began = time.monotonic()
        while time.monotonic() - began < 35 and not (
            "speaking" in phases and value.voicePhase == "waiting"
        ):
            QTest.qWait(50)
        assert value._barge_available and value._barge_capture
        assert value.recording and "speaking" in phases and "waiting" in phases
        assert "listening" not in phases and not sent
        assert not any(role == "system" for role, _ in messages), messages
        print(
            f"QML real reply: speaking/waiting, echo capture active, no self-trigger or agent dispatch; {value.inputNote}"
        )
    finally:
        value.shutdown()
        until = time.monotonic() + 6
        while value._calls and time.monotonic() < until:
            QTest.qWait(50)
        window.close()


def startup_controller(app, microphone_name="BSX"):
    value = desktop.Controller(
        launch_worker=False, startup_voice=True, microphone_name=microphone_name
    )
    calls, sent, messages = [], [], []
    value.core = lambda tool, args, callback: calls.append((tool, args, callback))
    value.send = sent.append
    value.message.connect(lambda role, text: messages.append((role, text)))
    return value, calls, sent, messages


def worker_event(value, event):
    import json
    from types import SimpleNamespace

    worker = value.worker
    value.worker = SimpleNamespace(
        readAllStandardOutput=lambda: (json.dumps(event) + "\n").encode()
    )
    try:
        value.read_worker()
    finally:
        value.worker = worker


@pytest.mark.skipif(
    os.environ.get("JARVIS_RUN_DESKTOP_PRELOAD_LIVE") != "1",
    reason="explicit real local 9B startup and first reply; pause wake service first",
)
def test_real_model_preloads_without_a_user_message_and_first_reply_uses_it(app):
    import json

    started = time.monotonic()
    value = desktop.Controller()
    value.voice_enabled = False
    messages = []
    value.message.connect(lambda role, text: messages.append((role, text)))
    ticks = 0
    try:
        deadline = started + 60
        while (value.modelLoading or value.busy) and time.monotonic() < deadline:
            QTest.qWait(25)
            ticks += 1
            assert value.status not in {"Needs attention", "Offline"}, messages
        prepared = time.monotonic()
        assert not value.modelLoading and value._model_load_ms is not None
        assert not messages and ticks > 0  # No user message was required to load.
        value.send(
            "Say hello in one short sentence. Do not inspect or change my computer."
        )
        assert value.status == "Thinking"
        deadline = time.monotonic() + 90
        while value.busy and time.monotonic() < deadline:
            QTest.qWait(25)
        assert value.status == "Ready" and any(
            role == "assistant" for role, _ in messages
        )
        result = {
            "model_load_ms": value._model_load_ms,
            "desktop_to_prepared_ms": (prepared - started) * 1000,
            "first_reply_after_prepared_ms": (time.monotonic() - prepared) * 1000,
            "qt_event_ticks_during_preload": ticks,
        }
        (ROOT / "target/desktop-preload-live.json").write_text(
            json.dumps(result, indent=2)
        )
        print("Real startup preload:", json.dumps(result), flush=True)
    finally:
        value.shutdown()
        deadline = time.monotonic() + 10
        while value._calls and time.monotonic() < deadline:
            QTest.qWait(25)
        assert value.worker.state() == desktop.QProcess.NotRunning


def activating_controller(app):
    value, calls, sent, messages = startup_controller(app, microphone_name="")
    now = [100.0]
    value._startup_clock = lambda: now[0]
    worker_event(value, {"event": "ready", "model_loading": True})
    calls[-1][2]({"devices": [{"index": 0, "name": "Default"}]}, None)
    return value, calls, sent, messages, now


def test_activation_countdown_never_opens_microphone_or_claims_readiness_on_timeout(
    app,
):
    value, calls, sent, messages, now = activating_controller(app)
    assert "8 saniye" in value.startupNote and "Tahmini 8 saniye" in messages[0][1]
    calls[-1][2]({"queued": True}, None)
    value.pollVoice()
    calls[-1][2]({"speaking": False, "output_phase": "idle"}, None)
    for elapsed in [3.1, 8, 15]:
        now[0] = 100 + elapsed
        value.startVoice(-1)
        value.resume_automatic()
        assert not value.recording and value.modelLoading
    assert "Hazırlık devam ediyor" in value.startupNote
    assert not any(tool == "speech_start" for tool, _, _ in calls) and not sent
    assert not any(text.startswith("Sistem aktif.") for _, text in messages)
    value.startup_timer.stop()


def test_actual_readiness_replaces_stale_countdown_speech_and_waits_for_welcome(app):
    value, calls, sent, messages, _now = activating_controller(app)
    stale_speech = calls[-1]
    worker_event(value, {"event": "model_ready", "load_time_ms": 1200})
    assert not value.modelLoading and not value.startup_timer.isActive()
    assert calls[-2][0] == "speech_stop"
    assert calls[-1][:2] == (
        "speech_speak",
        {"text": "Sistem aktif. Merhaba, nasıl yardımcı olabilirim?", "language": "tr"},
    )
    stale_speech[2](
        {"queued": True}, None
    )  # Late preparation acknowledgement is obsolete.
    assert value._speech_pending and not value.recording
    calls[-1][2]({"queued": True}, None)
    value.pollVoice()
    calls[-1][2]({"speaking": True, "output_phase": "speaking"}, None)
    value.resume_automatic()
    assert not value.recording
    value.pollVoice()
    calls[-1][2]({"speaking": False, "output_phase": "idle"}, None)
    value.resume_automatic()
    assert calls[-1][:2] == ("speech_start", {"automatic": True}) and not sent
    worker_event(value, {"event": "model_ready"})
    assert len([text for _, text in messages if text.startswith("Sistem aktif.")]) == 1
    value._automatic = False
    value.poll_timer.stop()


@pytest.mark.parametrize("failure", [False, True])
def test_cancel_or_failed_activation_never_records_or_rearms_on_late_ready(
    app, failure
):
    value, calls, sent, messages, _now = activating_controller(app)
    if failure:
        worker_event(
            value, {"event": "error", "stage": "model_load", "message": "No model"}
        )
    else:
        value.setAutomatic(False, -1)
    worker_event(value, {"event": "model_ready"})
    assert not value.automatic and not sent
    assert not any(tool in {"speech_start", "speech_finish"} for tool, _, _ in calls)
    assert not any(text.startswith("Sistem aktif.") for _, text in messages)


def test_manual_hold_cannot_start_until_preload_completes(app):
    value, calls, _sent = controller(app)
    value._model_loading = True
    value.startVoice(-1)
    assert not calls and not value.recording
    worker_event(value, {"event": "model_ready"})
    value.startVoice(-1)
    assert calls[-1][:2] == ("speech_start", {})
    calls[-1][2]({"recording_id": "manual"}, None)
    value.finishVoice()
    assert (
        calls[-1][0] == "speech_finish"
    )  # Release still ends manual capture immediately.
    value.poll_timer.stop()


def test_activation_waits_for_device_discovery_even_if_model_finishes_first(app):
    value, calls, sent, messages = startup_controller(app, microphone_name="")
    worker_event(value, {"event": "ready", "model_loading": True})
    discovery = calls[-1]
    worker_event(value, {"event": "model_ready"})
    value.resume_automatic()
    assert not messages and not sent and calls[-1] == discovery
    discovery[2]({"devices": []}, None)
    assert calls[-1][0] == "speech_speak" and messages[-1][1].startswith(
        "Sistem aktif."
    )
    value._automatic = False


def test_qml_countdown_is_estimated_and_stops_at_actual_readiness(app):
    from PySide6.QtCore import QObject

    value, calls, _sent, _messages, now = activating_controller(app)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(
        lambda values: warnings.extend(str(item) for item in values)
    )
    engine.rootContext().setContextProperty("jarvis", value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "services/desktop/Main.qml")))
    window = engine.rootObjects()[0]
    status = window.findChild(QObject, "startupStatus")
    assert "Tahmini kalan: 8 saniye" in status.property("text")
    now[0] += 5
    value.changed.emit()
    assert "3 saniye" in status.property("text")
    now[0] += 10
    value.changed.emit()
    assert "Hazırlık devam ediyor" in status.property("text")
    assert not any(tool == "speech_start" for tool, _, _ in calls)
    worker_event(value, {"event": "model_ready"})
    assert "Tahmini kalan" not in status.property("text") and not warnings
    value._automatic = False
    value.poll_timer.stop()
    window.close()


def test_worker_exit_during_activation_cannot_greet_after_late_device_discovery(app):
    value, calls, sent, messages = startup_controller(app, microphone_name="")
    worker_event(value, {"event": "ready", "model_loading": True})
    discovery = calls[-1]
    value.worker_finished()
    discovery[2]({"devices": []}, None)
    worker_event(value, {"event": "model_ready"})
    assert value.status == "Offline" and not value.automatic
    assert not messages and not sent
    assert not any(tool in {"speech_speak", "speech_start"} for tool, _, _ in calls)


def test_startup_greeting_finishes_before_turkish_auto_capture_on_selected_mic(app):
    value, calls, sent, messages = startup_controller(app)
    value.resume_automatic()
    assert not calls  # Device discovery has not completed.
    value.device_status({"devices": [{"index": 2, "name": "BSX"}]}, None)
    assert value.automatic and value.recognitionLanguage == value.replyLanguage == "tr"
    assert calls[-1][:2] == (
        "speech_speak",
        {"text": "Sistem aktif. Merhaba, nasıl yardımcı olabilirim?", "language": "tr"},
    )
    value.resume_automatic()
    assert not value.recording
    calls[-1][2]({"queued": True}, None)
    value.pollVoice()
    calls[-1][2]({"speaking": True, "output_phase": "queued"}, None)
    value.resume_automatic()
    assert not value.recording
    value.pollVoice()
    calls[-1][2]({"speaking": True, "output_phase": "speaking"}, None)
    value.resume_automatic()
    assert not value.recording
    value.pollVoice()
    calls[-1][2]({"speaking": False, "output_phase": "idle"}, None)
    value.resume_automatic()
    assert calls[-1][:2] == ("speech_start", {"device_index": 2, "automatic": True})
    calls[-1][2]({"recording_id": "turn", "input": {"name": "BSX"}}, None)
    value.finishVoice()
    assert calls[-1][:2] == (
        "speech_finish",
        {"recording_id": "turn", "language": "tr"},
    )
    calls[-1][2]({"text": "Merhaba", "language": "tr"}, None)
    value.device_status({}, None)
    assert messages == [
        ("assistant", "Sistem aktif. Merhaba, nasıl yardımcı olabilirim?")
    ] and sent == ["Merhaba"]
    value._automatic = False
    value.poll_timer.stop()


@pytest.mark.parametrize("failure", ["discovery", "missing", "duplicate", "output"])
def test_startup_errors_never_silently_open_another_mic(app, failure):
    value, calls, sent, messages = startup_controller(app)
    data = {"devices": [{"index": 2, "name": "BSX"}]}
    if failure == "missing":
        data["devices"] = [{"index": 0, "name": "Other microphone"}]
    elif failure == "duplicate":
        data["devices"].append({"index": 3, "name": "BSX"})
    value.device_status(data, "Core unavailable" if failure == "discovery" else None)
    if failure == "output":
        calls[-1][2](None, "Turkish voice unavailable")
    assert value.status == "Needs attention" and not value.automatic
    assert not sent and not any(tool == "speech_start" for tool, _, _ in calls)
    assert messages[-1][0] == "system"


def test_disabling_auto_before_discovery_prevents_delayed_startup(app):
    value, calls, sent, messages = startup_controller(app)
    value.setAutomatic(False, -1)
    value.device_status({"devices": [{"index": 2, "name": "BSX"}]}, None)
    value.resume_automatic()
    assert not value.automatic and not value.recording and not sent and not messages
    assert not any(tool in {"speech_start", "speech_speak"} for tool, _, _ in calls)


def test_windows_default_startup_does_not_pin_an_enumerated_microphone(app):
    value, calls, _sent, _messages = startup_controller(app, microphone_name="")
    value.device_status({"devices": [{"index": 0, "name": "Built in"}]}, None)
    calls[-1][2]({"queued": True}, None)
    value.pollVoice()
    calls[-1][2]({"speaking": False, "output_phase": "idle"}, None)
    value.resume_automatic()
    assert value.inputDevice == -1
    assert calls[-1][:2] == ("speech_start", {"automatic": True})
    value._automatic = False
    value.poll_timer.stop()


@pytest.mark.parametrize("stop_while_switching", [False, True])
def test_default_input_change_discards_partial_turn_before_rearming(
    app, stop_while_switching
):
    value, calls, sent = controller(app)
    value.setAutomatic(True, -1)
    calls[-1][2]({"recording_id": "old-route"}, None)
    value.pollVoice()
    calls[-1][2]({"phase": "error", "input_changed": True}, None)
    assert calls[-1][:2] == ("speech_cancel", {"recording_id": "old-route"})
    teardown = calls[-1]
    assert not value.recording and value.status == "Switching microphone" and not sent
    value.resume_automatic()
    assert calls[-1] == teardown  # Must wait for the old stream to release.
    if stop_while_switching:
        value.setAutomatic(False, -1)
    teardown[2]({"cancelled": True}, None)
    value.resume_automatic()
    starts = [args for tool, args, _ in calls if tool == "speech_start"]
    assert starts == [{"automatic": True}] * (1 if stop_while_switching else 2)
    assert not any(tool == "speech_finish" for tool, _, _ in calls) and not sent
    value._automatic = False
    value.poll_timer.stop()


def test_explicit_microphone_error_does_not_switch_to_default(app):
    value, calls, sent = controller(app)
    value.setAutomatic(True, 2)
    calls[-1][2]({"recording_id": "fixed"}, None)
    value.pollVoice()
    calls[-1][2](
        {"phase": "error", "input_changed": True, "error": "Disconnected"}, None
    )
    assert not value.automatic and not sent
    assert calls[-1][:2] == ("speech_cancel", {"recording_id": "fixed"})


def test_startup_qml_shows_turkish_and_selected_device_without_binding_errors(app):
    from PySide6.QtCore import QObject

    value, _calls, _sent, _messages = startup_controller(app)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(
        lambda values: warnings.extend(str(item) for item in values)
    )
    engine.rootContext().setContextProperty("jarvis", value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "services/desktop/Main.qml")))
    value.device_status({"devices": [{"index": 2, "name": "BSX"}]}, None)
    QTest.qWait(20)
    window = engine.rootObjects()[0]
    assert (
        window.findChild(QObject, "recognitionLanguage").property("currentIndex") == 1
    )
    assert window.findChild(QObject, "replyVoice").property("currentIndex") == 1
    assert window.findChild(QObject, "inputDevice").property("currentIndex") == 1
    assert window.findChild(QObject, "autoConversation").property("checked")
    assert not warnings
    value._automatic = False
    window.close()


@pytest.mark.skipif(
    os.environ.get("JARVIS_RUN_DESKTOP_STARTUP_LIVE") != "1",
    reason="explicit real startup speech/microphone; pause wake service first",
)
def test_real_startup_worker_greeting_completes_before_selected_microphone_opens(app):
    microphone = os.environ.get("JARVIS_DESKTOP_MICROPHONE", "")
    value = desktop.Controller(startup_voice=True, microphone_name=microphone)
    messages, polls, captures, requests = [], [], [], []
    value.message.connect(lambda role, text: messages.append((role, text)))
    real_core = value.core
    value.send = requests.append  # No captured words may execute actions in this probe.

    def traced_core(tool, arguments, callback):
        if tool == "speech_start":
            assert not value.modelLoading and value._model_load_ms is not None
            assert not value.startup_timer.isActive()
            assert messages[-1] == (
                "assistant",
                "Sistem aktif. Merhaba, nasıl yardımcı olabilirim?",
            )
            assert polls and polls[-1].get("output_phase") == "idle", polls
            assert not value._speech_pending and not value._speaking

        def completed(data, error):
            if tool == "speech_poll" and not arguments and data:
                polls.append(dict(data))
            callback(data, error)
            if tool == "speech_start" and not error:
                captures.append(data)
                value.setAutomatic(False, -1)  # Immediately discard test capture.

        real_core(tool, arguments, completed)

    value.core = traced_core
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("jarvis", value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "services/desktop/Main.qml")))
    window = engine.rootObjects()[0]
    try:
        deadline = time.monotonic() + 35
        while not captures and time.monotonic() < deadline:
            QTest.qWait(25)
            assert value.status not in {"Needs attention", "Offline"}, messages
        assert captures and any(row.get("output_phase") == "speaking" for row in polls)
        if microphone:
            assert captures[0]["input"]["name"] == microphone
        else:
            assert value.inputDevice == -1
            assert any(
                row["name"] == captures[0]["input"]["name"] for row in value._devices
            )
        assert any(text.startswith("Sistem aktifleştiriliyor.") for _, text in messages)
        assert (
            sum(
                text == "Sistem aktif. Merhaba, nasıl yardımcı olabilirim?"
                for _, text in messages
            )
            == 1
        )
        assert not requests
        assert value.recognitionLanguage == value.replyLanguage == "tr"
        assert "Tolga" in value.outputNote, value.outputNote
        print(
            "Real Turkish startup:", value.outputNote, captures[0]["input"], flush=True
        )
    finally:
        value.shutdown()
        deadline = time.monotonic() + 10
        while value._calls and time.monotonic() < deadline:
            QTest.qWait(25)
        assert not value._calls
        window.close()


def lifecycle(app):
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location(
        "jarvis_lifecycle", ROOT / "services/desktop/lifecycle.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    value, calls, sent = controller(app)
    quits = []
    control = module.DesktopLifecycle(
        SimpleNamespace(quit=lambda: quits.append(True)), value, desktop.CoreCall
    )
    requests = []
    control.core = lambda tool, args, callback: requests.append((tool, args, callback))
    control.attached({"session": "fixture", "closing": False, "revision": 1}, None)
    control.timer.stop()
    return value, control, calls, sent, quits, requests


def test_native_close_event_quits_once_and_prevents_late_voice_rearm(app):
    value, control, calls, sent, quits, _requests = lifecycle(app)
    value._automatic = True
    control.apply({"closing": True, "revision": 2})
    control.apply({"closing": True, "revision": 2})
    control.apply({"closing": False, "revision": 1})
    value.resume_automatic()
    value.startVoice(-1)
    assert quits == [True] and value._closing and not value.automatic
    assert not calls and not sent


def test_failed_desktop_poll_does_not_close_application_or_start_microphone(app):
    value, control, calls, sent, quits, requests = lifecycle(app)
    control.poll()
    assert requests[-1][:2] == ("desktop_poll", {"session": "fixture"})
    requests[-1][2](None, "Core disconnected")
    assert not quits and not value._closing and not calls and not sent


def test_fast_release_waits_for_microphone_then_submits_one_final_transcript(app):
    value, calls, sent = controller(app)
    value.startVoice(-1)
    value.finishVoice()
    assert calls[0][:2] == ("speech_start", {})
    calls[0][2]({"recording_id": "fixture"}, None)
    assert calls[1][:2] == (
        "speech_finish",
        {"recording_id": "fixture", "language": "auto"},
    )
    calls[1][2]({"text": "Open the second one."}, None)
    assert sent == ["Open the second one."]
    assert not value.recording


def test_cancel_during_microphone_open_discards_late_start_and_never_submits(app):
    value, calls, sent = controller(app)
    value.startVoice(-1)
    value.cancelVoice()
    calls[0][2]({"recording_id": "late"}, None)
    assert calls[1][:2] == ("speech_cancel", {"recording_id": "late"})
    assert not sent and not value.recording


def test_cancel_during_transcription_discards_late_text(app):
    value, calls, sent = controller(app)
    value.startVoice(-1)
    calls[0][2]({"recording_id": "fixture"}, None)
    value.finishVoice()
    value.cancelVoice()
    calls[1][2]({"text": "Open Steam"}, None)
    assert not sent


def test_silence_never_turns_into_agent_request(app):
    value, calls, sent = controller(app)
    value.startVoice(-1)
    calls[0][2]({"recording_id": "fixture"}, None)
    value.finishVoice()
    calls[1][2]({"text": ""}, None)
    assert not sent and not value.busy


def test_qml_loads_and_renders_real_result_cards(app):
    value, _, _ = controller(app)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda entries: warnings.extend(str(e) for e in entries))
    engine.rootContext().setContextProperty("jarvis", value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "services/desktop/Main.qml")))
    assert engine.rootObjects(), warnings
    value._scope_note = "1 result · Downloads\nPartial catalog: files outside scanned roots may be missing."
    value.changed.emit()
    value.message.emit("user", "Could you help me find my presentation?")
    value.message.emit(
        "assistant", "I found one candidate. You can open it from the results."
    )
    value.results.emit(
        '[{"number":1,"name":"Toplantı-Sunum.txt","kind":"file","location":"Downloads / Demo"}]'
    )
    QTest.qWait(300)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    output = ROOT / "target/desktop-preview.png"
    assert window.grabWindow().save(str(output))
    assert not warnings, warnings
    window.close()


@pytest.mark.skipif(
    os.environ.get("JARVIS_RUN_DESKTOP_LIVE") != "1", reason="opt-in real local agent"
)
def test_real_qt_worker_connects_and_answers_without_blocking_interface(app):
    value = desktop.Controller()
    messages = []
    value.message.connect(lambda role, text: messages.append((role, text)))
    value.voice_enabled = False
    try:
        deadline = time.monotonic() + 15
        while value.busy and time.monotonic() < deadline:
            QTest.qWait(50)
        assert value.status == "Ready", messages
        value.send(
            "Hello. Please reply with a short greeting. Do not inspect my computer."
        )
        assert value.busy
        deadline = time.monotonic() + 90
        ticks = 0
        while value.busy and time.monotonic() < deadline:
            QTest.qWait(50)
            ticks += 1
        assert any(role == "assistant" and text for role, text in messages), messages
        assert value.status == "Ready" and ticks > 0
        print("Real desktop reply:", messages[-1])
    finally:
        value.shutdown()


def test_automatic_mode_uses_native_speech_phase_and_submits_only_completed_turn(app):
    value, calls, sent = controller(app)
    value.setAutomatic(True, 2)
    assert calls[0][:2] == ("speech_start", {"device_index": 2, "automatic": True})
    calls[0][2]({"recording_id": "turn"}, None)
    assert value.voicePhase == "waiting" and value.automatic
    value.pollVoice()
    calls[-1][2]({"phase": "waiting", "level": 0.01}, None)
    assert value.voicePhase == "waiting" and not sent
    value.pollVoice()
    calls[-1][2]({"phase": "listening", "level": 0.7}, None)
    assert value.voicePhase == "listening" and value.audioLevel == 0.7 and not sent
    value.pollVoice()
    calls[-1][2]({"phase": "complete"}, None)
    assert calls[-1][0] == "speech_finish" and value.voicePhase == "processing"
    calls[-1][2]({"text": "What can you help with?"}, None)
    assert sent == ["What can you help with?"]
    value.poll_timer.stop()


def test_auto_off_during_open_cancels_late_capture_without_a_turn(app):
    value, calls, sent = controller(app)
    value.setAutomatic(True, -1)
    value.setAutomatic(False, -1)
    calls[0][2]({"recording_id": "late-auto"}, None)
    assert calls[-1][:2] == ("speech_cancel", {"recording_id": "late-auto"})
    calls[-1][2]({"cancelled": True}, None)
    assert not value.automatic and not value.busy and not sent


def test_auto_off_during_transcription_drops_late_final_command(app):
    value, calls, sent = controller(app)
    value.setAutomatic(True, -1)
    calls[0][2]({"recording_id": "turn"}, None)
    value.finishVoice()
    finish = calls[-1]
    value.setAutomatic(False, -1)
    finish[2]({"text": "Open an application"}, None)
    assert not value.automatic and not sent


def test_native_output_completion_controls_auto_rearm_and_never_a_fixed_speech_timer(
    app,
):
    value, calls, _ = controller(app)
    value._automatic = True
    value.spoken({"queued": True}, None)
    assert value.voicePhase == "speaking" and not value.recording
    value.pollVoice()
    calls[-1][2]({"speaking": True}, None)
    assert value.voicePhase == "speaking" and not value.recording
    value.pollVoice()
    calls[-1][2]({"speaking": False}, None)
    value.resume_automatic()
    assert calls[-1][0] == "speech_start" and value.recording
    value.cancelVoice()


def test_synthesis_waiting_for_output_never_rearms_automatic_microphone(app):
    value, calls, _ = controller(app)
    value._automatic = True
    value.spoken({"queued": True}, None)
    value.pollVoice()
    calls[-1][2]({"speaking": True, "output_phase": "queued"}, None)
    assert value.voicePhase == "processing" and not value.recording
    value.resume_automatic()
    assert not any(tool == "speech_start" for tool, _, _ in calls)
    value.pollVoice()
    calls[-1][2]({"speaking": True, "output_phase": "speaking"}, None)
    value.resume_automatic()
    assert not value.recording
    value.pollVoice()
    calls[-1][2]({"speaking": False, "output_phase": "idle"}, None)
    value.resume_automatic()
    assert calls[-1][0] == "speech_start"
    value.cancelVoice()


def test_stale_speech_ack_and_poll_cannot_revive_stopped_output(app):
    value, calls, _ = controller(app)
    epoch = value._speech_epoch
    value.spoken({"queued": True}, None, epoch)
    value.pollVoice()
    poll = calls[-1]
    value.stopSpeaking()
    value.spoken({"queued": True}, None, epoch)
    poll[2]({"speaking": True}, None)
    assert value.voicePhase == "idle" and not value._speaking


def test_capture_failure_stops_auto_and_never_dispatches_audio(app):
    value, calls, sent = controller(app)
    value.setAutomatic(True, -1)
    calls[0][2]({"recording_id": "turn"}, None)
    value.pollVoice()
    calls[-1][2]({"phase": "error", "error": "Microphone disconnected"}, None)
    assert not value.automatic and value.status == "Needs attention" and not sent
    assert calls[-1][0] == "speech_cancel"


def test_three_voice_animations_render_and_follow_controller_phase(app):
    from PySide6.QtCore import QObject

    value, _, _ = controller(app)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda entries: warnings.extend(str(e) for e in entries))
    engine.rootContext().setContextProperty("jarvis", value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "services/desktop/Main.qml")))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]
    orb = window.findChild(QObject, "voiceOrb")
    assert orb is not None
    for phase in ["waiting", "listening", "speaking"]:
        value._voice_phase = phase
        value._level = 0.8
        value.changed.emit()
        QTest.qWait(150)
        assert orb.property("phase") == phase
        assert window.grabWindow().save(str(ROOT / f"target/voice-{phase}.png"))
    assert not warnings, warnings
    window.close()


def test_stop_while_output_is_preparing_releases_interface_and_discards_late_ack(app):
    value, calls, _ = controller(app)
    value._speech_pending = True
    value.state("Preparing voice", True)
    epoch = value._speech_epoch
    value.stopSpeaking()
    value.spoken({"queued": True}, None, epoch)
    assert not value.busy and value.voicePhase == "idle"
    assert calls[-1][0] == "speech_stop"
    assert value.pool.maxThreadCount() == 1


def test_real_qml_hold_button_releases_one_turn_without_cancel_race(app):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtQuick import QQuickItem

    value, calls, sent = controller(app)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("jarvis", value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "services/desktop/Main.qml")))
    window = engine.rootObjects()[0]
    QTest.qWait(50)
    button = window.findChild(QQuickItem, "holdToTalk")
    position = button.mapToScene(
        QPointF(button.width() / 2, button.height() / 2)
    ).toPoint()
    QTest.mousePress(window, Qt.LeftButton, pos=position)
    assert calls[-1][0] == "speech_start" and value.recording
    calls[-1][2]({"recording_id": "mouse-turn"}, None)
    QTest.mouseRelease(window, Qt.LeftButton, pos=position)
    assert calls[-1][0] == "speech_finish"
    calls[-1][2]({"text": "Help me find a document"}, None)
    assert sent == ["Help me find a document"]
    assert not any(tool == "speech_cancel" for tool, _, _ in calls)
    window.close()


def test_muting_while_listening_preserves_microphone_phase(app):
    value, calls, _ = controller(app)
    value.setAutomatic(True, -1)
    calls[-1][2]({"recording_id": "turn"}, None)
    value.setVoiceEnabled(False)
    assert value.voicePhase == "waiting" and value.recording
    value.cancelVoice()


def test_recording_deadline_discards_instead_of_sending_a_cut_off_command(app):
    value, calls, sent = controller(app)
    value.startVoice(-1)
    calls[-1][2]({"recording_id": "long"}, None)
    value.voice_limit()
    assert calls[-1][0] == "speech_cancel"
    assert not sent and not any(tool == "speech_finish" for tool, _, _ in calls)


def test_worker_suggestion_mode_drives_one_card_and_speech_without_a_count_summary(app):
    import json
    from types import SimpleNamespace

    value, calls, _ = controller(app)
    reply = {
        "event": "response",
        "text": "Could budget-final.xlsx be the one?",
        "speech_text": "Could budget-final.xlsx be the one?",
        "presentation": "single",
        "items": [
            {
                "number": 3,
                "name": "budget-final.xlsx",
                "kind": "file",
                "location": "Downloads/budget-final.xlsx",
            }
        ],
        "page_token": "current",
        "page_info": {"total": 3, "scope": "Downloads"},
    }
    value.worker = SimpleNamespace(
        readAllStandardOutput=lambda: (json.dumps(reply) + "\n").encode()
    )
    value.read_worker()
    assert (
        value.resultMode == "single"
        and value.scopeNote == "Suggested match - Downloads"
    )
    assert calls[-1][:2] == (
        "speech_speak",
        {"text": reply["speech_text"], "language": "en"},
    )
    value._result_mode = "single"
    value.voice_enabled = False
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda entries: warnings.extend(str(e) for e in entries))
    engine.rootContext().setContextProperty("jarvis", value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "services/desktop/Main.qml")))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]
    value.results.emit(json.dumps(reply["items"]))
    QTest.qWait(150)
    assert window.grabWindow().save(str(ROOT / "target/recommendation-preview.png"))
    assert not warnings
    window.close()


def test_voice_test_routes_chosen_language_and_output_without_calling_agent(app):
    value, calls, sent = controller(app)
    value.setReplyLanguage("tr")
    value.setOutputDevice(1)
    value.testVoice()
    assert calls[-1][0] == "speech_speak"
    assert calls[-1][1]["language"] == "tr"
    assert calls[-1][1]["output_device_index"] == 1
    assert "Merhaba" in calls[-1][1]["text"] and not sent
    calls[-1][2]({"queued": True, "voice": "Tolga", "output_device": "OMEN"}, None)
    assert value.outputNote == "Tolga → OMEN"
    value.poll_timer.stop()


def test_selected_recognition_language_is_used_for_the_entire_final_transcript(app):
    value, calls, sent = controller(app)
    value.setLanguage("tr")
    value.startVoice(-1)
    calls[-1][2]({"recording_id": "turn"}, None)
    value.finishVoice()
    assert calls[-1][1]["language"] == "tr"
    calls[-1][2]({"text": "İkinci klasörü açma.", "language": "tr"}, None)
    assert sent == ["İkinci klasörü açma."]
    assert value.recognitionNote == "Last recognition: tr"


def test_actual_input_route_and_signal_are_visible_without_rewriting_transcript(app):
    value, calls, sent = controller(app)
    value.startVoice(1)
    calls[-1][2](
        {
            "recording_id": "turn",
            "input": {"name": "Microphone Array", "sample_rate": 48000, "channels": 2},
        },
        None,
    )
    assert value.inputNote == "Input: Microphone Array"
    value.finishVoice()
    calls[-1][2](
        {
            "text": "Merhaba Javi",
            "language": "tr",
            "signal": {"valid": True, "rms_dbfs": -48.0, "clipped_fraction": 0.0},
        },
        None,
    )
    assert "Low input level" in value.recognitionNote
    # Signal diagnostics never guess or silently replace the user's recognized words.
    assert sent == ["Merhaba Javi"]


def test_qml_recognition_default_matches_controller_and_voice_errors_are_visible(app):
    from PySide6.QtCore import QObject

    value, calls, _ = controller(app)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("jarvis", value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "services/desktop/Main.qml")))
    window = engine.rootObjects()[0]
    assert (
        window.findChild(QObject, "recognitionLanguage").property("currentIndex") == 2
    )
    value.device_status(
        {"default_output": "Realtek", "output_devices": [{"index": 0, "name": "OMEN"}]},
        None,
    )
    assert "Realtek" in value.outputs and "OMEN" in value.outputs
    messages = []
    value.message.connect(lambda role, text: messages.append((role, text)))
    value.testVoice()
    calls[-1][2](None, "No installed en speech voice")
    assert value.status == "Needs attention"
    assert messages[-1][0] == "system" and "No installed en" in messages[-1][1]
    window.close()


@pytest.mark.skipif(
    os.environ.get("JARVIS_RUN_VOICE_DEVICE_LIVE") != "1",
    reason="explicit real local speaker check",
)
@pytest.mark.parametrize(
    "language,text",
    [
        ("en", "Hello, this is JARVIS. Voice output is ready."),
        ("tr", "Merhaba, ben Jarvis. Sesli yanıt denemesi."),
    ],
)
def test_actual_qt_reply_reaches_native_voice_and_completes(app, language, text):
    import json
    from types import SimpleNamespace

    value = desktop.Controller(launch_worker=False)
    value.setReplyLanguage(language)
    value.worker = SimpleNamespace(
        readAllStandardOutput=lambda: (
            json.dumps(
                {
                    "event": "response",
                    "text": text,
                    "speech_text": text,
                }
            )
            + "\n"
        ).encode()
    )
    value.read_worker()
    saw_speaking = False
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            QTest.qWait(50)
            saw_speaking |= value.voicePhase == "speaking"
            if saw_speaking and value.voicePhase == "idle":
                break
            assert value.status != "Needs attention", value.outputNote
        assert saw_speaking and value.voicePhase == "idle"
        assert ("Zira" if language == "en" else "Tolga") in value.outputNote
        print("Qt native speech route:", language, value.outputNote)
    finally:
        value.stopSpeaking()
        deadline = time.monotonic() + 5
        while value._calls and time.monotonic() < deadline:
            QTest.qWait(50)


@pytest.mark.skipif(
    os.environ.get("JARVIS_RUN_DESKTOP_VOICE_LIVE") != "1",
    reason="explicit real QML, agent worker and native speech; no microphone",
)
def test_normal_qml_agent_reply_finishes_before_auto_rearm(app):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtQuick import QQuickItem

    value = desktop.Controller()
    messages, native_states, rearms = [], [], []
    value.message.connect(lambda role, text: messages.append((role, text)))
    real_core = value.core

    def traced_core(tool, args, callback):
        def completed(data, error):
            if tool == "speech_poll" and not args and data:
                native_states.append(dict(data))
            callback(data, error)

        real_core(tool, args, completed)

    value.core = traced_core

    # Observe the actual automatic rearm transition, without opening a microphone in this test.
    def rearm(device):
        rearms.append(time.monotonic())
        value._automatic = False

    value.startVoice = rearm
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("jarvis", value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "services/desktop/Main.qml")))
    window = engine.rootObjects()[0]
    try:
        deadline = time.monotonic() + 20
        while (value.busy or value.modelLoading) and time.monotonic() < deadline:
            QTest.qWait(50)
        assert value.status == "Ready", messages
        composer = window.findChild(QQuickItem, "composer")
        composer.setProperty(
            "text",
            "Hello. Please introduce yourself with two short sentences. Do not inspect my computer.",
        )
        button = window.findChild(QQuickItem, "sendMessage")
        position = button.mapToScene(
            QPointF(button.width() / 2, button.height() / 2)
        ).toPoint()
        QTest.mouseClick(window, Qt.LeftButton, pos=position)
        assert value.status == "Thinking"
        value._automatic = True
        value.changed.emit()
        deadline = time.monotonic() + 180
        while not rearms and time.monotonic() < deadline:
            QTest.qWait(50)
            assert value.status not in {"Needs attention", "Offline"}, messages
        assert any(role == "assistant" and text for role, text in messages), messages
        assert native_states and any(
            state.get("output_phase") == "speaking" for state in native_states
        ), native_states
        assert (
            native_states[-1].get("output_phase") == "idle"
            and not native_states[-1]["speaking"]
        )
        assert len(rearms) == 1
        print(
            "Normal agent/QML output phases:",
            [state.get("output_phase") for state in native_states],
        )
    finally:
        value._automatic = False
        value.shutdown()
        deadline = time.monotonic() + 5
        while value._calls and time.monotonic() < deadline:
            QTest.qWait(50)
        window.close()
