"""Explicit real Qt/worker/model/Core termination smoke; no microphone or tray resident."""

import importlib.util
import time
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    desktop = load("jarvis_close_desktop", ROOT / "services/desktop/main.py")
    lifecycle_module = load(
        "jarvis_close_lifecycle", ROOT / "services/desktop/lifecycle.py"
    )
    app = QGuiApplication([])
    desktop.configure_appearance(app)
    controller = desktop.Controller()
    controller.voice_enabled = False
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("jarvis", controller)
    engine.load(QUrl.fromLocalFile(str(ROOT / "services/desktop/Main.qml")))
    assert engine.rootObjects()
    lifecycle = lifecycle_module.DesktopLifecycle(app, controller, desktop.CoreCall)
    lifecycle.start()
    messages, sent = [], []
    controller.message.connect(lambda role, text: messages.append((role, text)))
    app.aboutToQuit.connect(lifecycle.shutdown)
    app.aboutToQuit.connect(controller.shutdown)
    started = time.monotonic()

    def tick():
        if time.monotonic() - started > 150:
            app.quit()
        elif lifecycle.session and not controller.busy and not sent:
            sent.append(True)
            controller.send("Jarvis kendini kapatabilirsin.")

    timer = QTimer()
    timer.setInterval(100)
    timer.timeout.connect(tick)
    timer.start()
    result = app.exec()
    timer.stop()
    assert result == 0 and controller._closing, messages
    assert controller.worker.state() == desktop.QProcess.NotRunning
    assert lifecycle.closed
    print(
        "Native-approved conversational close exited Qt and stopped Brain worker:",
        messages,
    )


if __name__ == "__main__":
    main()
