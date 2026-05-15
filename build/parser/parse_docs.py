"""Phase 2: parse the markdown documentation into structured entities.

Input  : sas_codebase/docs/functional_spec.md, sas_codebase/docs/data_dictionary.md
Output : build/graph/doc_entities.json

Entities extracted:
- Section          — every `#…##…###` header forms a section node
- DatasetMention   — tokens like `RAW.DM`, `ADAM.ADSL`, `DM_CLEAN`
- ColumnMention    — tokens like `USUBJID`, `RFSTDT` (heuristic: ALL-CAPS_IDENT
                     inside backticks within a known dataset section)
- BusinessRule     — bullet items inside Derivation Rules / Known Issues
- OpenIssue        — every entry under "Known issues / open items" plus any
                     bullet that contains a tracker reference (SP-184, SP-227, …)

Each entity records `source_file`, `source_section`, `source_line`.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent

DOCS = [
    "sas_codebase/docs/functional_spec.md",
    "sas_codebase/docs/data_dictionary.md",
]

# Datasets we know about from Phase 1
KNOWN_DATASETS = {
    "raw.dm", "raw.ae", "raw.site_lookup",
    "adam.dm_clean", "adam.ae_clean", "adam.adsl", "adam.adae",
    "adam.ae_summary", "adam.ae_incidence",
    # also unprefixed names used in headers like "ADAM.DM_CLEAN (output)"
    "dm_clean", "ae_clean", "adsl", "adae", "ae_summary", "ae_incidence",
    "dm", "ae", "site_lookup",
}

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*)$")
_TICKER_RE = re.compile(r"\b(SP-\d{2,4})\b")
_DATASET_REF_RE = re.compile(
    r"\b((?:RAW|ADAM|TGT|WORK)\.[A-Z][A-Z0-9_]+|"
    r"DM_CLEAN|AE_CLEAN|ADSL|ADAE|AE_SUMMARY|AE_INCIDENCE|"
    r"SITE_LOOKUP)\b"
)
_COLUMN_TICK_RE = re.compile(r"`([A-Z][A-Z0-9_]+)`")


def parse_doc(path: Path) -> dict:
    """Parse a single markdown doc. Returns:
    {
      file: str,
      sections: [{title, level, line_start, body_lines, datasets, columns,
                  bullets, open_issues}],
    }
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    sections: list[dict] = []
    current: dict | None = None

    for i, line in enumerate(lines, start=1):
        m = _HEADER_RE.match(line)
        if m:
            if current is not None:
                sections.append(current)
            current = {
                "title": m.group(2),
                "level": len(m.group(1)),
                "line_start": i,
                "body_lines": [],
                "datasets": set(),
                "columns": set(),
                "bullets": [],
                "open_issues": [],
            }
            continue
        if current is None:
            continue
        current["body_lines"].append((i, line))

        # bullets inside this section
        b = _BULLET_RE.match(line)
        if b:
            txt = b.group(1).strip()
            current["bullets"].append({"line": i, "text": txt})
            tickers = _TICKER_RE.findall(txt)
            if tickers or "deferred" in txt.lower() or "open" in txt.lower():
                current["open_issues"].append({
                    "line": i, "text": txt, "tickers": tickers,
                })

        for ds_match in _DATASET_REF_RE.finditer(line):
            current["datasets"].add(ds_match.group(1).lower())
        for col_match in _COLUMN_TICK_RE.finditer(line):
            current["columns"].add(col_match.group(1).upper())

    if current is not None:
        sections.append(current)

    # Convert sets to sorted lists for JSON
    for s in sections:
        s["datasets"] = sorted(s["datasets"])
        s["columns"] = sorted(s["columns"])
        # Drop heavy body for the JSON dump (keep first 2 lines as preview)
        s["body_preview"] = " ".join(l for _, l in s["body_lines"][:4])[:300]
        del s["body_lines"]

    return {"file": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "sections": sections}


def extract_business_rules(doc: dict) -> list[dict]:
    """Bullets inside any section whose title contains 'derivation', 'rules',
    'cleaning', 'flag', or numbered §4.x sections."""
    out: list[dict] = []
    for s in doc["sections"]:
        title_l = s["title"].lower()
        if not any(k in title_l for k in ("derivation", "rules", "cleaning",
                                          "flag", "summaries", "deriv")):
            continue
        for b in s["bullets"]:
            out.append({
                "source_file": doc["file"],
                "source_section": s["title"],
                "source_line": b["line"],
                "text": b["text"],
                "datasets": s["datasets"],
                "columns": s["columns"],
            })
    return out


def extract_open_issues(doc: dict) -> list[dict]:
    """Every bullet under 'Known issues / open items', plus any bullet
    elsewhere that names an SP-### tracker."""
    out: list[dict] = []
    seen: set[str] = set()
    for s in doc["sections"]:
        title_l = s["title"].lower()
        in_known_section = (
            "known issues" in title_l
            or "open" in title_l
            or "issues" in title_l
        )
        for b in s["bullets"]:
            tickers = _TICKER_RE.findall(b["text"])
            if not (in_known_section or tickers):
                continue
            key = (s["title"], b["line"])
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "id": tickers[0] if tickers else f"{Path(doc['file']).stem}-L{b['line']}",
                "tickers": tickers,
                "source_file": doc["file"],
                "source_section": s["title"],
                "source_line": b["line"],
                "text": b["text"],
                "datasets": s["datasets"],
                "columns": s["columns"],
            })
        # also: section-bodies that look like issue write-ups (### 6.x)
        # Skip parent "§6 Known issues" itself (no body, just a chapter head)
        if re.match(r"^6\.\d", title_l) and s["body_preview"].strip():
            body_tickers = _TICKER_RE.findall(s["body_preview"])
            out.append({
                "id": (body_tickers[0] if body_tickers
                       else f"{Path(doc['file']).stem}-§{s['title'].split()[0]}"),
                "tickers": body_tickers,
                "source_file": doc["file"],
                "source_section": s["title"],
                "source_line": s["line_start"],
                "text": s["body_preview"],
                "datasets": s["datasets"],
                "columns": s["columns"],
            })
    return out


def main() -> None:
    out_dir = PROJECT_ROOT / "build" / "graph"
    out_dir.mkdir(parents=True, exist_ok=True)

    docs = []
    business_rules: list[dict] = []
    open_issues: list[dict] = []

    for rel in DOCS:
        path = PROJECT_ROOT / rel
        doc = parse_doc(path)
        docs.append(doc)
        business_rules.extend(extract_business_rules(doc))
        open_issues.extend(extract_open_issues(doc))

    # Aggregate datasets / columns mentioned per file
    bundle = {
        "documents": docs,
        "business_rules": business_rules,
        "open_issues": open_issues,
    }

    out_path = out_dir / "doc_entities.json"
    out_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    print(f"phase 2 outputs written to {out_path}")
    print(f"  sections      : {sum(len(d['sections']) for d in docs)}")
    print(f"  business rules: {len(business_rules)}")
    print(f"  open issues   : {len(open_issues)}")


if __name__ == "__main__":
    main()
