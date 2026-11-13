"""Build and verify eval/questions.jsonl (Step 1, Stage A corpus).

Every gold quote is checked against the text actually extracted from the corpus
PDF, after whitespace normalisation. The script refuses to write the file if any
quote or page number does not check out, so a typo cannot become a silent gold
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

CORPUS_FILE = "data/corpus/1970_Marahatta_Relating_Hydrological_Extremes_with_Area_A_Case_on_Extreme_F_W2121362616.pdf"
EXPECTED_SHA256 = "1b42e67f590451c37499c5e065b39eb53b3d8497df961e3d8c75656ec6f5eb64"
OUT = pathlib.Path("eval/questions.jsonl")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def page_texts(path: str) -> list[str]:
    doc = pymupdf.open(path)
    return [norm(p.get_text()) for p in doc]


# id, split, type, question, history, answerable, gold_answer, gold_numbers, page, quote
Q = [
    ("q001", "dev", "fact",
     "What was the 24-hour rainfall depth recorded at Tistung on 20 July 1993?",
     [], True, "540 mm", [{"value": "540", "unit": "mm"}], 2,
     "The 24-hour rainfall depth of 540 mm at Tistung and 482 mm at Ghantemadi were recorded in morning hours of 20th July."),

    ("q002", "dev", "fact",
     "What was the peak flood in the Bagmati River during the July 1993 event?",
     [], True, "12,000 m3/s", [{"value": "12000", "unit": "m3 s-1"}], 3,
     "The peak floods in Bagmati and in East- Rapti River were found to be 12,000 m3 s-1 and 6800 m3s -1 respectively."),

    ("q003", "dev", "fact",
     "What was the highest rainfall intensity recorded at Pokhara and in which year?",
     [], True, "88 mm per hour, in 1989", [{"value": "88", "unit": "mm h-1"}, {"value": "1989", "unit": "year"}], 1,
     "The maximum rainfall intensity of 88 mm h-1 was recorded in 1989 at Pokhara in western region."),

    ("q004", "dev", "fact",
     "How large is the area of the Bagmati River basin whose physiography favoured severe flooding?",
     [], True, "about 1845 km2", [{"value": "1845", "unit": "km2"}], 2,
     "is only about 1845 km2."),

    ("q005", "heldout", "fact",
     "What return period does the paper attribute to the floods of 1993?",
     [], True, "approximately a 100 year return period", [{"value": "100", "unit": "years"}], 4,
     "Floods occurred in 1993 are of approximately 100 year recurring period."),

    ("q006", "dev", "fact",
     "What range of specific flows do streams with drainage areas between 100 and 3000 km2 show?",
     [], True, "4 to 15 m3 s-1 km-2", [{"value": "4", "unit": "m3 s-1 km-2"}, {"value": "15", "unit": "m3 s-1 km-2"}], 4,
     "The specific flows range from 4 to 15 m3s-1 km-2 in streams having drainage areas of different sizes (100 to 3000 km2)."),

    ("q007", "heldout", "fact",
     "What was the 48-hour rainfall depth at Ghantemadi?",
     [], True, "600 mm", [{"value": "600", "unit": "mm"}], 2,
     "The 48-hour rainfall depth at Ghantemadi was 600 mm."),

    ("q008", "dev", "exact",
     "Which roughness coefficient was used for the Bagmati River?",
     [], True, "0.06", [{"value": "0.06", "unit": "coefficient"}], 3,
     "0.06 for Bagmati"),

    ("q009", "dev", "exact",
     "What time lag was observed between the two rainfall peaks at Nibuwatar?",
     [], True, "26 hours", [{"value": "26", "unit": "hours"}], 2,
     "The time lag between two rainfall peaks at Nibuwatar is 26 hours."),

    ("q010", "heldout", "exact",
     "What correlation coefficient was found for equation (2)?",
     [], True, "0.78", [{"value": "0.78", "unit": "coefficient"}], 3,
     "The correlation coefficient is found to be 0.78"),

    ("q011", "dev", "exact",
     "For which catchment area range is equation (3) recommended?",
     [], True, "90 to 700 km2", [{"value": "90", "unit": "km2"}, {"value": "700", "unit": "km2"}], 4,
     "The equation (3) and the equation (4) can be recommended to apply only for areas between 90 to 700 Km2 and 90 to 2700 km2 respectively."),

    ("q012", "heldout", "exact",
     "What value of P0 was observed for the 48-hour duration in the study area?",
     [], True, "600 mm", [{"value": "600", "unit": "mm"}], 3,
     "In the study area, P0 is 540 mm and 600 mm observed in 1993 in 24-h and 48-h durations respectively."),

    ("q013", "dev", "summary",
     "How does the paper derive a relationship between rainfall depth and catchment area?",
     [], True,
     "It draws isohyet contours for 24-hour and 48-hour rainfall depths and fits an equation (1) for the depth-area-duration curves, in which the depth for a catchment area A decays exponentially from the maximum storm-centre depth P0.",
     [], 3,
     "Extreme rainfall: depth area duration Isohyet contours for 24-hour and 48-hour rainfall depths were drawn"),

    ("q014", "dev", "summary",
     "What extreme rainfall intensities does the paper say should be expected elsewhere in Nepal?",
     [], True,
     "About 60 to 80 mm per hour and 400-550 mm in 24 hours, in the lower Mahabharat and Siwalik regions at 300 to 3000 m altitude.",
     [{"value": "60", "unit": "mm h-1"}, {"value": "80", "unit": "mm h-1"}, {"value": "400", "unit": "mm"}, {"value": "550", "unit": "mm"}], 4,
     "The rainfall intensities of around 60 to 80 mm per hour and 400-550 mm in 24 hours are to be expected during unusual storms elsewhere in the country"),

    ("q015", "heldout", "summary",
     "What does the paper recommend about where equations (1) to (4) may be applied?",
     [], True,
     "Equations (3) and (4) apply only between 90 and 700 km2 and between 90 and 2700 km2 respectively; equations (1) and (2) may be used for extreme rainfall depths and extreme floods in ungauged catchments of the south central region and similar basins of Nepal.",
     [], 4,
     "However the equation (1) and equation (2) are recommended to assess extreme rainfall depths and extreme floods respectively for unguaged catchments in the south central region"),

    ("q016", "dev", "comparison",
     "How do the peak floods of the Bagmati and East-Rapti rivers compare?",
     [], True, "Bagmati reached 12,000 m3/s, East-Rapti 6800 m3/s, so Bagmati was the larger by about 5200 m3/s.",
     [{"value": "12000", "unit": "m3 s-1"}, {"value": "6800", "unit": "m3 s-1"}], 3,
     "The peak floods in Bagmati and in East- Rapti River were found to be 12,000 m3 s-1 and 6800 m3s -1 respectively."),

    ("q017", "dev", "comparison",
     "Compare the 24-hour rainfall at Tistung and at Ghantemadi.",
     [], True, "Tistung recorded 540 mm and Ghantemadi 482 mm, a difference of 58 mm.",
     [{"value": "540", "unit": "mm"}, {"value": "482", "unit": "mm"}], 2,
     "The 24-hour rainfall depth of 540 mm at Tistung and 482 mm at Ghantemadi"),

    ("q018", "heldout", "comparison",
     "Compare the hourly rainfall peaks at Tistung, Simlang and Nibuwatar.",
     [], True, "Tistung 70 mm/h, Simlang 67 mm/h and Nibuwatar 64 mm/h.",
     [{"value": "70", "unit": "mm h-1"}, {"value": "67", "unit": "mm h-1"}, {"value": "64", "unit": "mm h-1"}], 2,
     "The hourly rainfall intensities (Figure 2 and 3) during that period were 70 mm per hour in Tistung, 67 mm per hour in Simlang, and 64 mm per hour at Nibuwatar in Bhainse."),

    ("q019", "dev", "notfound",
     "What was the peak discharge of the Koshi River during the 2008 flood?",
     [], False, "", [], 1,
     ""),

    ("q020", "dev", "notfound",
     "What is the population living in the Bagmati catchment?",
     [], False, "", [], 2,
     ""),

    ("q021", "dev", "notfound",
     "What was the total economic loss caused by the July 1993 floods?",
     [], False, "", [], 1,
     ""),

    ("q022", "heldout", "notfound",
     "Which major flood struck Nepal after 1993?",
     [], False, "", [], 1,
     ""),

    ("q023", "dev", "followup",
     "And what was the 24-hour rainfall at Ghantemadi?",
     [{"role": "user", "content": "What was the 24-hour rainfall depth at Tistung on 20 July 1993?"},
      {"role": "assistant", "content": "540 mm."}],
     True, "482 mm", [{"value": "482", "unit": "mm"}], 2,
     "The 24-hour rainfall depth of 540 mm at Tistung and 482 mm at Ghantemadi were recorded in morning hours of 20th July."),

    ("q024", "heldout", "followup",
     "And what was the peak flood on the East-Rapti?",
     [{"role": "user", "content": "What was the peak flood in the Bagmati River in July 1993?"},
      {"role": "assistant", "content": "12,000 m3/s."}],
     True, "6800 m3/s", [{"value": "6800", "unit": "m3 s-1"}], 3,
     "The peak floods in Bagmati and in East- Rapti River were found to be 12,000 m3 s-1 and 6800 m3s -1 respectively."),
]


def main() -> int:
    digest = hashlib.sha256(pathlib.Path(CORPUS_FILE).read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        print(f"STOP: SHA-256 mismatch for {CORPUS_FILE}\n  expected {EXPECTED_SHA256}\n  actual   {digest}")
        return 1

    pages = page_texts(CORPUS_FILE)
    problems = []
    for qid, _, _, _, _, answerable, _, _, page, quote in Q:
        if not quote:
            continue
        if not 1 <= page <= len(pages):
            problems.append(f"{qid}: page {page} outside 1..{len(pages)}")
        elif quote not in pages[page - 1]:
            problems.append(f"{qid}: quote not found on page {page}\n    wanted: {quote[:110]}")

    if problems:
        print("FAILED quote verification:")
        for p in problems:
            print(" ", p)
        return 1

    lines = []
    for qid, split, qtype, question, history, answerable, gold, numbers, page, quote in Q:
        lines.append({
            "id": qid,
            "split": split,
            "type": qtype,
            "question": question,
            "history": history,
            "answerable": answerable,
            "gold_answer": gold,
            "gold_numbers": numbers,
            "gold_sources": [{"file": CORPUS_FILE, "page": page, "sha256": EXPECTED_SHA256}],
            "gold_quote": quote,
            "added_in_step": 1,
            "notes": "draft awaiting owner approval" if qtype != "notfound" else "confirm the answer is truly absent before approval",
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as fh:
        for row in lines:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    dev = sum(1 for r in lines if r["split"] == "dev")
    held = len(lines) - dev
    nf_dev = sum(1 for r in lines if r["split"] == "dev" and not r["answerable"])
    print(f"wrote {OUT} with {len(lines)} questions ({dev} dev / {held} held-out)")
    print(f"not-found on dev: {nf_dev}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
