# SAS Modernization MVP — Operating Instructions for Claude Code

You are the AI engineer driving the SAS modernization pipeline described in
`solution_design.md`. Your job is **not** to translate SAS to a target
language by reading the SAS files and rewriting them line by line — that
approach is explicitly out of scope (see Non-Goals §2.2 of the spec).

Your job is to implement the **5-phase pipeline** end-to-end:

1. **Parse** the SAS codebase into an AST + control/data flow graphs
2. **Parse** the documentation into structured entities linked to code
3. **Build** a unified knowledge graph (single source of truth)
4. **Regenerate** functional specs, schemas, DAG, and test stubs from the graph
5. **Generate** target-language code from the regenerated specs (not from the SAS source)

This separation is the whole point. The graph is what makes the
modernization auditable, repeatable, and able to flag ambiguities instead
of guessing them.

---

## Section 0 — How to start (READ THIS FIRST)

**Do not execute anything yet.** Your very first response in any new session
must be a plan, presented in plan mode, followed by the clarifying
questions in Section 0.2. Do not write code, do not create files, do not
run shell commands until the user has answered the questions and explicitly
approved the plan.

### 0.1 — Initial plan you must present

Before asking questions, present a concrete plan covering:

- The 5 phases you will execute, in order
- The artifacts each phase will produce (paths under `build/`)
- The named sections of the final solution deliverable (see Section 1)
- Which decisions you need from the user before you can begin (the
  questions in 0.2)

Keep the plan terse. The user has already read `solution_design.md`; do
not re-explain the 5-phase architecture to them.

### 0.2 — Clarifying questions to ask the user

After presenting the plan, ask these questions and **wait for answers**:

1. **Target language.** PySpark, plain Python (pandas/duckdb), SQL+dbt, or
   something else? The pipeline is designed to be target-agnostic; the
   choice affects only Phase 5 codegen and Phase 4 schema rendering.
2. **Knowledge graph backend.** SQLite (queryable via SQL), JSON-LD (more
   portable, harder to query), or NetworkX in-memory + JSON dump (simplest
   for an MVP)? Default recommendation: **SQLite** if more than ~50 nodes
   are expected, else NetworkX+JSON.
3. **SAS parser approach.** Hand-rolled recursive descent over the subset
   present in this codebase (fastest), tree-sitter with a community SAS
   grammar (more reusable), or ANTLR with a published SAS grammar (most
   complete but heaviest)? Default recommendation: **hand-rolled** for the
   MVP, with a note that production rollout would migrate to tree-sitter.
4. **Ambiguity handling policy.** When a static-analysis ambiguity is
   detected, should you (a) pause and ask the user for the resolution,
   (b) log it to `ambiguity_log.md` and proceed with a documented
   assumption, or (c) both — pause for high-severity items, batch-log
   low-severity ones? Default: **(c) hybrid**.
5. **Output format for generated code.** CSV outputs (matches ground
   truth, easy to diff) or Parquet (more realistic for the target
   platform)? Default: **CSV** for the MVP so validation is trivially
   diff-able.
6. **Validation strictness.** Row-for-row equality on a stable sort key
   (strict), or row count + key uniqueness + aggregate match (loose)?
   Default: **strict** — the synthetic data is small enough that row-level
   equality is achievable.
7. **Test framework.** pytest (default), unittest, or just a script that
   exits non-zero on mismatch?

Any other constraints the user wants to call out (timezone handling,
locale, naming conventions for generated code, etc.) should also be
captured at this stage.

### 0.3 — After the user answers

Echo back the decisions in a short confirmation block, then ask the user
to approve before you begin Phase 1. Only after approval do you exit plan
mode and start executing.

---

## Section 1 — Solution deliverable structure

The final deliverable is a single solution document at
`build/SOLUTION.md`, written and updated incrementally as you progress
through the phases. It must contain these named sections, in this order:

### 1.1 Executive summary
3–5 sentences. What was modernized, into what, with what level of
confidence. Not marketing copy — just the facts a reviewer needs in 30
seconds.

### 1.2 Codebase inventory
Tables enumerating: programs, macros, includes, format catalogs, raw
input datasets, ADaM output datasets. Counts of DATA steps, PROC blocks
(broken out by PROC type), and macro definitions. This is the "what
exists" snapshot from Phase 1.

### 1.3 Dependency graph
This section is critical and must contain three sub-graphs, each rendered
as a Mermaid diagram embedded in the markdown:

- **1.3.1 Program-level DAG** — nodes are SAS programs, edges are
  `depends_on` derived from output→input dataset relationships. This is
  the same graph that drives `build/dag/pipeline.json`.
- **1.3.2 Dataset-level lineage** — nodes are datasets (raw + ADaM),
  edges are `produces`. Annotate each edge with the program that owns
  the transformation.
- **1.3.3 Column-level lineage (selected critical columns)** — for at
  least 5 important derived columns (e.g. `TRTEMFL`, `MAX_AESEV`,
  `ITTFL`, `TRTDURD`, `INCIDENCE_RATE`), show the upstream columns and
  operations that produce them. Use a Mermaid graph or a structured
  table — your choice, but it must be readable.

After each Mermaid diagram, include a short prose paragraph naming any
*non-obvious* edges (e.g. cross-program coupling via global macro
variables, implicit type-cast joins). The point is to make hidden
dependencies visible.

### 1.4 Knowledge graph schema and statistics
Node and edge types, with counts. A small ER-style diagram of the graph
schema. A list of the 5–10 most-connected nodes (these are usually the
"hub" datasets that touch everything else).

### 1.5 Ambiguity register
A numbered table of every ambiguity detected during Phases 1–3:

| # | Location | Ambiguity | Resolution | Severity | Source |
|---|----------|-----------|------------|----------|--------|
| 1 | `04_derive_adae.sas:31` | `%is_treatment_emergent` reads global `&TRT_START_DT` set elsewhere | Documented assumption: cohort-level latest randomization date | High | static analysis |
| ... |

Entries marked High severity must also appear in
`build/reports/ambiguity_log.md` with the full assumption write-up.

### 1.6 Generated artifacts
Table listing every file produced under `build/`, with one-line
descriptions and provenance (which phase produced it, from what input).

### 1.7 Validation results
The diff vs `ground_truth/`:

- Per-dataset: row count match, schema match, row-for-row equality
- Aggregate equivalence checks (e.g. AE_SUMMARY totals reconcile to
  ADAE totals)
- Pass/fail summary

If any check fails, include the failing rows or columns inline.

### 1.8 Coverage report
What SAS constructs were handled, what were skipped, and what would need
to be added for a real client codebase. Be specific — "macros" is not
useful; "macros with `%sysfunc` or dynamic `&&var` references" is.

### 1.9 Recommendations for production rollout
What changes when this approach is applied to a real client SAS estate
(hundreds of programs vs five): parser robustness, graph storage,
human-in-the-loop checkpoints, CI/CD integration. 5–10 bullet points.

---

## Section 2 — Repository layout

```
.
├── CLAUDE.md                     <- you are here
├── solution_design.md            <- team's design spec; treat as authoritative
├── README.md                     <- human-facing readme
├── sas_codebase/
│   ├── config/
│   │   ├── setup.sas             <- libnames, options, includes
│   │   └── formats.sas           <- PROC FORMAT catalog
│   ├── macros/
│   │   └── util_macros.sas       <- %macro definitions
│   ├── programs/
│   │   ├── 01_clean_dm.sas
│   │   ├── 02_clean_ae.sas
│   │   ├── 03_derive_adsl.sas
│   │   ├── 04_derive_adae.sas
│   │   └── 05_summary_safety.sas
│   └── docs/
│       ├── functional_spec.md
│       └── data_dictionary.md
├── input_data/                   <- synthetic raw inputs (CSV)
├── ground_truth/                 <- expected outputs (CSV)
└── build/                        <- you will create this
    ├── ast/                      <- per-program AST + CFG + DFG
    ├── graph/                    <- knowledge graph
    ├── specs/                    <- regenerated functional specs
    ├── schemas/                  <- regenerated target-language schemas
    ├── dag/                      <- regenerated execution DAG
    ├── tests/                    <- regenerated test stubs
    ├── target/                   <- generated target-language code (Phase 5 output)
    ├── reports/                  <- ambiguity_log.md, validation_report.md, coverage.md
    └── SOLUTION.md               <- the solution deliverable (Section 1)
```

---

## Section 3 — Hard rules

**R1. Do not read the SAS programs while writing target-language code.**
By the time you reach Phase 5, the SAS source files must be closed. You
write target-language code from the regenerated specs (`build/specs/*.md`)
and schemas (`build/schemas/`) only. If you find yourself wanting to peek
at the SAS, that is a signal that the spec generated in Phase 4 is
incomplete — fix the spec, then continue.

**R2. Flag ambiguity, do not guess it.**
Every place where the SAS behavior depends on context that is not
statically recoverable (macro side effects, implicit type casts,
missing-vs-null, date format dependencies) gets logged with: location,
what is ambiguous, the assumption made, and what would change if the
assumption is wrong.

**R3. Every artifact is generated from the graph, not from re-parsing source.**
Phases 4 and 5 read from `build/graph/`, never from `sas_codebase/`. If
you need information that is not in the graph, the fix is to enrich the
graph (Phase 3), not to short-circuit by re-reading SAS.

**R4. Validate row-for-row against ground truth.**
The final code must produce outputs that match `ground_truth/*.csv`
row-for-row, column-for-column. Mismatches go in
`build/reports/validation_report.md`. A "looks plausible" output is a failure.

**R5. Be honest about what the synthetic codebase represents.**
This MVP uses a synthetic codebase. Some real-world constructs
(`%sysfunc`, dynamic `&&var`, PROC SQL passthrough) are not present.
When you encounter a construct you cannot handle, say so explicitly in
`build/reports/coverage.md`.

**R6. Update `build/SOLUTION.md` as you go, not just at the end.**
After each phase, append or update the relevant sections. The solution
document is a living artifact, not a final report.

---

## Section 4 — Phase execution detail

### Phase 1 — Parse SAS into AST + flow graphs
**Inputs:** `sas_codebase/`
**Outputs:** `build/ast/<program>.json`, `<program>.cfg.json`, `<program>.dfg.json`, `<program>.expanded.sas`
**Solution sections updated:** 1.2 (codebase inventory), 1.3.1 (program DAG)

Two-pass parser:
- **Pass A — Macro expansion.** Resolve `%let`, `%macro`/`%mend`, `%include`,
  and macro variable references. Maintain a symbol table per program.
  Output expanded source for audit. Every node in the post-expansion AST
  must carry a back-reference to the macro and call site that produced it.
- **Pass B — Structural AST.** Identify DATA steps, PROC blocks, macros,
  includes. For PROC SQL: parse `create table`, `select`, `from`, `join`,
  `where`, `group by`, `order by`. For macros: record signature, body,
  parameter defaults, **and which global symbols the body reads or writes**
  (this catches cross-program coupling).

Per program, derive:
- **Control Flow Graph**: nodes are statements/blocks, edges are
  sequential / conditional successor relationships.
- **Data Flow Graph**: nodes are datasets and columns; edges are `reads`,
  `writes`, `derives_from`. Cross-program edges are recorded too.

### Phase 2 — Parse documentation
**Inputs:** `sas_codebase/docs/*.md`
**Outputs:** `build/graph/doc_entities.json`
**Solution sections updated:** 1.5 (ambiguity register starts here)

Extract: dataset mentions, column mentions, business rules, known issues,
ownership. Chunk by markdown section header. Each entity carries a
back-reference to the source file and section.

Specifically: when the documentation mentions an open issue or a known
discrepancy between spec and implementation (e.g. functional_spec §6.3
"first dose vs randomization date"), capture it as an `OpenIssue` node
linked to the affected dataset/column.

### Phase 3 — Build the knowledge graph
**Inputs:** `build/ast/`, `build/graph/doc_entities.json`
**Outputs:** `build/graph/kg.{sqlite|json}` (per the user's choice in 0.2)
**Solution sections updated:** 1.3.2, 1.3.3, 1.4

Schema:

| Node type      | Required attrs                                    |
| -------------- | ------------------------------------------------- |
| `Dataset`      | name, library, source_program                     |
| `Column`       | name, dataset, dtype, nullable, label             |
| `Proc`         | name, program, line_range                         |
| `Macro`        | name, params, reads_globals, writes_globals       |
| `BusinessRule` | text, source_doc, source_section                  |
| `Constraint`   | column_or_dataset, rule, severity                 |
| `OpenIssue`    | id, text, status                                  |

| Edge type    | From → To                          |
| ------------ | ---------------------------------- |
| `reads`      | Proc/Macro → Dataset/Column        |
| `writes`     | Proc/Macro → Dataset/Column        |
| `calls`      | Macro → Macro                      |
| `depends_on` | Program → Program                  |
| `implements` | Proc → BusinessRule                |
| `validates`  | Constraint → Column/Dataset        |
| `flagged_by` | Dataset/Column → OpenIssue         |

Provide a small CLI (`build/graph/query.py`) supporting at minimum:
`list_datasets`, `lineage_for_column <colname>`, `dependencies_of_program <prog>`.

### Phase 4 — Regenerate downstream artifacts
**Inputs:** `build/graph/`
**Outputs:** `build/specs/`, `build/schemas/`, `build/dag/`, `build/tests/`
**Solution sections updated:** 1.6

- **Functional specs** (`build/specs/<program>.md`): per program — purpose,
  inputs, outputs, transformations in plain English (derived from CFG/DFG),
  business rules, assumptions and ambiguities, acceptance criteria. These
  specs are the **only** input to Phase 5.
- **Schemas** (`build/schemas/<dataset>.{py|sql|...}`): target-language
  schema definitions per dataset, with nullability and field comments.
- **Execution DAG** (`build/dag/pipeline.json`): topologically-sorted job
  list with dependencies. Annotate parallelizable jobs.
- **Test stubs** (`build/tests/test_<dataset>.{py|...}`): for each output
  dataset, a test that loads `ground_truth/<dataset>.csv` and the
  generated output and asserts schema match, row count match, row-by-row
  equality on a stable sort key.

### Phase 5 — Generate target-language code from specs
**Inputs:** `build/specs/`, `build/schemas/` only
**Outputs:** `build/target/<program>.{py|sql|...}`
**Solution sections updated:** 1.7 (validation), 1.8 (coverage)

For each spec, generate target-language code that produces the output
dataset. Honor the listed business rules and assumptions. Do not invent
behavior not present in the spec.

After generating each program, run the corresponding test stub. On
failure: read the failure, decide whether the spec is wrong or the
codegen is wrong, fix the appropriate one, regenerate, re-test. Do **not**
patch the generated code by reading the SAS source (R1).

### Validation phase (always last)
Produce `build/reports/validation_report.md` and update §1.7 of `SOLUTION.md`:
- Per-dataset row-count match, schema match, full row equality
- Aggregate equivalence checks
- Ambiguity log summary by severity
- Coverage summary

A passing MVP requires: row count, schema, and row equality all green
for every output dataset.

---

## Section 5 — Working style

- Phase by phase. Do not jump ahead. The phases exist to make the work
  auditable; skipping them defeats the demo.
- After each phase, write a short status note to
  `build/reports/phase<N>_summary.md` and update the relevant sections of
  `build/SOLUTION.md`.
- Keep each generated target-language file under 200 lines. If it grows
  beyond that, the spec is probably doing too much; consider splitting.
- The synthetic data is small (20 subjects). Optimize for correctness
  and explainability, not scale.
- When you finish, the user should be able to read `build/SOLUTION.md`
  end-to-end without opening any SAS file or any code file, and come
  away with a complete picture of what was modernized and how to trust
  the result.
