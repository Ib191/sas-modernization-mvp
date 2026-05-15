# SAS Modernization Explorer (Streamlit UI)

An interactive walkthrough of every phase of the modernization pipeline.

## Run

```powershell
python -m streamlit run build/ui/app.py
```

Then open http://localhost:8501.

## Pages

| #   | Page                             | What you'll see                                                                                              |
| --- | -------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| —   | **Overview** (`app.py`)          | Pipeline-at-a-glance Mermaid, headline metrics, **Run all phases** button (executes the full pipeline live)  |
| 1   | 📁 Codebase Inventory            | Every SAS file with line counts and DATA/PROC counts, source viewer, raw input + ground-truth previews        |
| 2   | 🔍 Phase 1 — Parser              | Per-program: original SAS, post-macro-expansion, AST blocks, CFG, DFG. Macro table. Program-level DAG.       |
| 3   | 📚 Phase 2 — Docs                 | Functional spec + data dictionary parsed into sections, business rules, open issues                          |
| 4   | 🕸️ Phase 3 — Knowledge Graph       | **Interactive pyvis network** (drag, zoom, click). Filter by node kind. Lineage queries. Mermaid diagrams.  |
| 5   | 🛠️ Phase 4 — Regenerated          | Functional specs (the only Phase 5 input), schemas, DAG, generated test stubs                              |
| 6   | 🐍 Phase 5 — Codegen              | Spec ↔ generated Python side by side. Generated CSV ↔ ground truth side by side with cell-level diff.     |
| 7   | ✅ Validation                     | **Run pytest** button + live aggregate reconciliation                                                       |
| 8   | ⚠️ Ambiguity register             | Cards for each ambiguity + full High-severity write-up                                                      |
| 9   | 📑 Final SOLUTION.md             | The deliverable rendered in full with sidebar quick-jump                                                    |

## Stop

Ctrl-C in the terminal where Streamlit is running.
