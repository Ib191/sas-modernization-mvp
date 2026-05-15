"""Backend walkthrough — show the actual code and explain what each phase does."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import BUILD, PROJECT_ROOT, read_text, page_header

st.set_page_config(page_title="Backend Walkthrough", layout="wide")

page_header("🔧", "Backend walkthrough",
            "How every phase is implemented in code — file paths, line "
            "numbers, key algorithms — so you can show the actual "
            "implementation during the presentation.")

# ----------------------------------------------------------------------------
# Sidebar quick-jump
# ----------------------------------------------------------------------------

PHASES = [
    ("📁 0 · File layout (10,000-foot)", "0"),
    ("🔍 1 · Phase 1 — Parsing SAS", "1"),
    ("📚 2 · Phase 2 — Parsing docs", "2"),
    ("🕸️ 3 · Phase 3 — Knowledge graph", "3"),
    ("🛠️ 4 · Phase 4 — Regenerator", "4"),
    ("🐍 5 · Phase 5 — Codegen", "5"),
    ("✅ 6 · Validation", "6"),
    ("🔒 7 · Cross-cutting concerns", "7"),
    ("❓ 8 · FAQ for the presentation", "8"),
    ("🎬 9 · Live-demo cheat sheet", "9"),
]
section = st.sidebar.radio("Jump to section", [p[0] for p in PHASES],
                              index=0)
section_idx = [p[0] for p in PHASES].index(section)

st.sidebar.divider()
st.sidebar.markdown("**📄 Markdown source:**")
st.sidebar.code("build/reports/backend_walkthrough.md", language="text")

# ----------------------------------------------------------------------------
# Render the walkthrough — split by ## sections
# ----------------------------------------------------------------------------

walkthrough = read_text(BUILD / "reports" / "backend_walkthrough.md")
if not walkthrough:
    st.error("`build/reports/backend_walkthrough.md` not found")
    st.stop()

# Split on '## N · ' top-level section headers
import re
sections = re.split(r"^## ", walkthrough, flags=re.MULTILINE)
intro = sections[0]
section_bodies = ["## " + s for s in sections[1:]]

st.markdown(intro)

# Show only the selected section to keep the page focused
if section_idx < len(section_bodies):
    st.markdown(section_bodies[section_idx])
else:
    st.warning(f"Section {section_idx} not found")

# ----------------------------------------------------------------------------
# Code preview panel — quick access to actual files
# ----------------------------------------------------------------------------

st.divider()
st.subheader("🗂️ Open the actual code")

CODE_FILES = {
    "Phase 1 — sas_parser.py (parser core)":
        "build/parser/sas_parser.py",
    "Phase 1 — flow_graphs.py (CFG/DFG)":
        "build/parser/flow_graphs.py",
    "Phase 1 — run.py (driver)":
        "build/parser/run.py",
    "Phase 2 — parse_docs.py (doc parser)":
        "build/parser/parse_docs.py",
    "Phase 3 — build_kg.py (graph builder)":
        "build/graph/build_kg.py",
    "Phase 3 — query.py (CLI)":
        "build/graph/query.py",
    "Phase 4 — regenerate.py (regenerator)":
        "build/regenerator/regenerate.py",
    "Phase 5 — common.py (shared utilities)":
        "build/target/common.py",
    "Phase 5 — 01_clean_dm.py":
        "build/target/01_clean_dm.py",
    "Phase 5 — 02_clean_ae.py":
        "build/target/02_clean_ae.py",
    "Phase 5 — 03_derive_adsl.py":
        "build/target/03_derive_adsl.py",
    "Phase 5 — 04_derive_adae.py":
        "build/target/04_derive_adae.py",
    "Phase 5 — 05_summary_safety.py":
        "build/target/05_summary_safety.py",
    "Phase 5 — dag/run.py (runner)":
        "build/dag/run.py",
    "Validation — test_aggregates.py":
        "build/tests/test_aggregates.py",
    "Validation — test_adam_adae.py (one of the auto-generated)":
        "build/tests/test_adam_adae.py",
}

choice = st.selectbox("File", list(CODE_FILES.keys()))
path = CODE_FILES[choice]
src = read_text(path)
total = len(src.splitlines())
st.caption(f"`{path}` · {total} lines")
st.code(src, language="python", line_numbers=True)
