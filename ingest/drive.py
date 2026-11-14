"""Fetch a bounded sample of PDFs from a shared Google Drive folder tree.

Nothing is hard-coded here: the folder is passed on the command line, the sample
size is an option, and every folder is discovered by walking the shared tree.
Folder names that start with "_" are treated as parked material and skipped
(`_wrong_pdf` is one), unless `--include-parked` asks for them.

Downloads land in `data/raw/<folder path>/<name>.pdf`, are hardlinked into
`data/corpus/<folder path>/` (D-030; copied only if the filesystem refuses a
link), and every file is appended to a JSONL manifest with its Drive id and
SHA-256. Re-running is safe: a leaf folder that already holds `--per-category`
PDFs is left alone.

Usage:
    .venv\\Scripts\\python.exe -m ingest.drive plan  --folder-id <id> --per-category 2
    .venv\\Scripts\\python.exe -m ingest.drive fetch --folder-id <id> --per-category 2

Example (one leaf folder, first two PDFs by name):
    data/raw/papers/02_Landslides_Earthquakes/0_Amod_An_Evaluation_of_Earthquake_Risk_Management_Initiatives_in_N_W7208270431.pdf
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import pathlib
import re
import shutil
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

LIST_URL = "https://drive.google.com/embeddedfolderview?id={folder}#list"
FILE_URL = "https://drive.usercontent.google.com/download?id={id}&export=download&confirm=t"
USER_AGENT = "rag-project-drive/1.0 (+local ingestion)"

RAW = pathlib.Path("data/raw")
CORPUS = pathlib.Path("data/corpus")
MANIFEST = pathlib.Path("logs/drive-downloads.jsonl")

_ENTRY = re.compile(
    r'<div class="flip-entry" id="entry-(?P<id>[^"]+)"[^>]*>.*?'
    r'<a href="(?P<href>[^"]+)".*?'
    r'flip-entry-title">(?P<title>[^<]*)</div>',
    re.S,
)


@dataclass(frozen=True)
class Entry:
    """One item in a Drive folder listing."""

    id: str
    name: str
    is_dir: bool

    @property
    def is_pdf(self) -> bool:
        return not self.is_dir and self.name.lower().endswith(".pdf")


def list_folder(folder_id: str, retries: int = 3) -> list[Entry]:
    """Every direct child of a shared folder, in Drive's listing order."""
    request = urllib.request.Request(
        LIST_URL.format(folder=folder_id), headers={"User-Agent": USER_AGENT}
    )
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8", "replace")
            break
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(2 * attempt)
    else:
        raise RuntimeError(f"could not list Drive folder {folder_id}: {last}")

    entries = []
    for match in _ENTRY.finditer(body):
        href = match.group("href")
        entries.append(
            Entry(
                id=match.group("id"),
                name=html.unescape(match.group("title")).strip(),
                is_dir="/drive/folders/" in href,
            )
        )
    if not entries and "flip-entries" not in body:
        raise RuntimeError(
            f"Drive folder {folder_id} returned {len(body)} bytes and no listing; "
            "check that the folder is shared with 'anyone with the link'"
        )
    return entries


def _walk(folder_id: str, prefix: tuple[str, ...], include_parked: bool):
    """Yield (relative folder path, Entry) for every PDF below `folder_id`."""
    for entry in list_folder(folder_id):
        if entry.is_dir:
            if entry.name.startswith("_") and not include_parked:
                continue
            yield from _walk(entry.id, prefix + (entry.name,), include_parked)
        elif entry.is_pdf:
            yield prefix, entry


def pdfs_by_folder(folder_id: str, include_parked: bool = False) -> dict[tuple[str, ...], list[Entry]]:
    """{relative folder path: [PDF entries, sorted by name]} for the whole tree."""
    folders: dict[tuple[str, ...], list[Entry]] = {}
    for prefix, entry in _walk(folder_id, (), include_parked):
        folders.setdefault(prefix, []).append(entry)
    for entries in folders.values():
        entries.sort(key=lambda e: e.name)
    return folders


def plan(folder_id: str, per_category: int, include_parked: bool = False) -> list[tuple[pathlib.Path, Entry]]:
    """The files to download: fill each leaf folder up to `per_category` PDFs."""
    wanted: list[tuple[pathlib.Path, Entry]] = []
    for prefix, entries in pdfs_by_folder(folder_id, include_parked).items():
        local = RAW.joinpath(*prefix)
        have = {p.name for p in local.glob("*.pdf")} if local.is_dir() else set()
        missing = [e for e in entries if e.name not in have]
        room = per_category - len(have)
        if room > 0:
            wanted.extend((local, entry) for entry in missing[:room])
    return wanted


def download(entry: Entry, dest: pathlib.Path, retries: int = 3) -> dict:
    """Write one Drive file to `dest` and return its manifest record."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(
        FILE_URL.format(id=entry.id), headers={"User-Agent": USER_AGENT}
    )
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        digest = hashlib.sha256()
        size = 0
        try:
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as fh:
                expected = response.headers.get("Content-Length")
                head = b""
                while chunk := response.read(1 << 20):
                    if len(head) < 1024:
                        head += chunk[: 1024 - len(head)]
                    fh.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            if b"%PDF-" not in head:
                raise ValueError("response is not a PDF (Drive may have returned an HTML page)")
            if expected is not None and int(expected) != size:
                raise ValueError(f"truncated download: {size} of {expected} bytes")
            os.replace(temporary, dest)
            break
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last = exc
            temporary.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(3 * attempt)
    else:
        raise RuntimeError(f"could not download {entry.name} ({entry.id}): {last}")

    return {
        "drive_id": entry.id,
        "path": str(dest),
        "bytes": size,
        "sha256": digest.hexdigest(),
        "downloaded": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def mirror(source: pathlib.Path, corpus_root: pathlib.Path = CORPUS) -> tuple[pathlib.Path, str]:
    """Hardlink `source` into the corpus tree, keeping its folder path (D-030)."""
    relative = source.relative_to(RAW)
    target = corpus_root / relative
    if target.exists():
        return target, "already there"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
        return target, "hardlink"
    except OSError:
        shutil.copy2(source, target)
        return target, "copied"


def record(info: dict, corpus: pathlib.Path, mode: str,
           manifest: pathlib.Path = MANIFEST) -> None:
    manifest.parent.mkdir(parents=True, exist_ok=True)
    row = {**info, "corpus": str(corpus), "link": mode}
    with manifest.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def local_hashes(root: pathlib.Path = RAW) -> dict[str, str]:
    """{sha256: path} for every PDF already downloaded, to skip duplicates.

    The same report appears under two folder names in the shared tree, so a
    second copy would add a duplicate document to the corpus (and a duplicate
    gold source later). Content, not file name, decides.
    """
    return {sha256(pdf): str(pdf) for pdf in sorted(root.rglob("*.pdf"))}


def main() -> int:
    parser = argparse.ArgumentParser(prog="ingest.drive")
    parser.add_argument("command", choices=["plan", "fetch"])
    parser.add_argument("--folder-id", required=True,
                        help="shared Drive folder id (the /folders/<id> part of the URL)")
    parser.add_argument("--per-category", type=int, default=2,
                        help="PDFs to keep in each leaf folder (default 2)")
    parser.add_argument("--include-parked", action="store_true",
                        help="also fetch folders whose name starts with '_'")
    args = parser.parse_args()

    wanted = plan(args.folder_id, args.per_category, args.include_parked)
    print(f"{len(wanted)} PDFs to fetch ({args.per_category} per leaf folder)")
    for folder, entry in wanted:
        print(f"  {folder / entry.name}")

    if args.command == "plan":
        return 0

    known = local_hashes()
    added = skipped = 0
    for number, (folder, entry) in enumerate(wanted, start=1):
        dest = folder / entry.name
        print(f"[{number}/{len(wanted)}] {dest}")
        info = download(entry, dest)
        if info["sha256"] in known:
            dest.unlink(missing_ok=True)
            skipped += 1
            print(f"  duplicate of {known[info['sha256']]}; not added")
            continue
        known[info["sha256"]] = str(dest)
        corpus, mode = mirror(dest)
        record(info, corpus, mode)
        added += 1
    print(f"done: {added} added, {skipped} duplicates skipped; manifest at {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
