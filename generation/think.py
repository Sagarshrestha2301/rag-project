"""Strip ` thinking...</think>` blocks from qwen3.5's output.

qwen3.5 emits those tags as literal text even with `think: false` — usually an empty
pair at the very start — so without this the UI shows "thinking" and the answer's
citations start after a stray tag. Tags can be split across chunks, so a partial tag
at the end of a chunk is held back until it resolves.

This lived in `ui/server.py`; it moved here when Step 6 needed it too, so there is one
implementation rather than two (UI and eval must strip the same way, or an answer is
scored on text the user never saw).
"""

from __future__ import annotations


class ThinkFilter:
    """Feed chunks in, get visible text out; `flush()` at the end."""

    OPEN = " thinking"
    CLOSE = "</think>"

    def __init__(self) -> None:
        self.pending = ""
        self.inside = False

    def feed(self, text: str) -> str:
        self.pending += text
        out: list[str] = []
        while self.pending:
            if self.inside:
                end = self.pending.find(self.CLOSE)
                if end < 0:
                    self.pending = self.pending[-(len(self.CLOSE) - 1):]
                    break
                self.pending = self.pending[end + len(self.CLOSE):]
                self.inside = False
                continue
            start = self.pending.find(self.OPEN)
            if start < 0:
                safe = len(self.pending)
                for size in range(1, len(self.OPEN)):
                    if self.pending.endswith(self.OPEN[:size]):
                        safe = len(self.pending) - size
                        break
                out.append(self.pending[:safe])
                self.pending = self.pending[safe:]
                break
            out.append(self.pending[:start])
            self.pending = self.pending[start + len(self.OPEN):]
            self.inside = True
        return "".join(out)

    def flush(self) -> str:
        rest, self.pending = self.pending, ""
        return "" if self.inside else rest


def strip(text: str) -> str:
    """Convenience for a complete (non-streamed) answer."""
    thinker = ThinkFilter()
    return (thinker.feed(text) + thinker.flush()).strip()
