"""Shared shapes for Step 4: blocks and sections.

`ingest` hands over pages of text blocks; this module gives those blocks stable
identities and groups them into sections, so every later step can ask "which
section is this chunk in?" without re-parsing anything.

Usage:
    from chunk.base import Block
    Block(pdf_page=3, text="2.\\nDATA USED AND METHODOLOGY", index=17)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Block:
    """One text block from a page, with its position in the document stream."""

    pdf_page: int
    text: str
    index: int          # 0-based position across the whole document


@dataclass
class Section:
    """A heading plus the blocks under it, up to the next heading.

    `path` is the full heading stack, so a subsection carries its parents:
    ["3. RESULTS AND DISCUSSION", "3.1 Onset and Withdrawal"].

    `source` says whether the path came from a real heading ("heading") or the
    document has none and the section is just a page's worth of paragraphs
    ("none"). Four of this corpus's pages have no headings at all, and a reader
    must be able to tell a real section path from a missing one.
    """

    number: str
    title: str
    path: list[str] = field(default_factory=list)
    source: str = "heading"          # "heading" | "none"
    heading_page: int = 0
    blocks: list[Block] = field(default_factory=list)

    @property
    def label(self) -> str:
        """The section's own name, e.g. "3.1 Onset and Withdrawal"."""
        return self.path[-1] if self.path else ""

    @property
    def page_start(self) -> int:
        return self.blocks[0].pdf_page if self.blocks else self.heading_page

    @property
    def page_end(self) -> int:
        return self.blocks[-1].pdf_page if self.blocks else self.heading_page

    @property
    def text(self) -> str:
        """The section's body, paragraphs separated by a blank line."""
        return "\n\n".join(block.text for block in self.blocks)
