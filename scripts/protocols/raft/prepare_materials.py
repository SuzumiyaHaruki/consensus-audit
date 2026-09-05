#!/usr/bin/env python3
"""Import known English Raft sources using Poppler; no model or key access."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "orchestrator/src"))
from consensus_audit.artifacts import write_json
from consensus_audit.source_materials import require, split_text, validate_bundle

REVISION = "0c10ea1b53d73bf6d163bdde8e4141a1cbd8f36a"


def pdf_text(path: Path, *options: str) -> str:
    return subprocess.run(["pdftotext", *options, str(path), "-"],
                          check=True, capture_output=True, text=True).stdout


def build_bundle(cache: Path, *, protocol_root: Path = ROOT / "audit-specs/protocols/raft",
                 target_spec: Path | None = None,
                 dissertation_version: str = REVISION) -> dict:
    inventory = yaml.safe_load((protocol_root / "sources.yaml").read_text(encoding="utf-8"))
    target = yaml.safe_load(target_spec.read_text(encoding="utf-8")) if target_spec else {}
    require(not target_spec or target.get("protocol") == inventory["protocol"],
            "target source configuration must use the same protocol as this importer")
    sources = []
    blocks = []
    unknowns = list(inventory.get("unresolved", [])) + list(target.get("unresolved", []))
    if not target_spec:
        unknowns.append("No implementation scope or fault model was selected; supply an explicit target source configuration before a scoped audit.")
    for original in inventory["sources"] + target.get("sources", []):
        source = dict(original)
        sid = source["id"]
        if sid == "raft-extended":
            path = cache / "raft.pdf"
        elif sid == "dissertation":
            path = cache / "dissertation.pdf"
            source["version"] = dissertation_version + " (declared import version; human verification pending)"
        elif sid == "dissertation-errata":
            path = cache / "dissertation-README.md"
            source["version"] = dissertation_version + " (declared import version; human verification pending)"
        else:
            path = ROOT / source["local"]
        if not path.is_file():
            unknowns.append(f"Missing source {sid}: import {path.name} from {source['location']}; no text was fabricated.")
            continue
        source["local"] = str(path.resolve())
        sources.append(source)
        if path.suffix != ".pdf":
            text = path.read_text(encoding="utf-8")
            if sid == "dissertation-errata":
                # Retain author text, not build instructions or the whole README.
                marker = "## Updates and Errata"
                offset = text.index(marker) if marker in text else 0
                blocks.extend(split_text(sid, text[offset:], line_offset=text[:offset].count("\n")))
            else:
                blocks.extend(split_text(sid, text))
            continue
        if sid == "raft-extended":
            raw_text = pdf_text(path)
            (cache / "raft-reading-order.txt").write_text(raw_text, encoding="utf-8")
            (cache / "raft-layout.txt").write_text(pdf_text(path, "-layout"), encoding="utf-8")
            for page, text in enumerate(raw_text.split("\f"), 1):
                if page == 4:
                    # Fixed geometry for the cited 2014 paper. Each algorithm box
                    # stays together; side-by-side rules never become one line.
                    boxes = [("State", 70, 100, 236, 278),
                             ("AppendEntries RPC", 70, 378, 236, 296),
                             ("RequestVote RPC", 315, 100, 235, 178),
                             ("Rules for Servers", 315, 280, 235, 394),
                             ("Caption", 70, 674, 480, 38)]
                    for index, (title, x, y, w, h) in enumerate(boxes, 1):
                        body = pdf_text(path, "-f", "4", "-l", "4", "-layout",
                                        "-x", str(x), "-y", str(y), "-W", str(w), "-H", str(h)).replace("\f", "").strip()
                        blocks.append({"id": f"{sid}:figure2:{index}", "source_id": sid,
                            "section": f"Figure 2 / {title}", "page": 4, "source_start_line": 1,
                            "pdf_box": [x, y, w, h], "text": body, "review_status": "pending",
                            "conversion_note": "Poppler extraction of one algorithm box. Compare to PDF page 4; not human approved."})
                else:
                    blocks.extend(split_text(sid, text, page=page, section=f"Extended paper, page {page}"))
        elif sid == "dissertation":
            raw_text = pdf_text(path, "-layout")
            (cache / "dissertation-layout.txt").write_text(raw_text, encoding="utf-8")
            # online.pdf has 17 front-matter pages before printed page 1.
            # Preserve neighboring paragraphs and mark scope explicitly rather
            # than removing membership passages needed to interpret PreVote.
            ranges = [(27, 29, "Chapter 3, sections 3.8-3.10"),
                      (40, 42, "Chapter 4, section 4.2.3 and adjacent context"),
                      (48, 64, "Chapter 5, log compaction"),
                      (72, 75, "Chapter 6, sections 6.4-6.4.1"),
                      (136, 137, "Chapter 9, section 9.6 and adjacent context")]
            pages = raw_text.split("\f")
            for start, end, section in ranges:
                for printed_page in range(start, end + 1):
                    physical_page = printed_page + 17
                    if physical_page > len(pages):
                        unknowns.append(f"Dissertation page {physical_page} missing; verify PDF edition/offset.")
                        continue
                    for block in split_text(sid, pages[physical_page - 1], page=physical_page, section=section):
                        block["printed_page"] = printed_page
                        blocks.append(block)
            unknowns.append("Dissertation selection uses online.pdf front-matter offset 17; verify imported edition and selected printed-page labels.")
        else:
            unknowns.append(f"No PDF conversion is defined for source {sid}; supply model-readable text or inspect the relevant target documentation during location.")
    bundle = {"schema_version": "source-bundle/v1", "generation": "poppler_source_import",
              "protocol": inventory["protocol"], "implementation": target.get("implementation"),
              "sources": sources, "blocks": blocks, "unresolved": unknowns}
    validate_bundle(bundle)
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".cache/materials/raft")
    parser.add_argument("--output", type=Path, required=True, help="Explicit destination for this protocol/implementation material bundle")
    parser.add_argument("--target-spec", type=Path, help="Implementation source configuration; no implementation is selected by default")
    parser.add_argument("--download", action="store_true", help="Fetch missing public originals; default is offline import")
    parser.add_argument("--raft-pdf", type=Path, help="Import a local copy of the cited extended paper")
    parser.add_argument("--dissertation-pdf", type=Path, help="Import a local online.pdf edition")
    parser.add_argument("--dissertation-readme", type=Path)
    parser.add_argument("--dissertation-version", default=REVISION)
    args = parser.parse_args()
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    if not shutil.which("pdftotext"):
        parser.error("pdftotext is required (Poppler); install it before PDF import")
    for value, name in ((args.raft_pdf, "raft.pdf"), (args.dissertation_pdf, "dissertation.pdf"),
                        (args.dissertation_readme, "dissertation-README.md")):
        if value and value.resolve() != (args.cache_dir / name).resolve():
            shutil.copyfile(value, args.cache_dir / name)
    if args.download:
        base = f"https://raw.githubusercontent.com/ongardie/dissertation/{args.dissertation_version}/"
        for name, url in (("raft.pdf", "https://raft.github.io/raft.pdf"),
                          ("dissertation.pdf", base + "online.pdf"),
                          ("dissertation-README.md", base + "README.md"),
                          ("dissertation-LICENSE", base + "LICENSE")):
            destination = args.cache_dir / name
            if destination.exists():
                continue
            try:
                with urllib.request.urlopen(url, timeout=45) as response:
                    content = response.read()
                destination.write_bytes(content)
            except OSError as exc:
                print(f"Could not fetch {name}: {exc}. Import a local copy instead.", file=sys.stderr)
    bundle = build_bundle(args.cache_dir, target_spec=args.target_spec, dissertation_version=args.dissertation_version)
    destination = args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_json(destination, bundle)
    print(destination)
    print(f"Imported {len(bundle['sources'])} sources and {len(bundle['blocks'])} blocks; review is pending.")


if __name__ == "__main__":
    main()
