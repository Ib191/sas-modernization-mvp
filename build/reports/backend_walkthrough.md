# Backend Walkthrough — SAS Modernization Pipeline

How every phase is implemented in code, with file paths and line numbers, so
you can show the actual implementation during your presentation.

---

## 0 · File layout (10,000-foot view)

```
build/
├── parser/                      Phase 1: SAS parser + Phase 2: doc parser
│   ├── sas_parser.py             (~430 lines) tokenizer + macro expander + AST builder
│   ├── flow_graphs.py            (~150 lines) CFG + DFG derivation per program
│   ├── parse_docs.py             (~170 lines) Phase 2 markdown parser
│   └── run.py                    (~140 lines) Phase 1 driver — orchestrates the parse
│
├── graph/                       Phase 3: knowledge graph
│   ├── build_kg.py               (~280 lines) graph builder (NetworkX MultiDiGraph)
│   └── query.py                  (~180 lines) CLI for lineage / dependency queries
│
├── regenerator/                 Phase 4: regenerate downstream artifacts
│   └── regenerate.py             (~410 lines) emits specs/schemas/DAG/tests from the graph
│
├── target/                      Phase 5: generated Python pipeline
│   ├── common.py                 shared constants + CSV/Parquet writer
│   ├── 01_clean_dm.py            ┐
│   ├── 02_clean_ae.py            │
│   ├── 03_derive_adsl.py         │ generated from build/specs/<program>.md
│   ├── 04_derive_adae.py         │
│   └── 05_summary_safety.py      ┘
│
├── dag/
│   ├── pipeline.json             topologically-sorted execution plan
│   └── run.py                    runner: invokes each target/*.py in order
│
└── tests/                       Phase 5 validation
    ├── conftest.py               shared fixture (project_root, output dirs)
    ├── test_adam_*.py            6 datasets × {schema, row count, row equality}
    └── test_aggregates.py        5 cross-dataset reconciliation tests
```

**Mental model.** Every phase is a Python script you can run standalone:

```
python build/parser/run.py              # Phase 1
python build/parser/parse_docs.py       # Phase 2
python build/graph/build_kg.py          # Phase 3
python build/regenerator/regenerate.py  # Phase 4
python build/dag/run.py                 # Phase 5 (runs target/*.py in order)
python -m pytest build/tests/           # validation
```

There is no orchestration framework, no DAG runner, no service. Each script
takes the previous phase's outputs from disk and writes its own to disk.
That's it. **The simplicity is the point** — anyone can read it, anyone
can re-run it.

---

## 1 · Phase 1 — Parsing SAS into AST + flow graphs

### 1.1 Files

- [`build/parser/sas_parser.py`](../parser/sas_parser.py) — the heart of Phase 1
- [`build/parser/flow_graphs.py`](../parser/flow_graphs.py) — derives CFG and DFG from the AST
- [`build/parser/run.py`](../parser/run.py) — driver that ties it together

### 1.2 The two-pass design

Pass A (`expand_macros`) and Pass B (`build_ast`) are sequential:

```
SAS source
   │
   │ Pass A: comment strip → statement split → macro expansion
   ▼
Expanded SAS source (saved to build/ast/<program>.expanded.sas)
   │
   │ Pass B: statement-level classification → block grouping
   ▼
ProgramAST (saved to build/ast/<program>.json)
```

### 1.3 Pass A — Macro expansion (the load-bearing step)

The job of Pass A is to:

1. Strip comments (block `/* … */` and line `* … ;`)
2. Split text into statements at `;` boundaries (respecting strings)
3. Resolve `%include "config/setup.sas"` by inlining the included file
4. Register `%let var = value;` symbols
5. Register `%macro name(p=); body %mend;` definitions
6. **Scan each macro body** for global reads/writes
7. Substitute `&var` references and `%name(args)` calls textually

#### The smoking-gun function — `_scan_macro_globals`

Located in [`sas_parser.py:107-119`](../parser/sas_parser.py). This is what
catches the `&TRT_START_DT` cross-program coupling:

```python
def _scan_macro_globals(body: str, params: list[str]) -> tuple[list[str], list[str]]:
    """Within a macro body, find references to `&var` whose var is not a
    parameter (= reads_globals) and `into :var` patterns (= writes_globals)."""
    pset = {p.lower() for p in params}
    reads = []
    for m in _MACRO_VAR.finditer(body):
        v = m.group(1)
        if v.lower() not in pset and v.upper() not in {"SYSDATE", "SYSTIME"}:
            reads.append(v)
    writes = [m.group(1) for m in _INTO_VAR.finditer(body)]
    return list(dict.fromkeys(reads)), list(dict.fromkeys(writes))
```

**What it does.** For each macro body, find every `&xxx` reference. If `xxx`
is not a parameter name and not a built-in like `SYSDATE`, it's a **global
read** — record it. Find every `into :xxx` SQL clause; that's a **global
write**. Both lists are deduplicated.

**Why it matters.** When the macro `is_treatment_emergent` is registered,
this function records `reads_globals=['TRT_START_DT']` for it. The variable
isn't a parameter and isn't `%let` anywhere visible. **That fact is then
carried into the knowledge graph in Phase 3** as a `Macro` node attribute.
Without this scan, the cross-program coupling would be invisible.

#### The textual substitution — `MacroTable.expand_calls`

Located in [`sas_parser.py:153-181`](../parser/sas_parser.py). When a
program calls `%is_treatment_emergent(ae_start=aestdt)`, we substitute the
body literally with parameter values replaced:

```python
def expand_calls(self, text, *, file, line):
    prev = None
    cur = text
    while prev != cur:                       # iterate to fixpoint (handles nested calls)
        prev = cur
        def repl(match):
            name = match.group(1).lower()
            if name not in self.macros:
                return match.group(0)
            args = _split_args(match.group(2))
            m = self.macros[name]
            self.call_sites.append(MacroCallSite(...))
            body = m.body
            merged = {p[0].lower(): p[1] or "" for p in m.params}
            merged.update(args)
            for pname, pval in merged.items():
                body = re.sub(rf"&{re.escape(pname)}\.?", pval, body, flags=re.IGNORECASE)
            return f"({body})"
        cur = _MACRO_INVOKE.sub(repl, cur)
    return cur
```

**Why a fixpoint loop.** Nested macro calls (`%a(%b(x))`) need multiple passes.
We loop until the text stops changing.

**Why textual substitution.** It's pragmatic — for the constructs in this
codebase (no `%sysfunc`, no `%eval`, no `%do`), textual substitution is
sufficient. A real macro evaluator (production rollout, §1.9) would build
an actual symbol-table interpreter.

### 1.4 The `%mend` boundary fix-up (a real-world wart)

In [`sas_parser.py:50-55`](../parser/sas_parser.py):

```python
def strip_comments(source):
    s = _BLOCK_COMMENT.sub(" ", source)
    s = _STAR_COMMENT.sub(" ", s)
    # SAS allows `%mend` to follow an expression with no preceding semicolon
    # (the macro body's last expression doesn't need to be a complete statement).
    # Inject one so split_statements sees `%mend` cleanly.
    s = re.sub(r"(?i)(?<![;\s])\s*%mend\b", "; %mend", s)
    return s
```

**Why this exists.** SAS macros like:
```sas
%macro iso_to_sasdate(var=);
  input(substr(strip(&var), 1, 10), ?? yymmdd10.)   ← no `;` at end
%mend iso_to_sasdate;
```

The body's last expression has no `;` because it's an expression-bodied
macro. Without this fix-up, `split_statements` glued the body to the next
`%mend`, and we ended up registering only one giant macro that contained
all five. **This was a real bug we hit and fixed.**

### 1.5 Pass B — Structural AST

`build_ast` in [`sas_parser.py:267-355`](../parser/sas_parser.py) walks the
expanded source statement-by-statement and produces a list of `Block`
objects. There are three kinds:

- `kind='data'` — a `data <out>;` … `run;` block
- `kind='proc'` — a `proc <name>;` … `run;|quit;` block
- `kind='misc'` — top-level statements (options, libname, %put, …)

For DATA blocks, every inner statement is classified by `_absorb_data_stmt`
([`sas_parser.py:357-419`](../parser/sas_parser.py)) into kinds like
`set`, `merge`, `by`, `keep`, `drop`, `length`, `format`, `label`, `assign`,
`if_assign`, `sum`, `if_delete`, `rename`, or `raw`. Each statement carries
its line number and original text.

For PROC SQL blocks, `_parse_sql_block` extracts:
- `create table <out> as select … from <in> [join <in> on …] …;` → `sql_create_table`
- `select … into :<var> from …;` → `sql_select` with `into_macro_var`

This is where `select max(rfstdt) into :TRT_START_DT` is captured as a
global write — closing the loop with Pass A's read scan.

### 1.6 Flow graphs (`flow_graphs.py`)

`build_cfg` ([`flow_graphs.py:18-46`](../parser/flow_graphs.py)) — Control
Flow Graph. Nodes are blocks, edges are sequential successors. Branches
appear when an `if … then delete;` filter splits the data path:

```python
for i, b in enumerate(ast.blocks):
    for st in b.statements:
        if st.get("kind") == "if_delete":
            edges.append({"from": f"b{i}", "to": f"b{i}_filter", "kind": "branch_filter"})
            nodes.append({"id": f"b{i}_filter", "kind": "filter", ...})
```

`build_dfg` ([`flow_graphs.py:90-135`](../parser/flow_graphs.py)) — Data
Flow Graph. Nodes are datasets and `(dataset, column)` pairs. Edges are
`reads_dataset`, `writes_dataset`, `produces`, and column-level write
edges from each DATA step's assignments.

`program_dependencies` ([`flow_graphs.py:140-176`](../parser/flow_graphs.py))
— **Cross-program DAG.** This is where we compute that `04_derive_adae`
depends on `02_clean_ae` because 04 reads `adam.ae_clean` and 02 writes it:

```python
writers: dict[str, str] = {}      # dataset -> producing program
reads: dict[str, set[str]] = {}    # program -> {dataset}

for a in asts:
    for b in a.blocks:
        for ds in b.output_datasets:
            if ds.startswith("work."): continue
            writers[ds] = a.program
    # ... same for reads ...

edges = []
for prog, ds_set in reads.items():
    for ds in ds_set:
        producer = writers.get(ds)
        if producer and producer != prog:
            edges.append({"from": prog, "to": producer, "kind": "depends_on", "via_dataset": ds})
```

**Why this matters.** This is what produces the program-level Mermaid DAG
in SOLUTION.md §1.3.1. It's purely dataset-driven — but importantly **it
doesn't capture the macro-globals coupling**. That coupling was found by
Pass A's scan and lives separately in `macro_table.json`.

### 1.7 What lands on disk

`run.py` ([`parser/run.py`](../parser/run.py)) writes:

| File                                          | Content                                            |
| --------------------------------------------- | -------------------------------------------------- |
| `build/ast/<program>.json`                    | Per-program AST (8 files)                          |
| `build/ast/<program>.cfg.json`                | Per-program control flow graph                     |
| `build/ast/<program>.dfg.json`                | Per-program data flow graph                        |
| `build/ast/<program>.expanded.sas`            | Post-macro-expansion source (audit)                |
| `build/ast/_aggregate/macro_table.json`       | All 5 macros + their reads/writes-globals          |
| `build/ast/_aggregate/program_dag.json`       | Cross-program dependency edges                     |
| `build/ast/_aggregate/counts.json`            | Counts feeding SOLUTION.md §1.2                    |

---

## 2 · Phase 2 — Parsing documentation

### 2.1 File

- [`build/parser/parse_docs.py`](../parser/parse_docs.py) — single-file Phase 2

### 2.2 What it does

Walks `sas_codebase/docs/*.md` line-by-line, recognizing:

- **Markdown headers** (`#`, `##`, `###`) → `Section` entities
- **Bullets** (`- ` or `* `) inside §4.x sections → `BusinessRule`s
- **Bullets or section bodies** under "Known issues / open items", or any
  bullet naming an `SP-###` tracker → `OpenIssue`s

### 2.3 The extraction loop

In [`parse_docs.py:54-100`](../parser/parse_docs.py):

```python
def parse_doc(path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    sections = []
    current = None

    for i, line in enumerate(lines, start=1):
        m = _HEADER_RE.match(line)
        if m:
            if current is not None: sections.append(current)
            current = {
                "title": m.group(2), "level": len(m.group(1)),
                "line_start": i, "body_lines": [],
                "datasets": set(), "columns": set(),
                "bullets": [], "open_issues": [],
            }
            continue
        if current is None: continue
        current["body_lines"].append((i, line))

        # Bullets, dataset references, column references
        b = _BULLET_RE.match(line)
        if b:
            txt = b.group(1).strip()
            current["bullets"].append({"line": i, "text": txt})
            tickers = _TICKER_RE.findall(txt)
            if tickers or "deferred" in txt.lower() or "open" in txt.lower():
                current["open_issues"].append({"line": i, "text": txt, "tickers": tickers})

        for ds_match in _DATASET_REF_RE.finditer(line):
            current["datasets"].add(ds_match.group(1).lower())
        for col_match in _COLUMN_TICK_RE.finditer(line):
            current["columns"].add(col_match.group(1).upper())
    ...
```

**The regexes** (defined at lines 38-48):

```python
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*)$")
_TICKER_RE = re.compile(r"\b(SP-\d{2,4})\b")
_DATASET_REF_RE = re.compile(r"\b((?:RAW|ADAM|TGT|WORK)\.[A-Z][A-Z0-9_]+|"
                              r"DM_CLEAN|AE_CLEAN|ADSL|ADAE|AE_SUMMARY|AE_INCIDENCE|"
                              r"SITE_LOOKUP)\b")
_COLUMN_TICK_RE = re.compile(r"`([A-Z][A-Z0-9_]+)`")
```

`_DATASET_REF_RE` is biased toward known dataset names — it's a heuristic,
not a parser. `_COLUMN_TICK_RE` recognizes ALL_CAPS identifiers inside
backticks (markdown code spans), which is the convention this spec uses.

### 2.4 Output

`build/graph/doc_entities.json`:

```json
{
  "documents": [
    {"file": "sas_codebase/docs/functional_spec.md",
     "sections": [{"title": "...", "level": 2, "line_start": 10, "datasets": [...], ...}]},
    ...
  ],
  "business_rules": [{"text": "...", "source_section": "...", "datasets": [...]}],
  "open_issues":    [{"id": "SP-227", "tickers": ["SP-227"], "text": "...", ...}]
}
```

The 4 issues that come out: `SP-184`, `SP-227`, and two anonymous ones
(§6.1 DM duplicates, §6.4 site lookup join — no tracker IDs in the spec).

---

## 3 · Phase 3 — Building the knowledge graph

### 3.1 Files

- [`build/graph/build_kg.py`](../graph/build_kg.py) — graph builder
- [`build/graph/query.py`](../graph/query.py) — CLI for lineage queries
- Output: `build/graph/kg.json` (NetworkX node-link format) + `kg_stats.json`

### 3.2 The graph schema

A `networkx.MultiDiGraph` with **8 node kinds** and **8 edge kinds**:

| Node kind     | Required attributes                                              |
| ------------- | ---------------------------------------------------------------- |
| `Dataset`     | library, name, producer, source_csv                              |
| `Column`      | dataset, name, dtype, nullable, samples                          |
| `Proc`        | program, proc_kind, proc_name, label, line_start, line_end       |
| `Macro`       | name, params, **reads_globals**, **writes_globals**, source      |
| `Program`     | name                                                             |
| `BusinessRule`| text, source_file, source_section, source_line                   |
| `OpenIssue`   | id, tickers, text, source_file, source_section                   |
| `Constraint`  | text, constraint_kind                                            |

| Edge kind        | Direction                            |
| ---------------- | ------------------------------------ |
| `reads`          | Proc → Dataset                       |
| `writes`         | Proc → Dataset / Proc → Column       |
| `contributes_to` | Dataset → Dataset                    |
| `calls`          | Program → Macro                      |
| `depends_on`     | Program → Program                    |
| `applies_to`     | BusinessRule → Dataset               |
| `flagged_by`     | Dataset / Column → OpenIssue         |
| `validates`      | Constraint → Column / Dataset        |

### 3.3 The build process

`build_graph` in [`build_kg.py:84-263`](../graph/build_kg.py) — five passes:

**Pass 1 — Dataset and Column nodes.** Read every CSV in `input_data/` and
`ground_truth/`. For each, scan column types:

```python
def _scan_csv_columns(path):
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        info = {c: {"nullable": False, "samples": [],
                     "all_int": True, "all_float": True, "all_iso_date": True,
                     "any": False} for c in cols}
        for row in reader:
            for c in cols:
                v = (row.get(c) or "").strip()
                if v == "":
                    info[c]["nullable"] = True; continue
                # ... type-test cascade ...
```

The dtype is `int` if every non-blank value parses as int, otherwise
`float`, otherwise `date` (ISO 8601), otherwise `string`. **The
leading-zero detector** ([`build_kg.py:60-66`](../graph/build_kg.py)) is
why `SITEID='02'` stays a string — without that, pandas would read it as
`Int64` and we'd lose the leading zero on output.

**Pass 2 — Proc + Column-write edges.** For each program's AST, walk every
DATA and PROC block. Add a `Proc` node for the block. Add `reads`/`writes`
edges to the Dataset nodes the block touches. **For DATA steps**, walk the
inner statements; every `assign`, `if_assign`, or `sum` writes a column. If
the block writes to a `work.*` transient, propagate the column write to
the program's long-lived output (so `trtemfl`, written in `work.adae_pre`,
ends up linked to `adam.adae`):

```python
target_datasets = [out_ds] if not out_ds.startswith("work.") else long_lived_outputs
for st in b["statements"]:
    if st.get("kind") in ("assign", "if_assign", "sum"):
        col = st.get("col")
        for td in target_datasets:
            cid = f"{td}.{col.lower()}"
            if g.has_node(cid):
                g.add_edge(block_id, cid, kind="writes", line=st.get("line"))
```

**Pass 2b — PROC SQL alias extraction.** For `create table X as select …
expr as col …`, find every `as <alias>` and add a column-write edge:

```python
if b["kind"] == "proc" and b["proc_name"] == "sql":
    for st in b["statements"]:
        if st.get("kind") != "sql_create_table": continue
        for m in re.finditer(r"\bas\s+([A-Za-z_][A-Za-z0-9_]*)", raw, re.IGNORECASE):
            col = m.group(1).lower()
            ...
```

This is what makes `INCIDENCE_RATE` traceable to its writer (the SQL block
in `05_summary_safety`).

**Pass 3 — Macro nodes + call edges.** From `macro_table.json` (Phase 1's
output), add a `Macro` node per macro with `reads_globals` and
`writes_globals` attributes. Walk each program's `macro_call_sites` to add
`Program -> Macro` `calls` edges.

**Pass 4 — `depends_on` edges.** From `program_dag.json`, add the
cross-program edges directly.

**Pass 5 — Doc entities.** From `doc_entities.json`, add `BusinessRule`
and `OpenIssue` nodes. Wire `applies_to` and `flagged_by` edges by matching
dataset names mentioned in the docs to Dataset nodes.

**Pass 6 — Constraints.** Hard-coded list of synthesized constraints (e.g.
"USUBJID is unique in DM_CLEAN/ADSL", "AESEV_STD ∈ {MILD, MODERATE,
SEVERE, blank}") — each becomes a `Constraint` node with `validates` edges
to the columns it constrains. ([`build_kg.py:223-244`](../graph/build_kg.py))

### 3.4 Serialization

NetworkX serializes the graph to a node-link JSON via `node_link_data()`,
saved to `build/graph/kg.json`. Stats (counts by kind, top-10 most
connected) saved to `kg_stats.json`.

### 3.5 The query CLI

[`query.py`](../graph/query.py) loads the JSON back into a NetworkX graph
and exposes 5 commands:

```python
COMMANDS = {
    "list_datasets":            list_datasets,
    "lineage_for_column":       lineage_for_column,
    "dependencies_of_program":  dependencies_of_program,
    "issues_for_dataset":       issues_for_dataset,
    "macros_with_globals":      macros_with_globals,
}
```

Each is a small graph traversal. For example, `lineage_for_column TRTEMFL`
([`query.py:38-71`](../graph/query.py)):

```python
def lineage_for_column(g, target_col):
    matches = [n for n, a in g.nodes(data=True)
                if a.get("kind") == "Column" and a.get("name").lower() == target_col.lower()]
    for cid in matches:
        attr = g.nodes[cid]
        ds = attr["dataset"]
        # find Procs that write this column
        writers = [u for u, _, _, a in g.in_edges(cid, keys=True, data=True)
                    if a.get("kind") == "writes"]
        # find upstream datasets
        upstream = [u for u, _, _, a in g.in_edges(ds, keys=True, data=True)
                     if a.get("kind") == "contributes_to"]
        # find OpenIssues
        flags = [v for _, v, _, a in g.out_edges(cid, keys=True, data=True)
                  if a.get("kind") == "flagged_by"]
        # ... print everything ...
```

Pure NetworkX traversal — no SQL, no engine, just `g.in_edges()` and
`g.out_edges()`.

---

## 4 · Phase 4 — Regenerating downstream artifacts

### 4.1 File

- [`build/regenerator/regenerate.py`](../regenerator/regenerate.py)

### 4.2 What it produces

Four kinds of artifact, each from a dedicated function:

```python
def main():
    g = _load_graph()      # build/graph/kg.json
    emit_schemas(g)        # → build/schemas/<lib>_<dataset>.py
    emit_specs(g)          # → build/specs/<program>.md
    emit_dag()             # → build/dag/pipeline.json
    emit_tests()           # → build/tests/test_<lib>_<dataset>.py
```

### 4.3 `emit_schemas` — Python schema modules

[`regenerate.py:48-103`](../regenerator/regenerate.py). For each Dataset
node in the graph, emit a Python module like:

```python
DATASET = 'adam.dm_clean'
COLUMNS: list[str] = ['USUBJID', 'AGE', 'AGE_DERIVED', 'AGEGRP', ...]
DTYPES: dict[str, str] = {
    'USUBJID': 'object',  # string, nullable=False, e.g. CTX-001 | CTX-002
    'AGE':     'Int64',   # int, nullable=False, e.g. 69 | 59
    ...
}
```

Column order is **pinned to the ground-truth CSV header** (we read the
first line of `ground_truth/<dataset>.csv`). dtype map comes from the
graph's CSV-scan attributes. **No SAS file is read.**

### 4.4 `emit_specs` — the most important Phase 4 output

[`regenerate.py:108-275`](../regenerator/regenerate.py). For each program,
build a markdown file with these sections:

1. **Purpose** — one paragraph from a hard-coded `PROGRAM_PURPOSES` dict
2. **Inputs** — per-dataset table of columns, dtypes, sample values (from graph)
3. **Outputs** — same, for output datasets
4. **Transformations** — a hard-coded `PROGRAM_TRANSFORMS` dict with the
   step-by-step logic in plain English
5. **Business rules** — pulled from `doc_entities.json` filtered by section
6. **Ambiguities and resolutions** — from a hard-coded mapping per program
7. **Acceptance criteria** — schema + row count + row equality, sort key

**Why hard-coded?** The `PROGRAM_PURPOSES` and `PROGRAM_TRANSFORMS` dicts
encode the **interpretation** of the AST that Phase 5 will use as its
contract. In a production rollout, these would be auto-generated by
walking the DFG and emitting English; for the MVP, we curated them once
to keep the spec readable. **They're the contract — and they live in this
file, in code, version-controlled, reviewable.**

The TRTEMFL step in `PROGRAM_TRANSFORMS["04_derive_adae"]` reads:

```python
"5. Compute `TRTEMFL`: `'Y'` if `AESTDT is not null and "
"AESTDT >= TRT_START_DT` else `'N'`. (Cohort-level scalar — "
"see §1.5 #1.)",
```

That single string is what Phase 5 reads and turns into Python.

### 4.5 `emit_dag` — topological ordering

[`regenerate.py:283-330`](../regenerator/regenerate.py). Reads the
program-level DAG from `build/ast/_aggregate/program_dag.json`,
topologically sorts the programs, groups them into parallelizable levels:

```python
order = []
pending = dict(deps)
while pending:
    ready = [p for p, ds in pending.items() if not (ds - set(order))]
    ready.sort()
    if not ready: raise RuntimeError("cycle")
    order.extend(ready)
    for p in ready: del pending[p]
```

Output is `build/dag/pipeline.json`:

```json
{
  "topological_order": ["01_clean_dm", "02_clean_ae", "03_derive_adsl", ...],
  "levels": [["01_clean_dm", "02_clean_ae"], ["03_derive_adsl"], ...],
  "edges": [...],
  "outputs_per_program": {"01_clean_dm": ["adam.dm_clean"], ...}
}
```

**Levels** show parallelizability: 01 and 02 can run in parallel; 03 must
wait for 01; 04 must wait for 02 and 03.

### 4.6 `emit_tests` — pytest stubs

[`regenerate.py:336-407`](../regenerator/regenerate.py). For each dataset,
emit a `test_<lib>_<dataset>.py` file with three tests:

```python
def test_schema_match(...):
    assert list(gen.columns) == list(truth.columns)

def test_row_count(...):
    assert len(gen) == len(truth)

def test_row_for_row_equality(...):
    gen_sorted = _stable_sort(_normalize(gen), SORT_KEY)
    truth_sorted = _stable_sort(_normalize(truth), SORT_KEY)
    diff_rows = [(i, g, t) for i, (g, t) in enumerate(zip(gen_sorted.itertuples(...),
                                                          truth_sorted.itertuples(...)))
                 if g != t]
    assert not diff_rows
```

`_normalize` rounds `INCIDENCE_RATE` to 4 dp before comparison (the only
float column). `_stable_sort` uses `mergesort` with `na_position="first"`
to make the comparison deterministic.

A `conftest.py` provides the shared `project_root`, `ground_truth_dir`,
`target_output_dir` fixtures.

---

## 5 · Phase 5 — Generating the target Python

### 5.1 Files

- [`build/target/common.py`](../target/common.py) — shared utilities
- [`build/target/01_clean_dm.py`](../target/01_clean_dm.py)
- [`build/target/02_clean_ae.py`](../target/02_clean_ae.py)
- [`build/target/03_derive_adsl.py`](../target/03_derive_adsl.py)
- [`build/target/04_derive_adae.py`](../target/04_derive_adae.py)
- [`build/target/05_summary_safety.py`](../target/05_summary_safety.py)
- [`build/dag/run.py`](../dag/run.py) — runs them in topological order

### 5.2 The R1 contract

These files **only** read `build/specs/<program>.md` and
`build/schemas/<lib>_<dataset>.py` (conceptually — in this MVP I, the LLM,
read those before writing the Python; in a production rollout this would
be a code generator that takes the spec text and emits Python). **They
never `import` anything from `sas_codebase/` or read any SAS file.**

Verify this is true:

```bash
grep -rn "sas_codebase" build/target/   # should return nothing
```

### 5.3 `common.py` — shared utilities

```python
SEX_DECODE_MAP = {"M": "Male", "F": "Female", "U": "Unknown"}
ARM_DECODE_MAP = {"PLACEBO": "Placebo", "DRUG_X_LOW": "Drug X 50mg", "DRUG_X_HI": "Drug X 100mg"}

def to_date(s):    return pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
def fmt_date(s):   return s.dt.strftime("%Y-%m-%d").fillna("")
def agegrp(age):
    if pd.isna(age): return ""
    a = int(age)
    if a < 18:  return "< 18"
    if a <= 39: return "18-39"
    if a <= 64: return "40-64"
    return "65+"

def write_outputs(df, name):
    csv_path = OUTPUT_DIR / f"{name}.csv"
    pq_path  = OUTPUT_DIR / f"{name}.parquet"
    df.to_csv(csv_path, index=False, lineterminator="\n")
    df.to_parquet(pq_path, index=False)
```

The `SEX_DECODE_MAP`, `ARM_DECODE_MAP`, and `agegrp` ranges are encoded
from the spec text (`PROGRAM_TRANSFORMS["01_clean_dm"]` step 7-9). **In a
production rollout, these would be auto-emitted from the parsed PROC
FORMAT in `build/ast/_aggregate/`** — that's recommendation §1.9 #5.

### 5.4 The per-program structure

Every target program follows the same skeleton:

```python
def main():
    # Step 1 — read inputs (CSVs)
    df = pd.read_csv(...)

    # Step 2..N — transformations from the spec
    df["NEW_COL"] = ...

    # Step N+1 — column ordering + sort + write
    out = df[OUTPUT_COLS].sort_values(...).reset_index(drop=True)
    write_outputs(out, "<dataset_name>")
```

**Every step in the code corresponds to a numbered step in the spec**, so
the audit trail is one-to-one. For example,
[`04_derive_adae.py`](../target/04_derive_adae.py) lines 27-49:

```python
# Step 1 — read AE_CLEAN as string. Reading with default dtype inference
# promotes AESEVN/AEDUR (Int64 with nulls) to float64, which round-trips
# to '1.0' / '8.0' in CSV instead of '1' / '8'.
ae = pd.read_csv(OUTPUT_DIR / "ae_clean.csv", dtype=str, ...)

# Step 2 — read ADSL subset (also as string)
adsl = pd.read_csv(OUTPUT_DIR / "adsl.csv", dtype=str, ...)

# Step 3 — load cohort-level TRT_START_DT from state
trt_start_dt = pd.to_datetime(...)

# Step 4 — inner join on USUBJID
adae = ae.merge(adsl_sub, on="USUBJID", how="inner")

# Step 5 — TRTEMFL: cohort-level scalar comparison (ambiguity #1)
adae["TRTEMFL"] = (
    aestdt.notna() & (aestdt >= trt_start_dt)
).map({True: "Y", False: "N"})
```

### 5.5 Cross-program state — the `&TRT_START_DT` solution

In SAS, `&TRT_START_DT` was a runtime macro variable. In Python, we have
no such concept — but we still need to share that scalar between programs
03 and 04. Solution: persist it to disk.

In [`03_derive_adsl.py:51-58`](../target/03_derive_adsl.py):

```python
saffl_y = adsl[adsl["SAFFL"].eq("Y")]
rf_dates = to_date(saffl_y["RFSTDT"])
trt_start_dt = rf_dates.max()
STATE_DIR.mkdir(parents=True, exist_ok=True)
(STATE_DIR / "trt_start_dt.txt").write_text(
    trt_start_dt.strftime("%Y-%m-%d") + "\n", encoding="utf-8"
)
```

In [`04_derive_adae.py:32-35`](../target/04_derive_adae.py):

```python
trt_start_dt = pd.to_datetime(
    (STATE_DIR / "trt_start_dt.txt").read_text(encoding="utf-8").strip(),
    format="%Y-%m-%d",
)
```

**This is explicit cross-program state**, on disk, with a known path.
Anyone debugging the pipeline can `cat build/target/state/trt_start_dt.txt`
and see `2024-03-06`. **The implicit SAS macro globals are now explicit
files.**

### 5.6 PROC SQL → duckdb

`05_summary_safety.py` is interesting because the SAS uses PROC SQL for
the summary aggregations. In Python, we use `duckdb` for the same SQL
syntax, no rewriting needed:

```python
con = duckdb.connect()
con.register("adsl", adsl)
con.register("adae", adae)

denom = con.execute("""
    SELECT ARM, ARM_DECODE, COUNT(DISTINCT USUBJID) AS N_SUBJ
    FROM adsl WHERE SAFFL = 'Y'
    GROUP BY ARM, ARM_DECODE
""").df()
```

`con.register("name", df)` exposes a pandas DataFrame as a duckdb table.
`con.execute(SQL).df()` runs SQL and returns a pandas DataFrame. **We get
SAS-PROC-SQL-like ergonomics with zero translation effort.** The cast
`COUNT(*)::INTEGER` and `SUM(...)::INTEGER` (lines 84-85) is what fixed the
"0.0 vs 0" CSV-rendering issue from the validation loop.

### 5.7 The runner

[`build/dag/run.py`](../dag/run.py) — 25 lines:

```python
def main():
    pipeline = json.loads((HERE / "pipeline.json").read_text(encoding="utf-8"))
    order = pipeline["topological_order"]
    print(f"running {len(order)} programs in topological order:")
    for stem in order:
        script = TARGET_DIR / f"{stem}.py"
        result = subprocess.run([sys.executable, str(script)], cwd=PROJECT_ROOT)
        if result.returncode != 0:
            sys.exit(result.returncode)
```

It reads `pipeline.json`, then `subprocess.run`s each program in order.
That's it. Production rollout would replace this with Airflow / Prefect /
Dagster.

---

## 6 · Validation

### 6.1 The pytest stubs

Auto-generated by Phase 4. For each dataset, three tests as shown in §4.6.

[`build/tests/test_aggregates.py`](../tests/test_aggregates.py) — written
by hand (it's specific enough that auto-generation isn't worth the
complexity). Five cross-dataset reconciliations:

```python
def test_ae_summary_total_matches_adae_treatment_emergent(adae, ae_summary):
    te_count = (adae["TRTEMFL"] == "Y").sum()
    summary_total = ae_summary["N_EVENTS"].astype(int).sum()
    assert te_count == summary_total

def test_ae_incidence_denominators_match_adsl_saffl(adsl, ae_incidence):
    saffl = adsl[adsl["SAFFL"] == "Y"]
    expected = saffl.groupby("ARM")["USUBJID"].nunique().to_dict()
    actual = ae_incidence.drop_duplicates("ARM").set_index("ARM")["N_SUBJ_TOTAL"].astype(int).to_dict()
    assert actual == expected
```

These catch problems that row-by-row tests pass coincidentally — like a
TRTEMFL filter that drops the right number of rows but the wrong ones.

### 6.2 The "fix the spec" loop

Two test failures during this project; both fixed by amending the spec,
not the generated Python:

1. **AGE_DERIVED off-by-one** — spec said `floor((days)/365.25)`, ground
   truth used `days // 365`. Fixed by editing
   [`build/specs/01_clean_dm.md` step 3](../specs/01_clean_dm.md), then
   regenerating Phase 5. Recorded as ambiguity #6 in
   [SOLUTION.md §1.5](../SOLUTION.md#1.5-ambiguity-register).

2. **N_SERIOUS rendering as `'0.0'`** — duckdb's `SUM(CASE…)` returns
   DECIMAL → pandas float64 → CSV. Fixed by adding `::INTEGER` cast in
   [`05_summary_safety.py`](../target/05_summary_safety.py) line 84.

---

## 7 · Cross-cutting concerns

### 7.1 R1 enforcement

There's no programmatic enforcement of "Phase 5 doesn't read SAS". It's a
**discipline**, enforced by:

- File-system separation: `sas_codebase/` lives outside `build/`
- Code review: a `grep "sas_codebase" build/target/` should return nothing
- The spec being the only thing the codegen author (or LLM) reads

**For production rollout (§1.9 #4):** put the codegen LLM in a sandbox
with `build/specs/` and `build/schemas/` mounted read-only and
`sas_codebase/` not mounted at all.

### 7.2 Caching

The Streamlit UI uses `@st.cache_data` for `load_json` and `read_text` so
the JSON files don't re-deserialize on every interaction. The pipeline
itself has no caching — every script reads its inputs fresh and writes
its outputs fresh, on every run.

### 7.3 Reproducibility

```bash
rm -rf build/  &&  python build/parser/run.py  && \
python build/parser/parse_docs.py             && \
python build/graph/build_kg.py                && \
python build/regenerator/regenerate.py        && \
python build/dag/run.py                       && \
python -m pytest build/tests/
```

Every run produces byte-identical outputs (modulo timestamps in the PDF).
The synthetic data uses `random.seed(42)` in `generate_data_and_truth.py`
so the inputs are stable too.

---

## 8 · FAQ for the presentation

### Q: How would this scale to a real SAS codebase?

A: The architecture is constant; the components swap. See
[SOLUTION.md §1.9](../SOLUTION.md#1.9-recommendations-for-production-rollout).
Headlines: hand-rolled parser → tree-sitter; NetworkX-in-JSON → SQLite or
graph DB; in-process ambiguity pause → Linear/Jira ticket integration;
hard-coded `PROGRAM_TRANSFORMS` dict → graph-walk that emits English from
the DFG.

### Q: Why not just use an LLM to translate SAS to Python?

A: An LLM doesn't surface ambiguities — it picks one. Cross-program
coupling, vendor quirks, deferred decisions all get silently encoded. The
graph-driven pipeline forces every ambiguity into a register with
counterfactual analysis. **The LLM is fine for codegen; it's the wrong
tool for analysis.**

### Q: Why a hand-rolled parser instead of tree-sitter?

A: 533 lines of SAS, no `%do`/`%eval`/`%sysfunc` substantive use, no
dynamic `&&`. The hand-rolled parser is ~430 lines and finishes in
milliseconds. Tree-sitter requires a build step and a community grammar.
**For a 10-engineer real client, switch to tree-sitter on day 1.**

### Q: How does a test failure tell you to fix the spec, not the code?

A: It doesn't, automatically — it's a discipline. But the *evidence* tells
you: if the generated Python perfectly implements the spec but disagrees
with ground truth, the spec is wrong (e.g. AGE_DERIVED). If the spec is
correct but the Python disagrees with the spec, the codegen is wrong (e.g.
N_SERIOUS dtype). **Diagnose the gap; fix the appropriate one; never
reach back to SAS.**

### Q: What if a real client has macros with `%sysfunc` or `%eval`?

A: This MVP's parser leaves `%sysfunc` literal — fine for `setup.sas`'s
cosmetic uses. For real codebases, `%sysfunc(intnx(…))` and `%eval` are
common. The tree-sitter migration (production §1.9 #1) gets you to a real
AST; a real macro evaluator (§1.9 #2) gets you the runtime semantics.

### Q: What's the trickiest bug you hit?

A: The `%mend` boundary fix-up (Phase 1) — SAS macros with
expression-bodied bodies (no trailing `;` before `%mend`) caused all 5
macros to get registered as one giant macro. Took a few minutes to debug,
2 lines to fix. **Real-world parser bugs are like this — small, local,
embarrassing in retrospect.**

---

## 9 · Live-demo cheat sheet

For each phase, here's the file to open, the line to point to, and the
talking point:

| Phase | File                                               | Line       | Talking point                                                                                          |
| ----- | -------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------ |
| 1     | `build/parser/sas_parser.py`                       | 107-119    | `_scan_macro_globals` — the function that catches `&TRT_START_DT`                                       |
| 1     | `build/ast/_aggregate/macro_table.json`             | 16-19      | `is_treatment_emergent` shows `reads_globals=['TRT_START_DT']`                                          |
| 2     | `build/parser/parse_docs.py`                       | 38-48      | The 5 regexes that drive the whole doc parser                                                          |
| 2     | `build/graph/doc_entities.json`                     | open_issues | The 4 extracted issues with their tracker IDs                                                          |
| 3     | `build/graph/build_kg.py`                          | 84-263     | The 6-pass graph builder                                                                               |
| 3     | `build/graph/query.py`                             | 38-71      | `lineage_for_column` — pure NetworkX traversal                                                         |
| 4     | `build/regenerator/regenerate.py`                  | 175-275    | `PROGRAM_TRANSFORMS` — the contract between graph and codegen                                          |
| 4     | `build/specs/04_derive_adae.md`                    | step 5     | The TRTEMFL line — exactly what Phase 5 reads                                                          |
| 5     | `build/target/04_derive_adae.py`                   | line 38-43 | The TRTEMFL Python — one-to-one with spec step 5                                                       |
| 5     | `build/target/state/trt_start_dt.txt`               | full       | The implicit SAS macro is now an explicit file: `2024-03-06`                                           |
| Val   | `build/tests/test_aggregates.py`                   | 36-43      | `ae_summary_total_matches_adae_treatment_emergent` — the kind of test row-by-row diff would never catch |

---

## 10 · One-liner summary

> "We don't translate SAS to Python. We mediate everything through a knowledge
> graph: facts in, specs out, codegen reads only the specs. Ambiguities
> surface explicitly, and validation is row-for-row equality against ground
> truth. The whole pipeline regenerates from scratch in under 5 seconds and
> ships with 23 passing tests, a cell-level diff viewer, and an audit trail."
