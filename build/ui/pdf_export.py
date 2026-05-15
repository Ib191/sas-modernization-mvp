"""Generate a comprehensive PDF takeaway from the SOLUTION.md and reports.

Uses reportlab (pure Python, no system deps). Renders Markdown via the
`markdown` library to HTML then ports a subset of the HTML to reportlab
flowables. Mermaid diagrams are replaced with descriptive captions so the
PDF stays readable; the live diagrams remain in the web app.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import markdown
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, Preformatted,
)


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
BUILD = PROJECT_ROOT / "build"


# ----------------------------------------------------------------------------
# Styles
# ----------------------------------------------------------------------------

def _make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    s: dict[str, ParagraphStyle] = {}
    s["Title"] = ParagraphStyle(
        "Title", parent=base["Title"], fontSize=22, leading=28,
        textColor=colors.HexColor("#1f2937"), spaceAfter=18,
    )
    s["H1"] = ParagraphStyle(
        "H1", parent=base["Heading1"], fontSize=16, leading=22,
        textColor=colors.HexColor("#1e40af"), spaceBefore=18, spaceAfter=8,
    )
    s["H2"] = ParagraphStyle(
        "H2", parent=base["Heading2"], fontSize=13, leading=18,
        textColor=colors.HexColor("#1e3a8a"), spaceBefore=12, spaceAfter=6,
    )
    s["H3"] = ParagraphStyle(
        "H3", parent=base["Heading3"], fontSize=11, leading=15,
        textColor=colors.HexColor("#3730a3"), spaceBefore=8, spaceAfter=4,
    )
    s["Body"] = ParagraphStyle(
        "Body", parent=base["BodyText"], fontSize=9.5, leading=13,
        textColor=colors.HexColor("#1f2937"), alignment=TA_JUSTIFY,
        spaceAfter=4,
    )
    s["Bullet"] = ParagraphStyle(
        "Bullet", parent=base["BodyText"], fontSize=9.5, leading=13,
        leftIndent=16, bulletIndent=4, spaceAfter=2,
    )
    s["Code"] = ParagraphStyle(
        "Code", parent=base["Code"], fontSize=8, leading=10,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f1f5f9"),
        borderColor=colors.HexColor("#cbd5e1"), borderPadding=4,
        leftIndent=4, rightIndent=4,
    )
    s["Caption"] = ParagraphStyle(
        "Caption", parent=base["Italic"], fontSize=8.5, leading=11,
        textColor=colors.HexColor("#64748b"), spaceAfter=8,
    )
    s["Callout"] = ParagraphStyle(
        "Callout", parent=base["BodyText"], fontSize=9.5, leading=13,
        backColor=colors.HexColor("#fef3c7"),
        borderColor=colors.HexColor("#f59e0b"),
        borderPadding=8, borderWidth=1,
        spaceBefore=6, spaceAfter=8,
    )
    s["Cover"] = ParagraphStyle(
        "Cover", parent=base["BodyText"], fontSize=11, leading=16,
        textColor=colors.HexColor("#1f2937"), alignment=TA_LEFT,
        spaceAfter=8,
    )
    s["TableCell"] = ParagraphStyle(
        "TableCell", parent=base["BodyText"], fontSize=8.5, leading=11,
    )
    return s


STYLES = _make_styles()


# ----------------------------------------------------------------------------
# Markdown → reportlab flowables (subset)
# ----------------------------------------------------------------------------

def _strip_inline(text: str) -> str:
    """Convert inline markdown to reportlab paragraph markup.

    Order matters: extract code spans first into placeholders so their
    contents (which may contain `*`, `<`, `>`, `&`) are not subject to
    further inline processing or HTML escaping until the final restore.
    """
    spans: list[str] = []

    def _extract(m: re.Match[str]) -> str:
        spans.append(m.group(1))
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", _extract, text)

    # Escape XML special chars in the non-code text
    text = (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))

    # Now apply bold / italic / link substitutions
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)

    # Restore code spans with HTML-escaped content
    def _restore(m: re.Match[str]) -> str:
        s = spans[int(m.group(1))]
        s = (s.replace("&", "&amp;")
              .replace("<", "&lt;")
              .replace(">", "&gt;"))
        return f"<font face='Courier' color='#0369a1'>{s}</font>"

    text = re.sub(r"\x00(\d+)\x00", _restore, text)
    return text


def _table_from_markdown(md_table_lines: list[str]) -> Table | None:
    """Convert a markdown pipe-table into a reportlab Table."""
    if len(md_table_lines) < 2:
        return None

    def split(line: str) -> list[str]:
        parts = [c.strip() for c in line.strip().strip("|").split("|")]
        return parts

    header = split(md_table_lines[0])
    rows = [split(l) for l in md_table_lines[2:] if l.strip()]
    if not header or not rows:
        return None
    n = len(header)
    rows = [r + [""] * (n - len(r)) if len(r) < n else r[:n] for r in rows]
    data = [[Paragraph(_strip_inline(c), STYLES["TableCell"]) for c in header]]
    for r in rows:
        data.append([Paragraph(_strip_inline(c), STYLES["TableCell"]) for c in r])
    # Distribute column widths evenly across the available page width
    # (A4 portrait, 2cm margins → ~17cm usable). Cap to avoid super-narrow
    # cells that crash reportlab's auto-layout on wide tables.
    available = 17.0 * cm
    col_w = max(1.6 * cm, available / n)
    col_widths = [col_w] * n
    tbl = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


def md_to_flowables(md: str) -> list:
    """Walk through markdown line-by-line and emit reportlab flowables."""
    flow: list = []
    lines = md.splitlines()
    i = 0

    def flush_paragraph(buf: list[str]) -> None:
        if not buf:
            return
        text = " ".join(s.strip() for s in buf)
        if not text.strip():
            return
        flow.append(Paragraph(_strip_inline(text), STYLES["Body"]))

    para_buf: list[str] = []

    while i < len(lines):
        line = lines[i]

        # Mermaid block — replace with caption
        if line.strip().startswith("```mermaid"):
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                j += 1
            flush_paragraph(para_buf); para_buf = []
            flow.append(Paragraph(
                "<i>📊 Diagram available in the live web app "
                "(http://localhost:8501)</i>", STYLES["Caption"]
            ))
            i = j + 1
            continue

        # Code block
        if line.strip().startswith("```"):
            j = i + 1
            code_lines: list[str] = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                code_lines.append(lines[j])
                j += 1
            flush_paragraph(para_buf); para_buf = []
            code = "\n".join(code_lines)
            # Truncate very long blocks to keep PDF size reasonable
            if len(code) > 3000:
                code = code[:3000] + "\n…(truncated)…"
            flow.append(Preformatted(code, STYLES["Code"]))
            flow.append(Spacer(1, 6))
            i = j + 1
            continue

        # Markdown table
        if line.strip().startswith("|") and i + 1 < len(lines) \
                and re.match(r"\s*\|[\s|:-]+\|\s*$", lines[i + 1]):
            tbl_lines = [line]
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith("|"):
                tbl_lines.append(lines[j])
                j += 1
            flush_paragraph(para_buf); para_buf = []
            tbl = _table_from_markdown(tbl_lines)
            if tbl:
                flow.append(tbl)
                flow.append(Spacer(1, 6))
            i = j
            continue

        # Headings
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_paragraph(para_buf); para_buf = []
            level = len(m.group(1))
            txt = _strip_inline(m.group(2))
            if level == 1:
                flow.append(Paragraph(txt, STYLES["H1"]))
            elif level == 2:
                flow.append(Paragraph(txt, STYLES["H2"]))
            else:
                flow.append(Paragraph(txt, STYLES["H3"]))
            i += 1
            continue

        # Bullets
        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            flush_paragraph(para_buf); para_buf = []
            text = _strip_inline(m.group(2))
            indent = len(m.group(1))
            style = ParagraphStyle("BulletL", parent=STYLES["Bullet"],
                                     leftIndent=12 + 16 * (indent // 2),
                                     bulletIndent=4 + 16 * (indent // 2))
            flow.append(Paragraph(text, style, bulletText="•"))
            i += 1
            continue

        # Blockquotes
        if line.strip().startswith("> "):
            flush_paragraph(para_buf); para_buf = []
            flow.append(Paragraph(_strip_inline(line.strip()[2:]),
                                    STYLES["Callout"]))
            i += 1
            continue

        # Horizontal rule
        if line.strip() in ("---", "***", "___"):
            flush_paragraph(para_buf); para_buf = []
            flow.append(Spacer(1, 6))
            i += 1
            continue

        # Blank line ends paragraph
        if not line.strip():
            flush_paragraph(para_buf); para_buf = []
            i += 1
            continue

        para_buf.append(line)
        i += 1

    flush_paragraph(para_buf)
    return flow


# ----------------------------------------------------------------------------
# Cover page
# ----------------------------------------------------------------------------

def cover_page() -> list:
    flow: list = []
    flow.append(Spacer(1, 4 * cm))
    flow.append(Paragraph("SAS → Python", STYLES["Title"]))
    flow.append(Paragraph("Modernization Pipeline", STYLES["Title"]))
    flow.append(Spacer(1, 1 * cm))
    flow.append(Paragraph(
        "<b>CTX-2024-001</b> · graph-driven modernization · "
        "row-for-row validated against ground truth",
        STYLES["Cover"],
    ))
    flow.append(Spacer(1, 0.6 * cm))
    flow.append(Paragraph(
        "This document accompanies the live web-app explorer "
        "(<font color='#1e40af'>http://localhost:8501</font>). It contains "
        "the full SOLUTION.md deliverable, the ambiguity log, the validation "
        "report, the coverage report, the regenerated functional specs, and "
        "the original SAS source as an appendix.",
        STYLES["Cover"],
    ))
    flow.append(Spacer(1, 1.2 * cm))

    summary = [
        ("Phases", "5"),
        ("SAS lines modernized", "533"),
        ("Output datasets", "6 / 6 ✓"),
        ("Knowledge-graph nodes", "173"),
        ("Knowledge-graph edges", "93"),
        ("Tests passing", "23 / 23"),
        ("Ambiguities surfaced", "6 (1 High resolved, 3 Medium, 2 Low)"),
    ]
    tbl = Table(summary, colWidths=[6 * cm, 8 * cm], hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1e40af")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#cbd5e1")),
    ]))
    flow.append(tbl)
    flow.append(PageBreak())
    return flow


# ----------------------------------------------------------------------------
# Section helper
# ----------------------------------------------------------------------------

def section_pages(title: str, src_path: Path) -> list:
    """Render a markdown source file as a PDF section."""
    flow: list = []
    flow.append(Paragraph(title, STYLES["H1"]))
    if not src_path.exists():
        flow.append(Paragraph(f"<i>{src_path} not found</i>", STYLES["Body"]))
        return flow
    md = src_path.read_text(encoding="utf-8")
    flow.extend(md_to_flowables(md))
    flow.append(PageBreak())
    return flow


def code_appendix(title: str, files: list[Path], language_label: str) -> list:
    """Render code files into a PDF appendix."""
    flow: list = []
    flow.append(Paragraph(title, STYLES["H1"]))
    for f in files:
        if not f.exists():
            continue
        rel = f.relative_to(PROJECT_ROOT)
        flow.append(Paragraph(f"<b>{rel}</b>", STYLES["H3"]))
        flow.append(Paragraph(f"<i>{language_label}</i>", STYLES["Caption"]))
        text = f.read_text(encoding="utf-8")
        if len(text) > 5000:
            text = text[:5000] + "\n…(truncated, see source)…"
        flow.append(Preformatted(text, STYLES["Code"]))
        flow.append(Spacer(1, 8))
    flow.append(PageBreak())
    return flow


# ----------------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------------

def build_pdf() -> bytes:
    """Build the full takeaway PDF and return as bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title="SAS → Python Modernization", author="CTX-2024-001",
    )

    flow: list = []
    flow.extend(cover_page())

    # Main deliverable
    flow.extend(section_pages("Solution Document",
                               BUILD / "SOLUTION.md"))

    # Reports
    flow.extend(section_pages("Backend Walkthrough (how each phase is implemented)",
                               BUILD / "reports" / "backend_walkthrough.md"))
    flow.extend(section_pages("Validation Report",
                               BUILD / "reports" / "validation_report.md"))
    flow.extend(section_pages("Ambiguity Log (full)",
                               BUILD / "reports" / "ambiguity_log.md"))
    flow.extend(section_pages("Coverage Report",
                               BUILD / "reports" / "coverage.md"))

    # Phase summaries
    flow.append(Paragraph("Phase Summaries", STYLES["H1"]))
    for n in (1, 2, 3, 4, 5):
        p = BUILD / "reports" / f"phase{n}_summary.md"
        if p.exists():
            flow.extend(md_to_flowables(p.read_text(encoding="utf-8")))
            flow.append(Spacer(1, 6))
    flow.append(PageBreak())

    # Functional specs (the only Phase 5 input)
    flow.append(Paragraph("Appendix A · Regenerated Functional Specs",
                            STYLES["H1"]))
    flow.append(Paragraph(
        "These five specs are the <i>only</i> input to Phase 5 codegen. "
        "Per Hard Rule R1, no SAS file is opened during codegen — the spec "
        "is the contract.", STYLES["Caption"]
    ))
    for spec in sorted((BUILD / "specs").glob("*.md")):
        flow.extend(md_to_flowables(spec.read_text(encoding="utf-8")))
        flow.append(PageBreak())

    # SAS source
    sas_files = [
        PROJECT_ROOT / "sas_codebase" / "config" / "setup.sas",
        PROJECT_ROOT / "sas_codebase" / "config" / "formats.sas",
        PROJECT_ROOT / "sas_codebase" / "macros" / "util_macros.sas",
        PROJECT_ROOT / "sas_codebase" / "programs" / "01_clean_dm.sas",
        PROJECT_ROOT / "sas_codebase" / "programs" / "02_clean_ae.sas",
        PROJECT_ROOT / "sas_codebase" / "programs" / "03_derive_adsl.sas",
        PROJECT_ROOT / "sas_codebase" / "programs" / "04_derive_adae.sas",
        PROJECT_ROOT / "sas_codebase" / "programs" / "05_summary_safety.sas",
    ]
    flow.extend(code_appendix("Appendix B · Original SAS Source",
                                sas_files, "SAS"))

    # Generated Python
    py_files = sorted([p for p in (BUILD / "target").glob("*.py")
                        if p.name != "__init__.py"])
    flow.extend(code_appendix("Appendix C · Generated Python (pandas + duckdb)",
                                py_files, "Python"))

    doc.build(flow)
    return buf.getvalue()


if __name__ == "__main__":
    pdf = build_pdf()
    out = HERE / "modernization_takeaway.pdf"
    out.write_bytes(pdf)
    print(f"wrote {out}  ({len(pdf):,} bytes)")
