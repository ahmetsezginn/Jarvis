"""Native-approved desktop termination. No tray resident or background microphone."""

from PySide6.QtCore import QObject, QThreadPool, QTimer


class DesktopLifecycle(QObject):
    def __init__(self, app, controller, core_call_type):
        super().__init__(controller)
        self.app, self.controller = app, controller
        self.session = None
        self.revision = -1
        self.closed = False
        self.pending = False
        self.calls = set()
        self.core_call_type = core_call_type
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.poll)
        controller.desktopEvent.connect(self.apply)

    def core(self, tool, args, callback):
        call = self.core_call_type(tool, args)
        self.calls.add(call)

        def done(data, error):
            self.calls.discard(call)
            if not self.closed:
                callback(data, error)

        call.signals.done.connect(done)
        self.pool.start(call)

    def start(self):
        self.core("desktop_attach", {}, self.attached)

    def attached(self, data, error):
        if error:
            self.controller.message.emit("system", f"Conversation close unavailable: {error}")
            return
        self.session = data["session"]
        self.apply(data)
        self.timer.start()

    def poll(self):
        if self.pending or not self.session:
            return
        self.pending = True

        def polled(data, error):
            self.pending = False
            if error:
                self.timer.stop()
                self.controller.message.emit("system", f"Desktop control unavailable: {error}")
            else:
                self.apply(data)

        self.core("desktop_poll", {"session": self.session}, polled)

    def apply(self, data):
        revision = data.get("revision")
        if type(revision) is not int or revision <= self.revision:
            return
        self.revision = revision
        if data.get("closing") is True and not self.controller._closing:
            self.controller._closing = True
            self.controller._automatic = False
            self.timer.stop()
            self.app.quit()

    def shutdown(self):
        self.closed = True
        self.timer.stop()
        if self.session:
            from jarvis_brain.core.client import JarvisCoreClient
            from jarvis_brain.errors import JarvisBrainError

            try:
                with JarvisCoreClient(connect_timeout=1, request_timeout=2) as core:
                    core.execute_tool("desktop_detach", {"session": self.session})
            except (JarvisBrainError, OSError, ValueError) as error:
                print(f"JARVIS desktop detach: {error}")
