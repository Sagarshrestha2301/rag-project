"""Command line for the parsed corpus.

    .venv\\Scripts\\python.exe -m ingest.cli build     # parse data/corpus -> index/parsed
    .venv\\Scripts\\python.exe -m ingest.cli verify    # checks + review sheet + report
    .venv\\Scripts\\python.exe -m ingest.cli all       # both, in order
"""

from __future__ import annotations

import argparse
import pathlib

from ingest import manifest, verify


def main() -> int:
    ap = argparse.ArgumentParser(prog="ingest")
    ap.add_argument("command", choices=["build", "verify", "all"])
    ap.add_argument("--out", default="index/parsed")
    args = ap.parse_args()

    if args.command in ("build", "all"):
        print("building parsed corpus…")
        built = manifest.build(pathlib.Path(args.out))
        print(f"  totals: {built['totals']}")

    if args.command in ("verify", "all"):
        pages, found, built = verify.load()
        tables_report = verify.check_tables(found)
        speed = verify.throughput(built)
        report = verify.write_report(tables_report, speed, built)
        sheet = verify.review_html(pages)
        table_sheet = verify.tables_html(found)
        print(f"  tables: {tables_report['tables']}, numeric tokens: "
              f"{tables_report['numeric_tokens']}, matched: {tables_report['matched']}")
        print(f"  speed: {speed['text_pages_per_min']} text pages/min, "
              f"{speed['total_seconds']} s total")
        print(f"  wrote {report}")
        print(f"  wrote {sheet}")
        print(f"  wrote {table_sheet}")
        if tables_report["problems"]:
            print("  MISMATCHES:")
            for problem in tables_report["problems"][:10]:
                print("   -", problem)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
