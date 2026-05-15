"""Generate a comprehensive PDF takeaway document on demand."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import BUILD, PROJECT_ROOT, page_header, tutorial_intro

st.set_page_config(page_title="Export PDF", layout="wide")

page_header("📥", "Export PDF takeaway",
            "Generate a comprehensive PDF document that bundles the full "
            "SOLUTION.md, all reports, every regenerated spec, the original "
            "SAS source, and the generated Python — ready to share or print "
            "for your presentation.")

tutorial_intro(
    why=(
        "The web app is great for live demonstration. The PDF is for the "
        "**takeaway** — the document a reviewer can read on a plane, mark "
        "up, share with a regulator, or hand to the next analyst. It "
        "includes every report and every appendix in one self-contained file."
    ),
    what=(
        "- **Cover page** with the headline numbers\n"
        "- **§1 Solution Document** — the full SOLUTION.md\n"
        "- **Validation, Ambiguity Log, Coverage** reports\n"
        "- **Phase summaries** for all 5 phases\n"
        "- **Appendix A** — the 5 regenerated functional specs (Phase 5's "
        "only input)\n"
        "- **Appendix B** — the original SAS source (8 files)\n"
        "- **Appendix C** — the generated Python code (6 files)"
    ),
    insight=(
        "The PDF is generated **fresh from the same source files the web "
        "app reads** — so it's always consistent with what's on screen. "
        "Mermaid diagrams are referenced by caption (the live diagrams stay "
        "in the web app); everything else is rendered as native PDF text "
        "with proper tables, code blocks, and styled headings."
    ),
)

st.divider()
st.subheader("Build the PDF")
st.markdown(
    "Generation takes 2-5 seconds. The output is ~50 pages and ~130 KB — "
    "fits comfortably in an email attachment."
)

if st.button("📄 Generate PDF takeaway", type="primary"):
    with st.status("Building PDF…", expanded=True) as status:
        try:
            from pdf_export import build_pdf
            pdf_bytes = build_pdf()
            status.update(label=f"✅ PDF generated ({len(pdf_bytes):,} bytes)",
                            state="complete")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.session_state["pdf_bytes"] = pdf_bytes
            st.session_state["pdf_filename"] = f"sas_modernization_{ts}.pdf"
        except Exception as e:
            import traceback
            status.update(label=f"❌ Failed: {e}", state="error")
            st.code(traceback.format_exc(), language="text")

if "pdf_bytes" in st.session_state:
    st.success(
        f"PDF ready: **{st.session_state['pdf_filename']}** "
        f"({len(st.session_state['pdf_bytes']):,} bytes)"
    )
    st.download_button(
        label="⬇️ Download PDF",
        data=st.session_state["pdf_bytes"],
        file_name=st.session_state["pdf_filename"],
        mime="application/pdf",
        type="primary",
        use_container_width=False,
    )

st.divider()

# ---------------------------------------------------------------------------
# Inventory of source files that go into the PDF
# ---------------------------------------------------------------------------

st.subheader("What's in the PDF")

import pandas as pd

inventory = []

def _add(label: str, path: Path, kind: str) -> None:
    if path.exists():
        inventory.append({
            "section": label,
            "source file": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "kind": kind,
            "bytes": f"{path.stat().st_size:,}",
        })

_add("Cover page", PROJECT_ROOT, "synthesized")
_add("§1 Solution document", BUILD / "SOLUTION.md", "markdown")
_add("Validation report", BUILD / "reports" / "validation_report.md", "markdown")
_add("Ambiguity log (full)", BUILD / "reports" / "ambiguity_log.md", "markdown")
_add("Coverage report", BUILD / "reports" / "coverage.md", "markdown")
for n in (1, 2, 3, 4, 5):
    _add(f"Phase {n} summary",
         BUILD / "reports" / f"phase{n}_summary.md", "markdown")
for spec in sorted((BUILD / "specs").glob("*.md")):
    _add(f"Appendix A · {spec.stem}", spec, "markdown spec")
for sas in [
    PROJECT_ROOT / "sas_codebase" / "config" / "setup.sas",
    PROJECT_ROOT / "sas_codebase" / "config" / "formats.sas",
    PROJECT_ROOT / "sas_codebase" / "macros" / "util_macros.sas",
    *sorted((PROJECT_ROOT / "sas_codebase" / "programs").glob("*.sas")),
]:
    _add(f"Appendix B · {sas.name}", sas, "SAS source")
for py in sorted((BUILD / "target").glob("*.py")):
    _add(f"Appendix C · {py.name}", py, "Python")

st.dataframe(pd.DataFrame(inventory), hide_index=True, width="stretch")
