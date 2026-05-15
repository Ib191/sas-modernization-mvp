"""Shared utilities for the modernization-explorer Streamlit app."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import streamlit as st

UI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = UI_DIR.parent.parent
BUILD = PROJECT_ROOT / "build"


@st.cache_data(show_spinner=False)
def load_json(path: str | Path) -> dict | list:
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return json.loads(p.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def read_text(path: str | Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def render_mermaid(code: str, height: int = 600) -> None:
    """Render Mermaid diagram inside the Streamlit app via the Mermaid CDN.

    Uses securityLevel: 'loose' so `<br/>` and other HTML-in-labels render
    instead of being silently stripped by the default 'strict' setting.
    """
    import streamlit.components.v1 as components
    html = f"""
<!DOCTYPE html>
<html>
<head>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  body {{ background: #0e1117; color: #fafafa; margin: 0; padding: 8px; }}
  .mermaid {{ background: #0e1117; }}
</style>
</head>
<body>
<pre class="mermaid">
{code}
</pre>
<script>
  mermaid.initialize({{
    startOnLoad: true,
    theme: 'dark',
    securityLevel: 'loose',
    flowchart: {{ htmlLabels: true, curve: 'basis' }},
    themeVariables: {{ background: '#0e1117', primaryColor: '#1f2937',
      primaryTextColor: '#fafafa', primaryBorderColor: '#3b82f6',
      lineColor: '#9ca3af', tertiaryColor: '#1f2937' }}
  }});
</script>
</body>
</html>
"""
    components.html(html, height=height, scrolling=True)


def run_pipeline_step(name: str, cmd: list[str]) -> tuple[bool, str]:
    """Run a pipeline subprocess; return (ok, combined_stdout_stderr)."""
    res = subprocess.run(
        cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True,
    )
    out = (res.stdout or "") + (res.stderr or "")
    return res.returncode == 0, out


def page_header(num: str, title: str, subtitle: str = "") -> None:
    st.markdown(f"# {num} · {title}")
    if subtitle:
        st.caption(subtitle)


def info_box(title: str, body: str) -> None:
    st.info(f"**{title}**\n\n{body}")


def tutorial_intro(*, why: str, what: str, insight: str = "",
                    speaker: str = "") -> None:
    """Standard educational header for each phase page.

    - **why**: why this phase exists in the pipeline
    - **what**: what's on this page (orient the viewer)
    - **insight**: the key technical insight that makes this phase non-trivial
    - **speaker**: presenter notes — what to say in a live demo
    """
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 🎯 Why this phase exists")
            st.markdown(why)
        with c2:
            st.markdown("##### 👀 What's on this page")
            st.markdown(what)
        if insight:
            st.markdown("##### 💡 Key insight")
            st.markdown(insight)
        if speaker:
            with st.expander("🗣️ Speaker notes (for live demo)", expanded=False):
                st.markdown(speaker)


def demo_prompt(text: str) -> None:
    """A 'do this in your demo' callout — yellow."""
    st.warning(f"🎬 **Demo prompt** — {text}")


PHASE_COLORS = {
    1: "#3b82f6",  # blue
    2: "#8b5cf6",  # purple
    3: "#22c55e",  # green
    4: "#f59e0b",  # amber
    5: "#ef4444",  # red
}
