# SAS → Python Modernization MVP

An auditable, repeatable pipeline that turns a small clinical-trials SAS
codebase into Python — and proves the result against a row-for-row ground
truth. Comes with an **interactive Streamlit explorer** that walks through
every phase.

> The point isn't to translate SAS line by line. It's to parse SAS into a
> knowledge graph, regenerate specs/schemas/tests from the graph, then
> codegen from the regenerated specs — so the modernization is reviewable,
> not a black box. See [solution_design.md](solution_design.md) and
> [CLAUDE.md](CLAUDE.md) for the architecture.

---

## Quickstart — run the explorer app

### Prerequisites
- Python **3.10+**
- Windows, macOS, or Linux

### 1. Clone and enter the project
```bash
git clone https://github.com/Ib191/sas-modernization-mvp.git
cd sas-modernization-mvp
```

### 2. Create a virtual environment (recommended)
```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install streamlit pyvis networkx pandas duckdb pyarrow pytest markdown reportlab
```

### 4. Launch the app
```bash
python -m streamlit run build/ui/app.py
```

The app opens automatically at **http://localhost:8501**. If it doesn't,
open that URL in your browser.

**Stop the app:** `Ctrl-C` in the terminal where Streamlit is running.

### Re-running the pipeline live (optional)
All artifacts under `build/` are already committed, so the app works
out-of-the-box. If you want to re-run any phase live, the app has buttons
for it (Overview page → "Run all phases", or per-phase pages).

To regenerate everything from scratch on the command line:
```bash
python build/parser/run.py            # Phase 1: parse SAS
python build/parser/parse_docs.py     # Phase 2: parse docs
python build/graph/build_kg.py        # Phase 3: build knowledge graph
python build/regenerator/regenerate.py # Phase 4: regen specs/schemas/DAG/tests
python build/dag/run.py               # Phase 5: codegen + execute target Python
python -m pytest build/tests/         # Validate vs ground truth
```

---

## What the app shows

| #  | Page                            | Highlights                                                                                |
| -- | ------------------------------- | ----------------------------------------------------------------------------------------- |
| —  | **Overview** (`app.py`)         | Pipeline-at-a-glance, headline metrics, "Run all phases" button                            |
| 0  | 🎬 Live Demo Walkthrough        | Guided narrative for a live presentation                                                  |
| 1  | 📁 Codebase Inventory           | Every SAS file with line / DATA / PROC counts, source viewer, raw + ground-truth previews |
| 2  | 🔍 Phase 1 — Parser             | SAS source, post-macro-expansion, AST blocks, CFG, DFG, program-level DAG                  |
| 3  | 📚 Phase 2 — Docs                | Functional spec + data dictionary parsed into sections, business rules, open issues       |
| 4  | 🕸️ Phase 3 — Knowledge Graph    | **Interactive pyvis network** (drag, zoom, click). Lineage queries. Mermaid diagrams       |
| 5  | 🛠️ Phase 4 — Regenerated         | Functional specs (the only Phase 5 input), schemas, DAG, generated test stubs              |
| 6  | 🐍 Phase 5 — Codegen             | Spec ↔ generated Python side by side. Generated CSV ↔ ground truth with cell-level diff   |
| 7  | ✅ Validation                    | "Run pytest" button + live aggregate reconciliation                                       |
| 8  | ⚠️ Ambiguity register            | Cards for each ambiguity + full High-severity write-up                                     |
| 9  | 📑 Final SOLUTION.md            | The deliverable rendered in full with sidebar quick-jump                                  |
| A  | 🔧 Backend Walkthrough           | Code-level tour of the parser, KG builder, regenerator                                    |
| B  | 📥 Export PDF                    | Export the SOLUTION.md as a printable PDF                                                  |

---

## Project structure

```
.
├── CLAUDE.md                       <- operating instructions for Claude Code
├── solution_design.md              <- 5-phase pipeline architecture spec
├── README.md                       <- this file
├── generate_data_and_truth.py      <- regenerates input + ground-truth (seed=42)
├── sas_codebase/                   <- the SAS source
│   ├── config/   formats.sas, setup.sas
│   ├── macros/   util_macros.sas
│   ├── programs/ 01_clean_dm.sas … 05_summary_safety.sas
│   └── docs/     functional_spec.md, data_dictionary.md
├── input_data/                     <- synthetic raw inputs (CSV)
├── ground_truth/                   <- expected outputs (CSV) — the validation target
└── build/                          <- everything the pipeline produces
    ├── parser/                     <- Phase 1 SAS parser
    ├── ast/                        <- per-program AST + CFG + DFG
    ├── graph/                      <- Phase 3 knowledge graph (kg.sqlite + JSON)
    ├── regenerator/                <- Phase 4 spec/schema/DAG/test regenerator
    ├── specs/                      <- regenerated functional specs (Phase 5 input)
    ├── schemas/                    <- regenerated Python schemas
    ├── dag/                        <- execution DAG + runner
    ├── tests/                      <- regenerated test stubs
    ├── target/                     <- generated Python + CSV outputs (Phase 5)
    ├── reports/                    <- ambiguity_log, validation_report, coverage, phase summaries
    ├── ui/                         <- the Streamlit app
    └── SOLUTION.md                 <- the 9-section deliverable
```

---

## Domain

A clinical-trials SDTM → ADaM pipeline for a fictitious Phase 2 study
(`CTX-2024-001`). Standard pharma SAS workload — realistic complexity
without inventing a domain model.

Five programs with these dependencies:

```
01_clean_dm.sas      02_clean_ae.sas
       \                 /
        v               v
   03_derive_adsl.sas  (sets &TRT_START_DT global)
              |
              v
        04_derive_adae.sas (uses &TRT_START_DT)
              |
              v
       05_summary_safety.sas
```

Outputs: `DM_CLEAN`, `AE_CLEAN`, `ADSL`, `ADAE`, `AE_SUMMARY`, `AE_INCIDENCE`.

---

## Planted complexity (this is the demo's value)

The synthetic codebase exercises things that distinguish a real
modernization pipeline from a regex translator:

| #  | What's planted                                              | Where                                                                                                 | Why it matters                                                              |
| -- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| 1  | Cross-program global macro side effect                      | `03_derive_adsl.sas` sets `&TRT_START_DT`, `04_derive_adae.sas` reads it via `%is_treatment_emergent` | Needs the cross-program DFG; can't be caught by single-program analysis     |
| 2  | Implicit type cast in PROC SQL join                         | `03_derive_adsl.sas` joins `DM.SITEID` (char `'01'`) on `SITE_LOOKUP.SITE_ID` (num `1`)               | SAS coerces silently; PySpark/pandas don't. Must be flagged, not guessed    |
| 3  | Severity codes that fall through the if-then chain          | `02_clean_ae.sas` standardizes `MILD/MOD/SEV/1/2/3` but `GRADE 1` etc. become blank                   | Tests "missing vs null vs blank" handling; doc explicitly notes it (SP-184) |
| 4  | DM duplicate records resolved by sort+first                 | `01_clean_dm.sas`                                                                                     | BY-group semantics; FIRST./LAST. behavior must be preserved                 |
| 5  | LAST. on max-severity per subject                           | `02_clean_ae.sas`                                                                                     | Same                                                                        |
| 6  | Missing AGE derived from BRTHDTC                            | `01_clean_dm.sas`                                                                                     | Conditional derivation; depends on field-missingness check                  |
| 7  | Drop on missing date / missing term                         | `02_clean_ae.sas`                                                                                     | Implicit row-level filter, easy to lose in translation                      |
| 8  | Spec/code disagreement: "first dose" vs "randomization date" | functional_spec.md §6.3 vs implementation                                                             | Documentation NLP must catch the gap, not assume code matches doc           |
| 9  | Format catalog with `other` fallthrough                     | `formats.sas`                                                                                         | Tests that the graph captures the format catalog as a first-class entity    |
| 10 | Macro depending on global, with no parameter                | `%is_treatment_emergent` in `util_macros.sas`                                                         | The classic "looks pure but isn't" pattern                                  |

A successful run produces an `ambiguity_log.md` that names items 1, 2, 3,
and 8 explicitly. Items 4–7 are handled correctly (verified by
ground-truth diff). Item 9 appears as a node in the knowledge graph.

---

## Validation

`ground_truth/*.csv` are computed by `generate_data_and_truth.py`, which
mirrors the SAS logic in Python (same seed, same implicit-cast behavior,
deliberately). The generated Python under `build/target/` should diff
cleanly against these files.

Quick check:
```bash
python -m pytest build/tests/
```

Or, on Linux/macOS:
```bash
diff <(sort build/target/output/ae_summary.csv) <(sort ground_truth/ae_summary.csv)
```

The Validation page in the app runs pytest live and shows aggregate
reconciliation.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'streamlit'`** — Activate the venv
and re-run the `pip install` line.

**Port 8501 already in use** — Run with a different port:
`python -m streamlit run build/ui/app.py --server.port 8502`.

**Interactive graph (pyvis) not rendering on the Phase 3 page** — Some
browsers block local HTML embeds. Try Chrome/Edge, or hard-refresh
(`Ctrl-Shift-R`).

**Long file paths on Windows** — If `git clone` warns about path length,
enable long paths: `git config --system core.longpaths true`.

**PDF export fails** — `pip install markdown reportlab` (already in the
quickstart install line, but easy to miss).

---

## Caveats (honest disclosure)

- **Synthetic codebase.** No `%sysfunc`, no dynamic `&&var`, no PROC SQL
  passthrough, no runtime-generated SAS. Real client codebases will have
  these; the pipeline will need extensions documented in
  `build/reports/coverage.md`.
- **Small data.** 20 subjects, 58 AEs by design — the MVP is about
  approach validity, not scale.
- **Ground truth was produced by Python mirroring the SAS logic**, not a
  real SAS compiler. If you have a SAS environment and want to regenerate
  ground truth from real SAS, the input CSVs are the same.

---

## The deliverable

The single document a reviewer should read end-to-end:
**[`build/SOLUTION.md`](build/SOLUTION.md)** — 9 sections covering
executive summary, codebase inventory, dependency graph (Mermaid),
knowledge graph schema, ambiguity register, generated artifacts,
validation results, coverage, and recommendations for production
rollout.

You should be able to understand the modernization from that file alone,
without opening any SAS or generated code.
