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

    OPEN = chr(60) + 'think' + chr(62)
    CLOSE = chr(60) + '/think' + chr(62)

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
                    # Hide the reasoning, but keep a suffix that may be the start of a
                    # split closing tag; anything else here is never shown.
                    keep = 0
                    for size in range(min(len(self.CLOSE) - 1, len(self.pending)), 0, -1):
                        if self.pending.endswith(self.CLOSE[:size]):
                            keep = size
                            break
                    self.pending = self.pending[len(self.pending) - keep:] if keep else ""
                    break
                self.pending = self.pending[end + len(self.CLOSE):]
                self.inside = False
                continue
            start = self.pending.find(self.OPEN)
            if start < 0:
                closed = self.pending.find(self.CLOSE)
                if closed >= 0:
                    # A closing tag with no opening tag is still a tag, not prose: drop it
                    # and keep every word after it.
                    out.append(self.pending[:closed])
                    self.pending = self.pending[closed + len(self.CLOSE):]
                    continue
                # Hold back only a suffix that may be the start of a tag. Both tokens count,
                # and the longest such suffix wins, so text after a tag is never lost.
                keep = 0
                for token in (self.OPEN, self.CLOSE):
                    for size in range(min(len(token) - 1, len(self.pending)), 0, -1):
                        if self.pending.endswith(token[:size]):
                            keep = max(keep, size)
                            break
                safe = len(self.pending) - keep
                out.append(self.pending[:safe])
                self.pending = self.pending[safe:]
                break
            out.append(self.pending[:start])
            self.pending = self.pending[start + len(self.OPEN):]
            self.inside = True
        return "".join(out)

    def flush(self) -> str:
        """Whatever is left at the end. A half-received tag is dropped, not shown."""
        rest, self.pending = self.pending, ""
        if self.inside:
            return ""
        # A single '<' is as likely a comparison sign as a cut tag, so it is kept; two or
        # more characters that only a tag could start with ("<t", "</") are not prose.
        if len(rest) > 1 and any(token.startswith(rest) for token in (self.OPEN, self.CLOSE)):
            return ""
        return rest


def strip(text: str) -> str:
    """Convenience for a complete (non-streamed) answer."""
    thinker = ThinkFilter()
    return (thinker.feed(text) + thinker.flush()).strip()
