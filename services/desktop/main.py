"""Qt Quick desktop. Fixed worker bootstrap; all machine/device actions go through Core."""

import json
import sys
from pathlib import Path

from jarvis_brain.core.client import JarvisCoreClient
from jarvis_brain.errors import JarvisBrainError
from PySide6.QtCore import (
    Property,
    QObject,
    QProcess,
    QRunnable,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle


class Completion(QObject):
    done = Signal(object, object)


class CoreCall(QRunnable):
    def __init__(self, tool, arguments):
        super().__init__()
        self.tool, self.arguments = tool, arguments
        self.signals = Completion()

    def run(self):
        try:
            with JarvisCoreClient(
                connect_timeout=3,
                request_timeout=120
                if self.tool == "speech_finish"
                else 15
                if self.tool == "speech_start"
                else 5,
            ) as core:
                data = core.execute_tool(self.tool, self.arguments).data
            self.signals.done.emit(data, None)
        except (JarvisBrainError, OSError, ValueError) as error:
            self.signals.done.emit(None, str(error))


class Controller(QObject):
    changed = Signal()
    message = Signal(str, str)
    results = Signal(str)
    cleared = Signal()

    def __init__(self, launch_worker=True):
        super().__init__()
        self._status = "Connecting"
        self._busy = True
        self._recording = False
        self._automatic = False
        self._voice_phase = "idle"
        self._level = 0.0
        self._device = -1
        self._speaking = False
        self._speech_pending = False
        self._speech_epoch = 0
        self._polling = False
        self._shutting_down = False
        self._devices = [{"index": -1, "name": "System default microphone"}]
        self._recording_id = None
        self._released = False
        self._voice_language = "auto"
        self._reply_language = "en"
        self._output_device = -1
        self._outputs = [{"index": -1, "name": "Default speech output"}]
        self._output_note = ""
        self._recognition_note = "Recognition: Auto"
        self._epoch = 0
        self._page_token = ""
        self._scope_note = ""
        self._result_mode = "none"
        self._buffer = bytearray()
        self._calls = set()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)  # Preserve native start/speak/stop order.
        self.worker = QProcess(self)
        self.worker.setProgram(sys.executable)
        self.worker.setArguments(["-u", "-m", "jarvis_brain.desktop.worker"])
        self.worker.readyReadStandardOutput.connect(self.read_worker)
        self.worker.readyReadStandardError.connect(lambda: self.worker.readAllStandardError())
        self.worker.errorOccurred.connect(
            lambda _: self.failure("Assistant process could not start.")
        )
        self.worker.finished.connect(self.worker_finished)
        if launch_worker:
            self.worker.start()
        else:
            self.state("Ready", False)
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self.voice_limit)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(200)
        self.poll_timer.timeout.connect(self.pollVoice)

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(bool, notify=changed)
    def recording(self):
        return self._recording

    @Property(bool, notify=changed)
    def automatic(self):
        return self._automatic

    @Property(str, notify=changed)
    def voicePhase(self):
        return self._voice_phase

    @Property(float, notify=changed)
    def audioLevel(self):
        return self._level

    @Property(str, notify=changed)
    def devices(self):
        return json.dumps(self._devices)

    @Property(str, notify=changed)
    def recognitionLanguage(self):
        return self._voice_language

    @Property(str, notify=changed)
    def replyLanguage(self):
        return self._reply_language

    @Property(str, notify=changed)
    def outputs(self):
        return json.dumps(self._outputs)

    @Property(str, notify=changed)
    def outputNote(self):
        return self._output_note

    @Property(str, notify=changed)
    def recognitionNote(self):
        return self._recognition_note

    @Property(str, notify=changed)
    def resultMode(self):
        return self._result_mode

    @Property(str, notify=changed)
    def scopeNote(self):
        return self._scope_note

    def state(self, status, busy):
        self._status, self._busy = status, busy
        self.changed.emit()

    def failure(self, text):
        self._automatic = False
        self._voice_phase = "idle"
        self._level = 0.0
        self.poll_timer.stop()
        self.state("Needs attention", False)
        self.message.emit("system", text)

    def core(self, tool, arguments, callback):
        call = CoreCall(tool, arguments)
        self._calls.add(call)

        def done(data, error):
            self._calls.discard(call)
            callback(data, error)

        call.signals.done.connect(done)
        self.pool.start(call)

    def request(self, value):
        if self.worker.state() != QProcess.Running:
            self.failure("Assistant is offline. Close and reopen JARVIS.")
            return
        self._voice_phase = "processing"
        self.state("Thinking", True)
        self.worker.write((json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8"))

    @Slot(str)
    def send(self, text):
        text = text.strip()
        if self._busy or not text:
            return
        if len(text) > 2000:
            self.failure("Please use a shorter message.")
            return
        self.stopSpeaking()
        self.message.emit("user", text)
        self.request({"op": "chat", "text": text})

    @Slot(int)
    def select(self, number):
        if self._busy or not self._page_token:
            return
        self.stopSpeaking()
        self.message.emit("user", f"Open item {number}")
        self.request({"op": "select", "number": number, "page_token": self._page_token})

    @Slot()
    def reset(self):
        if self._busy:
            return
        self.stopSpeaking()
        self._epoch += 1
        self._page_token = ""
        self.results.emit("[]")
        self.cleared.emit()
        self.request({"op": "reset"})

    @Slot()
    def stopSpeaking(self):
        preparing = self._speech_pending
        self._speech_epoch += 1
        self._speech_pending = False
        self._speaking = False
        self._voice_phase = "idle"
        self._level = 0.0
        if not self._recording:
            self.poll_timer.stop()
        if preparing:
            self.state("Ready", False)
        self.changed.emit()
        self.core("speech_stop", {}, self.output_stopped)

    def output_stopped(self, _data, error):
        if error and not self._shutting_down:
            self.failure(f"Could not stop speech: {error}")

    @Slot(bool, int)
    def setAutomatic(self, enabled, device):
        if enabled:
            if self._busy or self._shutting_down:
                return
            self._automatic = True
            self._device = device
            self.startVoice(device)
        else:
            self._automatic = False
            if self._status == "Thinking":
                self.changed.emit()
            elif self._recording or self._status == "Transcribing":
                self.cancelVoice()
            else:
                self.stopSpeaking()
                self.changed.emit()

    def resume_automatic(self):
        if (
            self._automatic
            and not self._busy
            and not self._recording
            and not self._speaking
            and not self._speech_pending
            and not self._shutting_down
        ):
            self.startVoice(self._device)

    @Slot(int)
    def startVoice(self, device):
        if self._busy or self._shutting_down:
            return
        self._epoch += 1
        self._released = False
        self._recording = True
        self._speaking = False
        self._speech_pending = False
        self._voice_phase = "opening"
        self.state("Opening microphone", True)
        epoch = self._epoch

        def started(data, error):
            if epoch != self._epoch:
                if data and data.get("recording_id"):
                    self.core(
                        "speech_cancel",
                        {"recording_id": data["recording_id"]},
                        lambda _d, _e: self.cancelled(_d, _e, self._epoch),
                    )
                elif not self._shutting_down:
                    self.state("Ready", False)
                return
            if error:
                self._recording = False
                self.failure(error)
                return
            self._recording_id = data["recording_id"]
            self._voice_phase = "waiting" if self._automatic else "listening"
            self.state(
                "Waiting for speech" if self._automatic else "Listening - release to send", True
            )
            self.poll_timer.start()
            if not self._automatic:
                self.deadline.start(29000)
            if self._released:
                self.finishVoice()

        arguments = {} if device < 0 else {"device_index": device}
        if self._automatic:
            arguments["automatic"] = True
        self.core("speech_start", arguments, started)

    @Slot()
    def pollVoice(self):
        if self._polling or self._shutting_down:
            return
        token = self._recording_id
        if token is None and not self._speaking and not self._speech_pending:
            self.poll_timer.stop()
            return
        self._polling = True
        epoch = self._epoch
        speech_epoch = self._speech_epoch

        def polled(data, error):
            self._polling = False
            if epoch != self._epoch:
                return
            if token is None and speech_epoch != self._speech_epoch:
                return
            # Capture may have been released while this poll was in flight.
            if token is not None and token != self._recording_id:
                return
            if error:
                if self._recording:
                    self.cancelVoice()
                self.failure(error)
                return
            if token is not None:
                phase = data.get("phase")
                if phase == "error":
                    detail = data.get("error") or "Microphone stream failed"
                    self.cancelVoice()
                    self.failure(detail)
                elif phase == "complete":
                    self.finishVoice()
                else:
                    self._voice_phase = phase if phase in {"waiting", "listening"} else "opening"
                    self._level = float(data.get("level", 0.0))
                    self.state("Waiting for speech" if phase == "waiting" else "Listening", True)
            elif not self._speech_pending:
                self._speaking = bool(data.get("speaking"))
                queued = self._speaking and data.get("output_phase") == "queued"
                self._voice_phase = (
                    "processing" if queued else "speaking" if self._speaking else "idle"
                )
                self.state(
                    "Preparing voice" if queued else "Speaking" if self._speaking else "Ready",
                    False,
                )
                if not self._speaking:
                    self.poll_timer.stop()
                    QTimer.singleShot(300, self.resume_automatic)

        self.core("speech_poll", {} if token is None else {"recording_id": token}, polled)

    def voice_limit(self):
        self.cancelVoice()
        self.message.emit(
            "system", "Recording limit reached. Nothing sent; please use a shorter turn."
        )

    @Slot()
    def finishVoice(self):
        self._released = True
        if self._recording_id is None:
            return
        token, self._recording_id = self._recording_id, None
        self._recording = False
        self.deadline.stop()
        self.poll_timer.stop()
        self._voice_phase = "processing"
        self._level = 0.0
        self.state("Transcribing", True)
        epoch = self._epoch

        def finished(data, error):
            if epoch != self._epoch:
                return
            if error:
                self.failure(error)
                return
            text = data.get("text", "").strip()
            language = data.get("language")
            self._recognition_note = (
                f"Last recognition: {language}" if language else "No clear speech detected"
            )
            self._voice_phase = "idle"
            self.state("Ready", False)
            if not text:
                if self._automatic:
                    QTimer.singleShot(300, self.resume_automatic)
                else:
                    self.message.emit(
                        "system", "No clear speech detected. Hold the microphone and try again."
                    )
            else:
                self.send(text)

        self.core(
            "speech_finish", {"recording_id": token, "language": self._voice_language}, finished
        )

    @Slot(str)
    def setLanguage(self, language):
        if language in {"en", "tr", "auto"}:
            self._voice_language = language
            self.changed.emit()

    @Slot(str)
    def setReplyLanguage(self, language):
        if language in {"en", "tr"}:
            self._reply_language = language
            self.changed.emit()

    @Slot(int)
    def setOutputDevice(self, index):
        if -1 <= index < 32:
            self._output_device = index

    @Slot()
    def testVoice(self):
        if self._busy or self._recording:
            return
        self.stopSpeaking()
        self.speak_text(
            "Merhaba, ben Jarvis. Sesli yanıt denemesi."
            if self._reply_language == "tr"
            else "Hello, this is JARVIS. Voice output is ready."
        )

    def speak_text(self, text):
        if not isinstance(text, str) or not text.strip():
            self._voice_phase = "idle"
            self.changed.emit()
            QTimer.singleShot(300, self.resume_automatic)
            return
        self._voice_phase = "processing"
        self._speech_pending = True
        self.state("Preparing voice", True)
        arguments = {"text": text[:1024], "language": self._reply_language}
        if self._output_device >= 0:
            arguments["output_device_index"] = self._output_device
        epoch = self._speech_epoch
        self.core(
            "speech_speak",
            arguments,
            lambda data, error, epoch=epoch: self.spoken(data, error, epoch),
        )

    @Slot()
    def cancelVoice(self):
        self._automatic = False
        self._epoch += 1
        epoch = self._epoch
        self.deadline.stop()
        self.poll_timer.stop()
        self._recording = False
        self._released = True
        self._voice_phase = "idle"
        self._level = 0.0
        token, self._recording_id = self._recording_id, None
        if token:
            self.state("Stopping microphone", True)
            self.core(
                "speech_cancel",
                {"recording_id": token},
                lambda data, error: self.cancelled(data, error, epoch),
            )
        elif self._status == "Opening microphone":
            self.state("Stopping microphone", True)
        else:
            self.state("Ready", False)

    def cancelled(self, _data, error, epoch):
        if epoch != self._epoch or self._shutting_down:
            return
        if error:
            self.failure(error)
        elif self._status not in {"Needs attention", "Offline"}:
            self.state("Ready", False)

    @Slot(bool)
    def setVoiceEnabled(self, enabled):
        self.voice_enabled = enabled
        if not enabled and (self._speaking or self._speech_pending):
            self.stopSpeaking()
            # Resume only once the native stop acknowledges; no timer-based speech completion.
            if self._automatic and not self._busy:
                self.core("speech_stop", {}, lambda data, error: self.after_muting(data, error))

    def after_muting(self, data, error):
        self.output_stopped(data, error)
        if not error:
            QTimer.singleShot(300, self.resume_automatic)

    @Slot()
    def read_worker(self):
        self._buffer.extend(bytes(self.worker.readAllStandardOutput()))
        if len(self._buffer) > 128000:
            self._buffer.clear()
            self.failure("Assistant response exceeded the display limit.")
            return
        while b"\n" in self._buffer:
            line, _, remainder = self._buffer.partition(b"\n")
            self._buffer = bytearray(remainder)
            try:
                result = json.loads(line)
            except (ValueError, UnicodeError):
                continue  # Native diagnostic output is never interpreted as a command.
            if result.get("event") == "ready":
                self.state("Ready", False)
                self.core("speech_status", {}, self.device_status)
            elif result.get("event") == "error":
                self.failure(result["message"])
            elif result.get("event") == "response":
                self.state("Ready", False)
                self._page_token = result.get("page_token", "")
                info = result.get("page_info", {})
                self._result_mode = result.get("presentation", "none")
                if info and self._result_mode == "single":
                    self._scope_note = f"Suggested match - {info['scope']}"
                else:
                    shown = len(result.get("items", []))
                    self._scope_note = f"{shown} shown - {info['scope']}" if info else ""
                if info.get("partial"):
                    self._scope_note += (
                        "\nPartial catalog: files outside scanned roots may be missing."
                    )
                if result.get("has_more"):
                    self._scope_note += "\nAsk for the next page to see more."
                self.changed.emit()
                self.results.emit(json.dumps(result.get("items", []), ensure_ascii=False))
                text = result["text"]
                self.message.emit("assistant", text)
                if getattr(self, "voice_enabled", True) and text.strip():
                    speech = result.get("speech_text", text)
                    self.speak_text(speech)
                else:
                    self._voice_phase = "idle"
                    self.changed.emit()
                    QTimer.singleShot(300, self.resume_automatic)

    def spoken(self, data, error, epoch=None):
        if epoch is not None and epoch != self._speech_epoch:
            return
        self._speech_pending = False
        if error:
            self.failure(f"Voice output unavailable: {error}")
            return
        if data.get("voice") and data.get("output_device"):
            self._output_note = f"{data['voice']} → {data['output_device']}"
        self._speaking = True
        self._voice_phase = "speaking"
        self.state("Speaking", False)
        self.poll_timer.start()

    def device_status(self, data, error):
        if error:
            self.message.emit("system", f"Voice is unavailable: {error}")
            return
        self._devices = self._devices[:1] + data.get("devices", [])
        default = data.get("default_output", "Default speech output")
        self._outputs = [{"index": -1, "name": f"Default: {default}"}] + data.get(
            "output_devices", []
        )
        self._output_note = default
        if data.get("output_error"):
            self.message.emit("system", f"Voice output unavailable: {data['output_error']}")
        self.changed.emit()

    def worker_finished(self, *_):
        if self._recording:
            self.cancelVoice()
        self._automatic = False
        self.stopSpeaking()
        self.state("Offline", False)

    @Slot()
    def shutdown(self):
        self._shutting_down = True
        self._automatic = False
        self.poll_timer.stop()
        if self._recording:
            self.cancelVoice()
        self.stopSpeaking()
        self.worker.closeWriteChannel()
        if not self.worker.waitForFinished(1500):
            self.worker.terminate()
            if not self.worker.waitForFinished(1500):
                self.worker.kill()


def configure_appearance(app):
    QQuickStyle.setStyle("Basic")
    # The offscreen Windows platform has no system-font discovery. Register the same
    # installed UI font explicitly; this also makes development previews representative.
    font = Path("C:/Windows/Fonts/segoeui.ttf")
    if font.is_file():
        QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont("Segoe UI", 10))


def main():
    app = QGuiApplication(sys.argv)
    configure_appearance(app)
    app.setApplicationName("JARVIS")
    controller = Controller()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("jarvis", controller)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name("Main.qml"))))
    if not engine.rootObjects():
        controller.shutdown()
        return 1
    app.aboutToQuit.connect(controller.shutdown)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
