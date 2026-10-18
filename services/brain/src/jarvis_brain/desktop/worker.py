"""Fixed stdio session endpoint, spawned only by the installed desktop client.

No shell, executable selection or device access. Qt and CLI share JarvisBrain.
"""

import json
import sys
from uuid import uuid4

from jarvis_brain.core.client import JarvisCoreClient
from jarvis_brain.errors import JarvisBrainError
from jarvis_brain.intelligence.models.factory import create_agent_model
from jarvis_brain.intelligence.runtime import JarvisBrain


class Session:
    def __init__(self, core, model):
        self.brain = JarvisBrain(core, model)
        self.page_token = ""
        self.page_numbers = set()

    def request(self, request):
        if not isinstance(request, dict) or set(request) - {"op", "text", "number", "page_token"}:
            raise ValueError("Invalid desktop request")
        operation = request.get("op")
        if operation == "reset":
            self.brain.reset_context()
            self.page_token = ""
            self.page_numbers = set()
            return {
                "text": "Session cleared.",
                "items": [],
                "page_token": "",
                "page_info": {},
                "executed": False,
            }
        if operation == "chat":
            if set(request) != {"op", "text"}:
                raise ValueError("Invalid chat request")
            text = request["text"]
        elif operation == "select":
            if (
                set(request) != {"op", "number", "page_token"}
                or not self.page_token
                or request["page_token"] != self.page_token
                or type(request["number"]) is not int
                or request["number"] not in self.page_numbers
            ):
                raise ValueError("This result page has changed; choose from the current list.")
            text = str(request["number"])
        else:
            raise ValueError("Unknown desktop operation")
        response = self.brain.handle_text(text)
        return self.present(response)

    def present(self, response):
        files = self.brain._files
        items = self.brain._agent.builtins.recommendations.items()
        self.page_token = str(uuid4()) if items else ""
        self.page_numbers = {item["number"] for item in items}
        # Spoken and conversational output use the model's selected suggestion, not a page count.
        history = self.brain._conversation.snapshot()
        text = history[-1].assistant if history else response.message
        speech = text
        page_info = dict(files._page_info)
        if page_info:
            page_info["scope"] = (
                files._scope["name"]
                if files._scope and files._clock() < files._scope_expires
                else "Permitted catalog roots"
            )
        return {
            "text": text,
            "executed": response.executed,
            "items": items,
            "speech_text": speech,
            "presentation": self.brain._agent.builtins.recommendations.mode,
            "page_info": page_info,
            "page_token": self.page_token,
            "has_more": bool(files._page) if items else False,
        }


def main():
    model = create_agent_model()
    try:
        with JarvisCoreClient(request_timeout=120) as core:
            session = Session(core, model)
            print(json.dumps({"event": "ready"}), flush=True)
            while line := sys.stdin.buffer.readline(32769):
                try:
                    if len(line) > 32768 or not line.endswith(b"\n"):
                        raise ValueError("Desktop message exceeds limit")
                    request = json.loads(line)
                    result = session.request(request)
                    print(
                        json.dumps({"event": "response", **result}, ensure_ascii=False), flush=True
                    )
                except (JarvisBrainError, ValueError, TypeError) as error:
                    # Never replay a failed operation or fall back to old intent execution.
                    print(json.dumps({"event": "error", "message": str(error)[:500]}), flush=True)
    finally:
        model.unload()


if __name__ == "__main__":
    main()
