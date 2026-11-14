"""Step 4: turn parsed pages into chunks with metadata.

Split on the same tiers as `ingest/`: structure first, then one small module per
content type, each registered in one place.

Usage:
    from chunk import structure
    sections = structure.split_sections(pages)   # pages from index/parsed/pages.jsonl
"""
