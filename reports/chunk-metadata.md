# Chunk metadata coverage (Step 4 task 3)

Generated from `index/chunks.jsonl` after the page-evidence change of 2026-11-15.
Every number below is counted, not estimated; re-run the two commands at the bottom
to reproduce them.

| Field | Before | After | Of |
|---|---|---|---|
| year | 2,381 (73.8%) | 2,665 (82.6%) | 3,226 chunks |
| publisher | 1,665 (51.6%) | 1,670 (51.8%) | 3,226 chunks |
| doc_type | 3,027 (93.8%) | 3,027 (93.8%) | 3,226 chunks |
| section_path | 946 (29.3%) | 946 (29.3%) | 3,226 chunks |

Documents with a year: **68 of 95**; with a publisher: **38 of 95**.

## What changed and why the rest is still empty

The path is still the first source: `YYYY_` in the file name gives the year, and
`reports/<organisation>/` gives the publisher. Page 1 is now read **only when the path
says nothing**, and only for text a page actually prints:

- **year** — a volume line (`Vol. 8, No. 1, 2019`), a copyright line, or a month and
  year in the masthead (first 300 characters of page 1). +284 chunks.
- **publisher** — a journal or bulletin name printed in the same masthead area. +5 chunks.

Deliberately refused, each after measuring it:

- a bare month and year **anywhere** on page 1 (it matched six documents, two of them with
  `April 2026` in a footer — a print date is not a publication year);
- a journal name found outside the masthead (on two papers the only match is a citation in
  their own reference list: `Journal of Hydrology and Meteorology, Vol. 7`);
- the topic folder as publisher (`01_Floods_GLOFs` is not an organisation);
- a publisher for the 58 documents whose page-1 head is title and author only, such as
  `Beliefs, superstitions and taboos associated with bamboos in Nepal A.N. Das`. There is
  no outlet name on the page, so the field stays empty rather than borrowing one.

## Publishers now in the index

- `USGS` — 4 document(s)
- `NTNC` — 4 document(s)
- `DoFSC` — 3 document(s)
- `MoFE` — 3 document(s)
- `DHM` — 3 document(s)
- `Internet_Archive` — 2 document(s)
- `ICIMOD` — 2 document(s)
- `World_Bank` — 2 document(s)
- `MoALD` — 2 document(s)
- `NSO` — 2 document(s)
- `NPC` — 2 document(s)
- `DNPWC` — 2 document(s)
- `CGIAR` — 2 document(s)
- `ForestAction` — 2 document(s)
- `WWF_Nepal` — 2 document(s)
- `Dhaulagiri Journal of Sociology and Anthropology` — 1 document(s)

## One caveat on the years this adds

The masthead rule takes the printed date at face value. Two documents therefore gain
**2026** from an `April 2026` line, and 2020 and 2024 come from similar printed dates.
If one of those is a print date rather than a publication year, that document's year is
wrong rather than missing - it is listed under "Proposals for owner" in `STATUS.md` so
the owner can rule on it. The alternative (leaving it empty) is not obviously better for
retrieval, which uses the year as a filter, but it is the owner's call.

## Reproduce

```
.venv\Scripts\python.exe -m chunk.cli build
.venv\Scripts\python.exe chunk\test_meta.py
```

TODO(step-04): `section_path` at 29.3% is the next metadata gap; it is a heading-detection
problem (Step 4 task 1), not a provenance problem, and is not fixed here.
