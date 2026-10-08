"""Ephemeral conversation pairs; no persistence, raw Core payloads or trusted IDs."""

from collections import deque

from jarvis_brain.intelligence.contract import BrainResponse, ConversationTurn


class ConversationMemory:
    def __init__(self) -> None:
        self._turns: deque[ConversationTurn] = deque(maxlen=6)

    def clear(self) -> None:
        self._turns.clear()

    def snapshot(self) -> tuple[ConversationTurn, ...]:
        return tuple(self._turns)

    def observe(self, text: str, response: BrainResponse) -> BrainResponse:
        message = response.message
        if isinstance(response.data, dict) and "candidates" in response.data:
            # Candidate lists have a separate 120-second lifetime; never replay them in history.
            message = "Multiple applications matched; choose a displayed name or number."
        turn = ConversationTurn(text, message)
        # Drop complete oldest pairs, never truncate text into a different meaning.
        if len(turn.user) + len(turn.assistant) > 2400:
            self.clear()
            return response
        self._turns.append(turn)
        while sum(len(t.user) + len(t.assistant) for t in self._turns) > 2400:
            self._turns.popleft()
        return response
