"""Build and verify eval/questions.jsonl (Step 1, Stage A corpus, 5 documents).

Every gold quote is checked against the text actually extracted from the cited
corpus page, after whitespace normalisation, and every corpus file's SHA-256 is
checked against the pinned value. The script refuses to write the file if any
quote, page or hash does not check out, so a typo cannot become a silent gold
error.

Usage:
    .venv\\Scripts\\python.exe eval\\build_questions.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

import pymupdf

# key -> (corpus path, pinned sha256). Hashes are verified before anything is written.
FILES = {
    "marahatta": (
        "data/corpus/1970_Marahatta_Relating_Hydrological_Extremes_with_Area_A_Case_on_Extreme_F_W2121362616.pdf",
        "1b42e67f590451c37499c5e065b39eb53b3d8497df961e3d8c75656ec6f5eb64",
    ),
    "das": (
        "data/corpus/1970_Das_Beliefs_superstitions_and_taboos_associated_with_bamboos_in_W1999918290.pdf",
        "a483da15858555cf0a6106167201bb9ff572f1e4dbb73beb47f80a499ff88cd2",
    ),
}

OUT = pathlib.Path("eval/questions.jsonl")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# id, split, type, question, history, answerable, gold_answer, gold_numbers, file key, page, quote
Q = [
    # ---------------- specific fact (7) ----------------
    ("q001", "dev", "fact",
     "What was the 24-hour rainfall depth recorded at Tistung on 20 July 1993?",
     [], True, "540 mm", [{"value": "540", "unit": "mm"}], "marahatta", 2,
     "The 24-hour rainfall depth of 540 mm at Tistung and 482 mm at Ghantemadi were recorded in morning hours of 20th July."),

    ("q002", "dev", "fact",
     "What was the peak flood in the Bagmati River during the July 1993 event?",
     [], True, "12,000 m3/s", [{"value": "12000", "unit": "m3 s-1"}], "marahatta", 3,
     "The peak floods in Bagmati and in East- Rapti River were found to be 12,000 m3 s-1 and 6800 m3s -1 respectively."),

    ("q003", "dev", "fact",
     "What was the highest rainfall intensity recorded at Pokhara and in which year?",
     [], True, "88 mm per hour, in 1989", [{"value": "88", "unit": "mm h-1"}, {"value": "1989", "unit": "year"}], "marahatta", 1,
     "The maximum rainfall intensity of 88 mm h-1 was recorded in 1989 at Pokhara in western region."),

    ("q004", "dev", "fact",
     "How large is the area of the Bagmati River basin whose physiography favoured severe flooding?",
     [], True, "about 1845 km2", [{"value": "1845", "unit": "km2"}], "marahatta", 2,
     "is only about 1845 km2."),

    ("q005", "heldout", "fact",
     "What return period does the paper attribute to the floods of 1993?",
     [], True, "approximately a 100 year return period", [{"value": "100", "unit": "years"}], "marahatta", 4,
     "Floods occurred in 1993 are of approximately 100 year recurring period."),

    ("q006", "dev", "fact",
     "What range of specific flows do streams with drainage areas between 100 and 3000 km2 show?",
     [], True, "4 to 15 m3 s-1 km-2", [{"value": "4", "unit": "m3 s-1 km-2"}, {"value": "15", "unit": "m3 s-1 km-2"}], "marahatta", 4,
     "The specific flows range from 4 to 15 m3s-1 km-2 in streams having drainage areas of different sizes (100 to 3000 km2)."),

    ("q007", "heldout", "fact",
     "What was the 48-hour rainfall depth at Ghantemadi?",
     [], True, "600 mm", [{"value": "600", "unit": "mm"}], "marahatta", 2,
     "The 48-hour rainfall depth at Ghantemadi was 600 mm."),

    # ---------------- exact lookup (5) ----------------
    ("q008", "dev", "exact",
     "Which roughness coefficient was used for the Bagmati River?",
     [], True, "0.06", [{"value": "0.06", "unit": "coefficient"}], "marahatta", 3,
     "0.06 for Bagmati"),

    ("q009", "dev", "exact",
     "What time lag was observed between the two rainfall peaks at Nibuwatar?",
     [], True, "26 hours", [{"value": "26", "unit": "hours"}], "marahatta", 2,
     "The time lag between two rainfall peaks at Nibuwatar is 26 hours."),

    ("q010", "heldout", "exact",
     "What correlation coefficient was found for equation (2)?",
     [], True, "0.78", [{"value": "0.78", "unit": "coefficient"}], "marahatta", 3,
     "The correlation coefficient is found to be 0.78"),

    ("q011", "dev", "exact",
     "For which catchment area range is equation (3) recommended?",
     [], True, "90 to 700 km2", [{"value": "90", "unit": "km2"}, {"value": "700", "unit": "km2"}], "marahatta", 4,
     "The equation (3) and the equation (4) can be recommended to apply only for areas between 90 to 700 Km2 and 90 to 2700 km2 respectively."),

    ("q012", "heldout", "exact",
     "What value of P0 was observed for the 48-hour duration in the study area?",
     [], True, "600 mm", [{"value": "600", "unit": "mm"}], "marahatta", 3,
     "In the study area, P0 is 540 mm and 600 mm observed in 1993 in 24-h and 48-h durations respectively."),

    # ---------------- summary (3) ----------------
    ("q013", "dev", "summary",
     "How does the paper derive a relationship between rainfall depth and catchment area?",
     [], True,
     "It draws isohyet contours for 24-hour and 48-hour rainfall depths and fits an equation (1) for the depth-area-duration curves, in which the depth for a catchment area A decays exponentially from the maximum storm-centre depth P0.",
     [], "marahatta", 3,
     "Extreme rainfall: depth area duration Isohyet contours for 24-hour and 48-hour rainfall depths were drawn"),

    ("q014", "dev", "summary",
     "What extreme rainfall intensities does the paper say should be expected elsewhere in Nepal?",
     [], True,
     "About 60 to 80 mm per hour and 400-550 mm in 24 hours, in the lower Mahabharat and Siwalik regions at 300 to 3000 m altitude.",
     [{"value": "60", "unit": "mm h-1"}, {"value": "80", "unit": "mm h-1"}, {"value": "400", "unit": "mm"}, {"value": "550", "unit": "mm"}], "marahatta", 4,
     "The rainfall intensities of around 60 to 80 mm per hour and 400-550 mm in 24 hours are to be expected during unusual storms elsewhere in the country"),

    ("q015", "heldout", "summary",
     "What does the paper recommend about where equations (1) to (4) may be applied?",
     [], True,
     "Equations (3) and (4) apply only between 90 and 700 km2 and between 90 and 2700 km2 respectively; equations (1) and (2) may be used for extreme rainfall depths and extreme floods in ungauged catchments of the south central region and similar basins of Nepal.",
     [], "marahatta", 4,
     "However the equation (1) and equation (2) are recommended to assess extreme rainfall depths and extreme floods respectively for unguaged catchments in the south central region"),

    # ---------------- comparison (3) ----------------
    ("q016", "dev", "comparison",
     "How do the peak floods of the Bagmati and East-Rapti rivers compare?",
     [], True, "Bagmati reached 12,000 m3/s, East-Rapti 6800 m3/s, so Bagmati was the larger by about 5200 m3/s.",
     [{"value": "12000", "unit": "m3 s-1"}, {"value": "6800", "unit": "m3 s-1"}], "marahatta", 3,
     "The peak floods in Bagmati and in East- Rapti River were found to be 12,000 m3 s-1 and 6800 m3s -1 respectively."),

    ("q017", "dev", "comparison",
     "Compare the 24-hour rainfall at Tistung and at Ghantemadi.",
     [], True, "Tistung recorded 540 mm and Ghantemadi 482 mm, a difference of 58 mm.",
     [{"value": "540", "unit": "mm"}, {"value": "482", "unit": "mm"}], "marahatta", 2,
     "The 24-hour rainfall depth of 540 mm at Tistung and 482 mm at Ghantemadi"),

    ("q018", "heldout", "comparison",
     "Compare the hourly rainfall peaks at Tistung, Simlang and Nibuwatar.",
     [], True, "Tistung 70 mm/h, Simlang 67 mm/h and Nibuwatar 64 mm/h.",
     [{"value": "70", "unit": "mm h-1"}, {"value": "67", "unit": "mm h-1"}, {"value": "64", "unit": "mm h-1"}], "marahatta", 2,
     "The hourly rainfall intensities (Figure 2 and 3) during that period were 70 mm per hour in Tistung, 67 mm per hour in Simlang, and 64 mm per hour at Nibuwatar in Bhainse."),

    # ---------------- not-found (4) ----------------
    ("q019", "dev", "notfound",
     "What was the peak discharge of the Koshi River during the 2008 flood?",
     [], False, "", [], "marahatta", 1, ""),

    ("q020", "dev", "notfound",
     "What is the population living in the Bagmati catchment?",
     [], False, "", [], "marahatta", 2, ""),

    ("q021", "dev", "notfound",
     "What was the total economic loss caused by the July 1993 floods?",
     [], False, "", [], "marahatta", 1, ""),

    ("q022", "heldout", "notfound",
     "Which major flood struck Nepal after 1993?",
     [], False, "", [], "marahatta", 1, ""),

    # ---------------- follow-up (2) ----------------
    ("q023", "dev", "followup",
     "And what was the 24-hour rainfall at Ghantemadi?",
     [{"role": "user", "content": "What was the 24-hour rainfall depth at Tistung on 20 July 1993?"},
      {"role": "assistant", "content": "540 mm."}],
     True, "482 mm", [{"value": "482", "unit": "mm"}], "marahatta", 2,
     "The 24-hour rainfall depth of 540 mm at Tistung and 482 mm at Ghantemadi were recorded in morning hours of 20th July."),

    ("q024", "heldout", "followup",
     "And what was the peak flood on the East-Rapti?",
     [{"role": "user", "content": "What was the peak flood in the Bagmati River in July 1993?"},
      {"role": "assistant", "content": "12,000 m3/s."}],
     True, "6800 m3/s", [{"value": "6800", "unit": "m3 s-1"}], "marahatta", 3,
     "The peak floods in Bagmati and in East- Rapti River were found to be 12,000 m3 s-1 and 6800 m3s -1 respectively."),

    # ---------------- table lookup (6), from Das Tables 1-3 and 4 ----------------
    ("q025", "dev", "table",
     "According to Table 1, how many Terai households believe in taboos and superstitions associated with bamboos?",
     [], True, "139 households (69.85% of Terai households)", [{"value": "139", "unit": "households"}], "das", 2,
     "Believe in taboos and superstitions 139 69.85 79 37.96 16 39.02"),

    ("q026", "dev", "table",
     "In Table 2, how many Midhills households do not believe in the superstitions and taboos against bamboo planting?",
     [], True, "102 households (49.04% of Midhills households)", [{"value": "102", "unit": "households"}], "das", 6,
     "Do not believe 54 27.14 102 49.04 19 46.34"),

    ("q027", "dev", "table",
     "In Table 2, how many Terai households strongly believe in the superstitions and taboos against bamboo planting?",
     [], True, "28 households (14.07% of Terai households)", [{"value": "28", "unit": "households"}], "das", 6,
     "Strongly believe 28 14.07 16 7.69 0 0.00"),

    ("q028", "dev", "table",
     "In Table 2, how many households in Kerabari strongly disbelieve in the superstitions and taboos?",
     [], True, "2 households (4.88% of Kerabari households)", [{"value": "2", "unit": "households"}], "das", 6,
     "Strongly disbelieve 0 0.00 4 1.92 2 4.88"),

    ("q029", "heldout", "table",
     "In the Terai table on belief and growing status, how many growers believe that superstition discourages bamboo planting?",
     [], True, "71 growers (63.39% of growers)", [{"value": "71", "unit": "households"}], "das", 9,
     "Grower 41 36.61 68.33 71 63.39 51.08"),

    ("q030", "heldout", "table",
     "How many households were surveyed in Kerabari, and how many in the Midhills?",
     [], True, "41 in Kerabari and 208 in the Midhills", [{"value": "41", "unit": "households"}, {"value": "208", "unit": "households"}], "das", 6,
     "Terai (N=199) Midhills (N=208) Kerabari (N=41)"),
]


def main() -> int:
    pages: dict[str, list[str]] = {}
    problems: list[str] = []

    for key, (path, expected) in FILES.items():
        p = pathlib.Path(path)
        if not p.exists():
            problems.append(f"{key}: missing corpus file {path}")
            continue
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        if digest != expected:
            problems.append(f"{key}: SHA-256 mismatch\n    expected {expected}\n    actual   {digest}")
            continue
        pages[key] = [norm(pg.get_text()) for pg in pymupdf.open(path)]

    for qid, _, _, _, _, _, _, _, key, page, quote in Q:
        if key not in pages:
            continue
        if not quote:
            continue
        if not 1 <= page <= len(pages[key]):
            problems.append(f"{qid}: page {page} outside 1..{len(pages[key])}")
        elif quote not in pages[key][page - 1]:
            problems.append(f"{qid}: quote not found on {key} page {page}\n    wanted: {quote[:110]}")

    if problems:
        print("FAILED verification:")
        for p in problems:
            print(" ", p)
        return 1

    rows = []
    for qid, split, qtype, question, history, answerable, gold, numbers, key, page, quote in Q:
        rows.append({
            "id": qid,
            "split": split,
            "type": qtype,
            "question": question,
            "history": history,
            "answerable": answerable,
            "gold_answer": gold,
            "gold_numbers": numbers,
            "gold_sources": [{"file": FILES[key][0], "page": page, "sha256": FILES[key][1]}],
            "gold_quote": quote,
            "added_in_step": 1,
            "notes": ("draft awaiting owner approval" if answerable
                      else "confirm the answer is truly absent before approval"),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    dev = sum(1 for r in rows if r["split"] == "dev")
    held = len(rows) - dev
    nf_dev = sum(1 for r in rows if r["split"] == "dev" and not r["answerable"])
    types: dict[str, int] = {}
    for r in rows:
        types[r["type"]] = types.get(r["type"], 0) + 1
    print(f"wrote {OUT} with {len(rows)} questions ({dev} dev / {held} held-out)")
    print(f"types: {types}")
    print(f"not-found on dev: {nf_dev}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
