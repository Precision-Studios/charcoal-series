# SPDX-License-Identifier: Apache-2.0
"""Build the Charcoal filter release."""
import concurrent.futures
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import time
import subprocess
import tempfile

ASSET = "filters-v1.json.gz"
TRUSTED = {"ublock-filters", "ublock-privacy", "ublock-badware", "ublock-quick-fixes", "ublock-unbreak"}
LIMIT = 100 * 1024 * 1024


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def fetch(source):
    deadline = time.monotonic() + 30
    for attempt in range(3):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("30-second source deadline exceeded")
        try:
            with tempfile.TemporaryFile() as body:
                request = subprocess.run(
                    ["curl", "--silent", "--show-error", "--location", "--proto", "=https",
                     "--proto-redir", "=https", "--max-time", str(remaining),
                     "--max-filesize", str(LIMIT), "--user-agent", "CharcoalBrowser filter publisher",
                     "--output", "-", "--write-out", "%{stderr}\n%{http_code}",
                     "--", source["url"]], stdout=body, stderr=subprocess.PIPE, text=True,
                )
                status = request.stderr.splitlines()[-1] if request.stderr else ""
                if status in {"403", "404"}:
                    raise RuntimeError(f'{source["id"]}: HTTP {status} at {source["url"]}')
                if request.returncode or not status.startswith("2"):
                    raise OSError(f"curl exit {request.returncode}, HTTP {status}")
                body.seek(0)
                data = body.read(LIMIT + 1)
            if len(data) > LIMIT:
                raise ValueError("oversized list")
            text = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
            if (text.lstrip().startswith(("<", "{")) or "\0" in text or
                    not re.search(r"(?m)^(?:@@|\|\||[\w.*,-]+#(?:#|@#)|(?:0\.0\.0\.0|127\.0\.0\.1)\s+|/[!-~]+/|\*\$)", text)):
                raise ValueError("invalid list body")
            return text
        except (OSError, ValueError) as error:
            if attempt == 2:
                raise
            time.sleep(min(2 ** attempt, max(0, deadline - time.monotonic())))


def simplify(raw, seen, source_index):
    # Record references to removed rules so the next build can recover a failed
    # publisher's ORIGINAL input even if the source owning its duplicate changed.
    kept, removed = [], []
    depth = 0
    continuing = False
    for position, line in enumerate(raw.split("\n")):
        stripped = line.strip()
        multiline = continuing or stripped.endswith("\\")
        continuing = stripped.endswith("\\")
        directive = re.match(r"^!#(if|else|endif)\b", line) if line.startswith("!#") else None
        if directive and directive[1] == "if":
            depth += 1
        # Hosts-file comments (including attribution) start with '#'. Only known
        # generic cosmetic separators can be rules when '#' starts the line.
        comment = line.startswith("#") and not line.startswith(("##", "#@#", "#?#", "#$#"))
        ordinary = (depth == 0 and not multiline and stripped and not comment and
                    not stripped.startswith(("!", "[")) and line == stripped)
        if ordinary and line in seen:
            removed.append([position, *seen[line]])
        else:
            if ordinary:
                seen[line] = (source_index, len(kept))
            kept.append(line)
        if directive and directive[1] == "endif":
            depth = max(0, depth - 1)
    return "\n".join(kept), removed


def originals(previous):
    if previous is None:
        return {}
    rows = previous["sources"]
    lines = ["".join(r["chunks"]).split("\n") for r in rows]
    result = {}
    for i, row in enumerate(rows):
        removed = {pos: lines[src][n] for pos, src, n in row["duplicates"]}
        kept = iter(lines[i])
        # An entirely deduplicated input with no trailing newline has zero kept lines.
        raw = "\n".join(removed[p] if p in removed else next(kept) for p in range(row["lineCount"]))
        if digest(raw) != row["originalSha256"]:
            raise ValueError("invalid recovery data for " + row["id"])
        result[row["id"]] = (raw, row)
    return result


def build(catalog, previous, download=fetch, now=None, report=print):
    old = originals(previous)
    now = int(time.time()) if now is None else now
    seen, rows = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        jobs = [pool.submit(download, s) for s in catalog]
        for i, (source, job) in enumerate(zip(catalog, jobs)):
            raw_old, meta = old.get(source["id"], (None, {}))
            try:
                raw = job.result()
                timestamp = now if raw != raw_old else meta["sourceDate"]
            except (OSError, ValueError) as error:
                if raw_old is None or meta["url"] != source["url"]:
                    raise RuntimeError(f'{source["id"]}: no validated copy available') from error
                raw, timestamp = raw_old, meta["sourceDate"]
                report(f'- {source["id"]}: reused snapshot aged {(now-timestamp)//3600} hours ({error}).')
            bucket = (source["group"], source["id"] in TRUSTED)
            text, duplicates = simplify(raw, seen.setdefault(bucket, {}), i)
            rows.append(dict(source, sourceDate=timestamp, originalSha256=digest(raw),
                             lineCount=raw.count("\n")+1, duplicates=duplicates, sha256=digest(text),
                             chunks=[text[j:j+16384] for j in range(0, len(text), 16384)]))
    return {"version": 1, "sources": rows}


def main():
    previous = None
    previous_file = Path("previous", ASSET)
    if previous_file.is_file():
        with gzip.open(previous_file, "rt", encoding="utf-8") as stream:
            previous = json.load(stream)
    catalog = json.loads(Path(__file__).with_name("sources.json").read_text())
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    def report(message):
        print(message)
        if summary:
            with open(summary, "a") as stream:
                print(message, file=stream)
    bundle = build(catalog, previous, report=report)
    if bundle == previous:
        report("The published filters are current.")
        return
    originals(bundle)  # Check that removal references recover every input.
    payload = json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode()
    if len(payload) > 256 * 1024 * 1024:
        raise ValueError("expanded bundle exceeds Android limit")
    with open(ASSET, "wb") as file, gzip.GzipFile(filename="", fileobj=file, mode="wb", mtime=0) as output:
        output.write(payload)
    if Path(ASSET).stat().st_size > LIMIT:
        raise ValueError("compressed bundle exceeds Android limit")
    report(f'Built {ASSET} with {len(catalog)} sources.')


if __name__ == "__main__":
    main()
