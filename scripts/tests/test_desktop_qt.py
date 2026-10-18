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
        while value.busy and time.monotonic() < deadline:
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
