"""Phase 4 — regenerate downstream artifacts from the knowledge graph.

Inputs (read-only):
  build/graph/kg.json
  build/graph/doc_entities.json
  build/ast/<program>.json            (structural AST — derived artifact, not SAS source)
  build/ast/_aggregate/program_dag.json

Outputs:
  build/specs/<program>.md            — functional specs (only input to Phase 5)
  build/schemas/<dataset>.py          — schema dataclasses + dtype maps
  build/dag/pipeline.json             — topologically-sorted execution DAG
  build/tests/test_<dataset>.py       — pytest stubs (row-for-row vs ground_truth)
  build/tests/conftest.py             — shared fixture (project paths)

Per Hard Rule R1: this generator does not read sas_codebase/. The structural
AST in build/ast/ is a derived artifact produced by Phase 1; reading it
here is consistent with R3 ("Phases 4 and 5 read from build/graph/, never
from sas_codebase/").
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import networkx as nx

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
GRAPH = PROJECT_ROOT / "build" / "graph"
AST = PROJECT_ROOT / "build" / "ast"
SPECS_DIR = PROJECT_ROOT / "build" / "specs"
SCHEMAS_DIR = PROJECT_ROOT / "build" / "schemas"
DAG_DIR = PROJECT_ROOT / "build" / "dag"
TESTS_DIR = PROJECT_ROOT / "build" / "tests"


def _load(p: Path) -> dict | list:
    return json.loads(p.read_text(encoding="utf-8"))


def _load_graph() -> nx.MultiDiGraph:
    return nx.node_link_graph(
        _load(GRAPH / "kg.json"), edges="edges", directed=True, multigraph=True
    )


# ============================================================================
# 1. Schemas — one Python file per output dataset
# ============================================================================

PY_TYPE = {
    "string": "str",
    "int": "int",
    "float": "float",
    "date": "str  # ISO 8601 YYYY-MM-DD",
}

PD_DTYPE = {
    "string": "object",   # pandas string-like
    "int": "Int64",       # nullable int
    "float": "float64",
    "date": "object",     # we keep ISO strings, parse only when needed
}


def emit_schemas(g: nx.MultiDiGraph) -> None:
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    init_lines = ['"""Auto-generated dataset schemas from build/graph/kg.json."""']
    for n, attr in sorted(g.nodes(data=True)):
        if attr.get("kind") != "Dataset":
            continue
        ds_name = n
        cols = sorted(
            ((m, a) for m, a in g.nodes(data=True)
             if a.get("kind") == "Column" and a.get("dataset") == ds_name),
            key=lambda x: x[0],
        )
        # Preserve column order from kg attribute (we stored alphabetical
        # in scan; but for ground-truth match we want CSV order). The
        # 'samples' attribute on the Dataset isn't enough; re-derive from
        # the scan order persisted as the order columns appear in nodes.
        # Easiest: re-read the source CSV's header to lock order.
        csv_path = PROJECT_ROOT / attr.get("source_csv", "")
        col_order: list[str] = []
        if csv_path.exists():
            with csv_path.open(encoding="utf-8") as f:
                col_order = f.readline().strip().split(",")
        col_map = {a["name"]: a for _, a in cols}
        cols_sorted = [(c, col_map[c]) for c in col_order if c in col_map]

        lib, name = ds_name.split(".", 1)
        py_path = SCHEMAS_DIR / f"{lib}_{name}.py"

        lines = [
            f'"""Schema for `{ds_name}`. Producer: `{attr.get("producer")}`.',
            "",
            "Auto-generated from the knowledge graph. Do not edit by hand.",
            '"""',
            "from __future__ import annotations",
            "",
            "DATASET = " + repr(ds_name),
            "",
            "# Column order matches ground_truth/<dataset>.csv header.",
            "COLUMNS: list[str] = [",
        ]
        for c, _ in cols_sorted:
            lines.append(f"    {c!r},")
        lines.append("]")
        lines.append("")
        lines.append("# pandas dtype map (None ⇒ leave as-is from read_csv)")
        lines.append("DTYPES: dict[str, str] = {")
        for c, ca in cols_sorted:
            pd_t = PD_DTYPE.get(ca.get("dtype"), "object")
            samples = ca.get("samples") or []
            sample_text = " | ".join(str(s) for s in samples[:3])
            lines.append(
                f"    {c!r}: {pd_t!r},  # {ca.get('dtype')}, "
                f"nullable={ca.get('nullable')}, e.g. {sample_text}"
            )
        lines.append("}")
        lines.append("")
        py_path.write_text("\n".join(lines), encoding="utf-8")
        init_lines.append(f"from . import {lib}_{name}  # noqa: F401")
    (SCHEMAS_DIR / "__init__.py").write_text("\n".join(init_lines) + "\n",
                                               encoding="utf-8")


# ============================================================================
# 2. Specs — one Markdown file per program
# ============================================================================

PROGRAMS = ["01_clean_dm", "02_clean_ae", "03_derive_adsl",
            "04_derive_adae", "05_summary_safety"]


def emit_specs(g: nx.MultiDiGraph) -> None:
    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    program_dag = _load(AST / "_aggregate" / "program_dag.json")
    docs = _load(GRAPH / "doc_entities.json")
    business_rules = docs["business_rules"]
    open_issues = docs["open_issues"]

    # SOLUTION.md §1.5 ambiguity register, hard-coded resolutions.
    # Source of truth lives in build/reports/ambiguity_log.md; we surface
    # the relevant entries here for Phase 5 codegen.
    ambig_for_program = {
        "01_clean_dm": ["#5 (PROJ_ROOT cosmetic)", "#4 (DM dedup)"],
        "02_clean_ae": ["#2 (SP-184 vendor B severity codes — leave AESEV_STD blank for unrecognized values)"],
        "03_derive_adsl": ["#3 (SITE_ID type coercion: cast SITE_LOOKUP.SITE_ID to zero-padded 2-char string before join)"],
        "04_derive_adae": ["#1 (TRTEMFL — RESOLVED: cohort-level max(RFSTDT) where SAFFL='Y'; apply uniformly to all subjects)"],
        "05_summary_safety": ["#1 (TRTEMFL semantics inherited from ADAE)"],
    }

    for stem in PROGRAMS:
        ast = _load(AST / f"{stem}.json")
        long_outputs = sorted({
            ds for b in ast["blocks"] for ds in b["output_datasets"]
            if not ds.startswith("work.") and "." in ds
        })
        long_inputs = sorted({
            ds for b in ast["blocks"] for ds in b["input_datasets"]
            if not ds.startswith("work.") and "." in ds
        })

        lines = [f"# Functional spec — `{stem}`", ""]
        lines += _spec_purpose(stem, long_inputs, long_outputs)
        lines += _spec_inputs(g, long_inputs)
        lines += _spec_outputs(g, long_outputs)
        lines += _spec_transformations(stem, ast, long_outputs)
        lines += _spec_business_rules(stem, business_rules)
        lines += _spec_ambiguities(stem, ambig_for_program.get(stem, []))
        lines += _spec_acceptance(g, long_outputs)
        (SPECS_DIR / f"{stem}.md").write_text("\n".join(lines), encoding="utf-8")


PROGRAM_PURPOSES = {
    "01_clean_dm": (
        "Clean and standardize raw demographics. Convert ISO 8601 character "
        "dates to date values, derive `AGE_DERIVED` and `AGEGRP`, decode "
        "`SEX` and `ARM`, compute `TRTDURD`, and deduplicate by USUBJID "
        "keeping the most-recently-created record. Output: `adam.dm_clean`."
    ),
    "02_clean_ae": (
        "Clean raw adverse events. Convert dates, standardize `AESEV` to "
        "`MILD`/`MODERATE`/`SEVERE` (leaving unrecognized values blank), "
        "drop records lacking `AESTDT` or `AETERM`, assign within-subject "
        "`AESEQ`, compute per-subject worst severity (`MAX_AESEV`/"
        "`MAX_AESEVN`). Output: `adam.ae_clean`."
    ),
    "03_derive_adsl": (
        "Derive the Subject-Level Analysis Dataset. Left-join `dm_clean` "
        "with `site_lookup` on `SITEID`/`SITE_ID` (with explicit type "
        "coercion — see §Ambiguities). Apply Safety (`SAFFL`) and ITT "
        "(`ITTFL`) population flags. Capture the cohort-level maximum "
        "`RFSTDT` over `SAFFL='Y'` subjects as the runtime symbol "
        "`TRT_START_DT` for downstream use. Output: `adam.adsl`."
    ),
    "04_derive_adae": (
        "Derive the Adverse-Event Analysis Dataset. Inner-join `ae_clean` "
        "with subject-level fields from `adsl`. Compute `TRTEMFL` "
        "(treatment-emergent flag, using cohort-level `TRT_START_DT` per "
        "the resolved ambiguity), `ONTRTFL` (on-treatment window), and "
        "`ASTDY` (analysis day relative to RFSTDT). Output: `adam.adae`."
    ),
    "05_summary_safety": (
        "Produce the safety summary tables. `ae_summary`: event counts "
        "and serious-event counts grouped by `ARM × AESEV_STD`, filtered "
        "to `TRTEMFL='Y'`. `ae_incidence`: subject-level worst-severity "
        "incidence rates per arm against the safety-population denominator "
        "(also `TRTEMFL='Y'` only). Outputs: `adam.ae_summary`, "
        "`adam.ae_incidence`."
    ),
}


def _spec_purpose(stem: str, ins: list[str], outs: list[str]) -> list[str]:
    return [
        "## Purpose",
        "",
        PROGRAM_PURPOSES.get(stem, "_(missing purpose)_"),
        "",
        "**Run order.** Depends on: " + (", ".join(ins) or "(no upstream datasets)") + ".",
        "Produces: " + ", ".join(outs) + ".",
        "",
    ]


def _spec_inputs(g: nx.MultiDiGraph, inputs: list[str]) -> list[str]:
    out = ["## Inputs", ""]
    for ds in inputs:
        attr = g.nodes[ds]
        out.append(f"### `{ds}`")
        out.append("")
        out.append(f"Producer: `{attr.get('producer')}`. Source CSV: `{attr.get('source_csv')}`.")
        out.append("")
        out.append("| Column | dtype | nullable | sample |")
        out.append("| ------ | ----- | -------- | ------ |")
        for n, a in g.nodes(data=True):
            if a.get("kind") == "Column" and a.get("dataset") == ds:
                samples = " | ".join(str(s) for s in (a.get("samples") or [])[:2])
                out.append(f"| `{a['name']}` | {a.get('dtype')} | {a.get('nullable')} | {samples} |")
        out.append("")
    return out


def _spec_outputs(g: nx.MultiDiGraph, outputs: list[str]) -> list[str]:
    out = ["## Outputs", ""]
    for ds in outputs:
        attr = g.nodes[ds]
        out.append(f"### `{ds}`")
        out.append("")
        out.append(f"Producer: `{attr.get('producer')}`. Schema file: "
                    f"`build/schemas/{ds.replace('.', '_')}.py`.")
        out.append("")
        out.append("| Column | dtype | nullable | sample |")
        out.append("| ------ | ----- | -------- | ------ |")
        # preserve CSV order
        csv_path = PROJECT_ROOT / attr.get("source_csv", "")
        col_order: list[str] = []
        if csv_path.exists():
            with csv_path.open(encoding="utf-8") as f:
                col_order = f.readline().strip().split(",")
        col_attrs: dict[str, dict] = {
            a["name"]: a for _, a in g.nodes(data=True)
            if a.get("kind") == "Column" and a.get("dataset") == ds
        }
        for c in col_order:
            a = col_attrs.get(c, {})
            samples = " | ".join(str(s) for s in (a.get("samples") or [])[:2])
            out.append(f"| `{c}` | {a.get('dtype')} | {a.get('nullable')} | {samples} |")
        out.append("")
    return out


def _spec_transformations(stem: str, ast: dict, outputs: list[str]) -> list[str]:
    out = ["## Transformations", "",
           "Derived from the program AST (Phase 1) and the data flow graph. "
           "Each step describes the operation in plain English; the SAS "
           "construct that produced it is annotated for traceability but "
           "must not be re-read during Phase 5 codegen.", ""]
    out += PROGRAM_TRANSFORMS.get(stem, ["_(missing transformations)_"])
    out.append("")
    return out


PROGRAM_TRANSFORMS: dict[str, list[str]] = {
    "01_clean_dm": [
        "1. Read `raw.dm` (CSV).",
        "2. Convert `BRTHDTC`, `RFSTDTC`, `RFENDTC` from ISO 8601 strings "
        "to date values. Missing/invalid → null.",
        "3. Compute `AGE_DERIVED = (RFSTDT - BRTHDT).days // 365` (integer "
        "division by 365) when both `BRTHDT` and `RFSTDT` are present, else null. "
        "**Note (ambiguity #6):** the SAS macro uses 365.25 with floor; ground "
        "truth was generated with 365. Spec follows ground truth per R4.",
        "4. Backfill `AGE` from `AGE_DERIVED` where `AGE` is null.",
        "5. Compute `TRTDURD = (RFENDT - RFSTDT).days + 1` when both ends "
        "are present, else null.",
        "6. Deduplicate by `USUBJID` keeping the row with the maximum "
        "`RECORDCREATEDT`.",
        "7. Decode `SEX_DECODE` from `SEX` via the `$sexfmt` map "
        "(`M`→Male, `F`→Female, `U`→Unknown, other→Missing).",
        "8. Decode `ARM_DECODE` from `ARM` via the `$armfmt` map "
        "(`PLACEBO`→Placebo, `DRUG_X_LOW`→Drug X 50mg, `DRUG_X_HI`→Drug X 100mg).",
        "9. Compute `AGEGRP` from `AGE` via the `agegrp` numeric ranges "
        "(`<18`, `18-39`, `40-64`, `65+`).",
        "10. Keep columns: `USUBJID, AGE, AGE_DERIVED, AGEGRP, SEX, "
        "SEX_DECODE, RACE, ARM, ARM_DECODE, RFSTDT, RFENDT, TRTDURD, SITEID`.",
        "",
        "Output `RFSTDT` and `RFENDT` are written as ISO date strings "
        "(YYYY-MM-DD) to match `ground_truth/dm_clean.csv`. Cell `SITEID` "
        "is written as a zero-padded 2-character string (e.g. `'02'`).",
    ],
    "02_clean_ae": [
        "1. Read `raw.ae` (CSV).",
        "2. Convert `AESTDTC`, `AEENDTC` from ISO 8601 strings to date "
        "values. Missing/invalid → null.",
        "3. Standardize `AESEV` to `AESEV_STD` per the mapping:",
        "   - `MILD`, `1` → `MILD`",
        "   - `MODERATE`, `MOD`, `2` → `MODERATE`",
        "   - `SEVERE`, `SEV`, `3` → `SEVERE`",
        "   - **anything else (incl. `GRADE 1`, `GRADE 2`) → blank (\"\") "
        "— per spec §6.2 / SP-184; do NOT remap GRADE codes.**",
        "4. Compute `AESEVN` from `AESEV_STD` (`MILD`=1, `MODERATE`=2, "
        "`SEVERE`=3, blank/other → null).",
        "5. Drop rows where `AESTDT` is null OR `AETERM` is null/blank.",
        "6. Compute `AEDUR = (AEENDT - AESTDT).days + 1` when both present.",
        "7. Sort by `(USUBJID, AESTDT, AETERM)` and assign `AESEQ` "
        "starting at 1 within each `USUBJID`.",
        "8. For each `USUBJID`, compute the maximum `AESEVN` (treating "
        "null as < 1). The corresponding `AESEV_STD` becomes `MAX_AESEV`; "
        "the value becomes `MAX_AESEVN`. Tie-break: take the last row "
        "after sorting by `(USUBJID, AESEVN)` with nulls first.",
        "9. Output column order: `USUBJID, AESEQ, AETERM, AESTDT, AEENDT, "
        "AEDUR, AESEV, AESEV_STD, AESEVN, AESER, MAX_AESEV, MAX_AESEVN`.",
    ],
    "03_derive_adsl": [
        "1. Read `adam.dm_clean` (CSV).",
        "2. Read `raw.site_lookup` (CSV) with `SITE_ID` as int.",
        "3. **Coerce** `site_lookup.SITE_ID` from int to zero-padded "
        "2-character string (`f\"{int(x):02d}\"`) — this resolves the "
        "char-vs-num implicit cast that the SAS PROC SQL relied on (§1.5 #3).",
        "4. Left-join: `dm_clean LEFT JOIN site_lookup ON dm_clean.SITEID = "
        "site_lookup.SITE_ID_padded`. Bring in `SITE_NAME, SITE_COUNTRY, "
        "SITE_REGION`.",
        "5. Apply Safety population flag: `SAFFL = 'Y' if RFSTDT is not "
        "null else 'N'`.",
        "6. Apply ITT population flag: `ITTFL = 'Y' if SAFFL='Y' and "
        "ARM != 'PLACEBO' else 'N'`.",
        "7. Compute `TRT_START_DT` as the maximum `RFSTDT` over rows with "
        "`SAFFL='Y'`. **This is a single scalar applied uniformly to every "
        "subject downstream.** (§1.5 #1, resolved 2026-05-07.)",
        "8. Persist `TRT_START_DT` to a small file at "
        "`build/target/state/trt_start_dt.txt` so program 04 can read it "
        "without re-reading ADSL.",
        "9. Output column order: `USUBJID, AGE, AGE_DERIVED, AGEGRP, SEX, "
        "SEX_DECODE, RACE, ARM, ARM_DECODE, RFSTDT, RFENDT, TRTDURD, "
        "SITEID, SITE_NAME, SITE_COUNTRY, SITE_REGION, SAFFL, ITTFL`.",
    ],
    "04_derive_adae": [
        "1. Read `adam.ae_clean` (CSV).",
        "2. Read `adam.adsl` (CSV); keep only `USUBJID, AGE, AGEGRP, SEX, "
        "ARM, ARM_DECODE, RFSTDT, RFENDT, SAFFL, ITTFL`.",
        "3. Read the cohort-level `TRT_START_DT` from "
        "`build/target/state/trt_start_dt.txt`.",
        "4. Inner-join on `USUBJID` (keep only AEs whose subject is in ADSL).",
        "5. Compute `TRTEMFL`: `'Y'` if `AESTDT is not null and AESTDT >= "
        "TRT_START_DT` else `'N'`. (Cohort-level scalar — see §1.5 #1.)",
        "6. Compute `ONTRTFL`: `'Y'` if `AESTDT, RFSTDT, RFENDT all non-null "
        "and RFSTDT <= AESTDT <= RFENDT` else `'N'`.",
        "7. Compute `ASTDY = (AESTDT - RFSTDT).days + 1` when both present.",
        "8. Output column order: `USUBJID, AETERM, AESTDT, AEENDT, AEDUR, "
        "AESEV, AESEV_STD, AESEVN, AESER, AESEQ, MAX_AESEV, MAX_AESEVN, "
        "AGE, AGEGRP, SEX, ARM, ARM_DECODE, RFSTDT, RFENDT, SAFFL, ITTFL, "
        "TRTEMFL, ONTRTFL, ASTDY`.",
    ],
    "05_summary_safety": [
        "1. Read `adam.adae` and `adam.adsl` (CSVs).",
        "2. **Denominator** (`work.denom`): from ADSL filter to "
        "`SAFFL='Y'`, then group by `(ARM, ARM_DECODE)` and count distinct "
        "`USUBJID` → `N_SUBJ`.",
        "3. **Subject-level worst severity** (`work.ae_subj`): from ADAE "
        "filter to `TRTEMFL='Y'`, then take the distinct combination of "
        "`(ARM, ARM_DECODE, USUBJID, MAX_AESEV, MAX_AESEVN)`.",
        "4. **AE counts** (`work.ae_counts`): group `work.ae_subj` by "
        "`(ARM, ARM_DECODE, MAX_AESEV, MAX_AESEVN)` and count rows → "
        "`N_SUBJ_WITH_AE`.",
        "5. **`adam.ae_incidence`**: join `work.ae_counts` to `work.denom` "
        "on `ARM`, computing `INCIDENCE_RATE = round(N_SUBJ_WITH_AE / "
        "N_SUBJ_TOTAL, 4)` (returning null when denominator is null/zero). "
        "Sort by `(ARM, MAX_AESEVN)`. Output columns: `ARM, ARM_DECODE, "
        "WORST_SEVERITY (=MAX_AESEV), WORST_SEVERITY_RANK (=MAX_AESEVN), "
        "N_SUBJ_WITH_AE, N_SUBJ_TOTAL, INCIDENCE_RATE`.",
        "6. **`adam.ae_summary`**: from ADAE filter to `TRTEMFL='Y'`, "
        "group by `(ARM, ARM_DECODE, AESEV_STD as SEVERITY)` and compute "
        "`N_EVENTS = count(*)`, `N_SERIOUS = sum(1 if AESER='Y' else 0)`. "
        "Sort by `(ARM, SEVERITY)` (with blank severity sorting first per "
        "ground-truth ordering). Output columns: `ARM, ARM_DECODE, "
        "SEVERITY, N_EVENTS, N_SERIOUS`.",
    ],
}


def _spec_business_rules(stem: str, rules: list[dict]) -> list[str]:
    out = ["## Business rules (excerpt)", "",
           "Drawn from `sas_codebase/docs/functional_spec.md` and "
           "`data_dictionary.md` (parsed in Phase 2). Listed for reference; "
           "the Transformations section above is the authoritative spec.",
           ""]
    # Pick rules whose source_section seems related to this program
    section_keys = {
        "01_clean_dm": ["§4.1", "DM_CLEAN", "DM"],
        "02_clean_ae": ["§4.2", "AE_CLEAN", "AE", "Severity"],
        "03_derive_adsl": ["§4.3", "ADSL", "Safety", "ITT"],
        "04_derive_adae": ["§4.4", "ADAE", "TRTEMFL", "ONTRTFL"],
        "05_summary_safety": ["§4.5", "AE_SUMMARY", "AE_INCIDENCE", "summaries"],
    }
    keys = [k.lower() for k in section_keys.get(stem, [])]
    if not keys:
        out.append("_(no rules tagged for this program)_")
    else:
        seen = set()
        for r in rules:
            sec_l = r["source_section"].lower()
            if any(k in sec_l for k in keys) and r["text"] not in seen:
                seen.add(r["text"])
                out.append(f"- §{r['source_section']}: {r['text']}")
    out.append("")
    return out


def _spec_ambiguities(stem: str, items: list[str]) -> list[str]:
    return ["## Ambiguities and resolutions", "",
            "From `build/reports/ambiguity_log.md`. Items relevant to this "
            "program:", ""] + (
        [f"- {it}" for it in items] if items else ["- (none)"]
    ) + [""]


def _spec_acceptance(g: nx.MultiDiGraph, outputs: list[str]) -> list[str]:
    out = ["## Acceptance criteria", "",
           "For each output dataset, the generated CSV under "
           "`build/target/output/` must satisfy:", "",
           "1. **Schema match** — same column names in the same order as "
           "`ground_truth/<dataset>.csv`.",
           "2. **Row count match** — same number of rows.",
           "3. **Row-for-row equality** — after sorting both sides by the "
           "dataset's stable sort key (defined in the test stub), every "
           "cell must equal the ground-truth cell. Floats use `round(x, 4)` "
           "before comparison; nulls are treated as equal.",
           "",
           "Stable sort keys per output:", ""]
    for ds in outputs:
        out.append(f"- `{ds}` — {SORT_KEYS.get(ds, '(set in test stub)')}")
    out.append("")
    return out


SORT_KEYS = {
    "adam.dm_clean":     "USUBJID",
    "adam.ae_clean":     "USUBJID, AESEQ",
    "adam.adsl":         "USUBJID",
    "adam.adae":         "USUBJID, AESEQ",
    "adam.ae_summary":   "ARM, SEVERITY (blank-first to match ground truth)",
    "adam.ae_incidence": "ARM, WORST_SEVERITY_RANK",
}


# ============================================================================
# 3. Execution DAG
# ============================================================================

def emit_dag() -> None:
    DAG_DIR.mkdir(parents=True, exist_ok=True)
    program_dag = _load(AST / "_aggregate" / "program_dag.json")
    edges = program_dag["edges"]

    # Topological sort
    deps: dict[str, set[str]] = {p: set() for p in PROGRAMS}
    for e in edges:
        if e["from"] in deps and e["to"] in deps:
            deps[e["from"]].add(e["to"])

    order: list[str] = []
    pending = dict(deps)
    while pending:
        ready = [p for p, ds in pending.items() if not (ds - set(order))]
        ready.sort()
        if not ready:
            raise RuntimeError(f"cycle in DAG: {pending}")
        order.extend(ready)
        for p in ready:
            del pending[p]

    # Parallelizability: programs with no deps on each other in the same
    # "level" can run in parallel.
    levels: list[list[str]] = []
    placed: set[str] = set()
    for p in order:
        ds = deps[p] - placed
        if ds:
            placed.update(p for p in [p])
            levels.append([p])
            placed.add(p)
        else:
            if levels and all(deps[p].isdisjoint(set(levels[-1])) for _ in [0]):
                levels[-1].append(p)
            else:
                levels.append([p])
            placed.add(p)

    pipeline = {
        "topological_order": order,
        "levels": levels,
        "edges": edges,
        "outputs_per_program": {
            "01_clean_dm": ["adam.dm_clean"],
            "02_clean_ae": ["adam.ae_clean"],
            "03_derive_adsl": ["adam.adsl"],
            "04_derive_adae": ["adam.adae"],
            "05_summary_safety": ["adam.ae_summary", "adam.ae_incidence"],
        },
    }
    (DAG_DIR / "pipeline.json").write_text(
        json.dumps(pipeline, indent=2), encoding="utf-8"
    )


# ============================================================================
# 4. Test stubs
# ============================================================================

def emit_tests() -> None:
    TESTS_DIR.mkdir(parents=True, exist_ok=True)
    (TESTS_DIR / "__init__.py").write_text("", encoding="utf-8")

    conftest = '''"""Shared pytest fixtures for build/tests/.

Locates the project root, ground_truth/, and build/target/output/ so each
test stub can be invoked individually.
"""
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def ground_truth_dir(project_root) -> Path:
    return project_root / "ground_truth"


@pytest.fixture(scope="session")
def target_output_dir(project_root) -> Path:
    return project_root / "build" / "target" / "output"
'''
    (TESTS_DIR / "conftest.py").write_text(conftest, encoding="utf-8")

    for ds, sort_key in SORT_KEYS.items():
        lib, name = ds.split(".", 1)
        path = TESTS_DIR / f"test_{lib}_{name}.py"
        sort_cols = _parse_sort_key(sort_key)
        body = f'''"""Row-for-row equality test for `{ds}`.

Auto-generated by Phase 4 from the spec acceptance criteria. Compares
build/target/output/{name}.csv against ground_truth/{name}.csv.
"""
import pandas as pd
import pytest


SORT_KEY = {sort_cols!r}
DATASET = "{ds}"


def _read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Round float-like incidence_rate to 4dp string; otherwise pass through."""
    if "INCIDENCE_RATE" in df.columns:
        def _r(v):
            v = (v or "").strip()
            if v == "":
                return ""
            try:
                return f"{{round(float(v), 4):g}}"
            except ValueError:
                return v
        df = df.copy()
        df["INCIDENCE_RATE"] = df["INCIDENCE_RATE"].map(_r)
    return df


def _stable_sort(df: pd.DataFrame, key: list) -> pd.DataFrame:
    sort_cols = [c for c in key if c in df.columns]
    if not sort_cols:
        return df.reset_index(drop=True)
    return df.sort_values(by=sort_cols, kind="mergesort", na_position="first").reset_index(drop=True)


def test_schema_match(target_output_dir, ground_truth_dir):
    gen = _read(target_output_dir / "{name}.csv")
    truth = _read(ground_truth_dir / "{name}.csv")
    assert list(gen.columns) == list(truth.columns), (
        f"column order differs:\\n  generated: {{list(gen.columns)}}\\n  truth:     {{list(truth.columns)}}"
    )


def test_row_count(target_output_dir, ground_truth_dir):
    gen = _read(target_output_dir / "{name}.csv")
    truth = _read(ground_truth_dir / "{name}.csv")
    assert len(gen) == len(truth), f"row count: gen={{len(gen)}}, truth={{len(truth)}}"


def test_row_for_row_equality(target_output_dir, ground_truth_dir):
    gen = _normalize(_read(target_output_dir / "{name}.csv"))
    truth = _normalize(_read(ground_truth_dir / "{name}.csv"))
    gen_sorted = _stable_sort(gen, SORT_KEY)
    truth_sorted = _stable_sort(truth, SORT_KEY)
    assert list(gen_sorted.columns) == list(truth_sorted.columns)
    diff_rows = []
    for i, (g_row, t_row) in enumerate(zip(gen_sorted.itertuples(index=False),
                                              truth_sorted.itertuples(index=False))):
        if g_row != t_row:
            diff_rows.append((i, g_row, t_row))
    assert not diff_rows, "row mismatches:\\n" + "\\n".join(
        f"  row {{i}}:\\n    gen   = {{g}}\\n    truth = {{t}}" for i, g, t in diff_rows[:10]
    )
'''
        path.write_text(body, encoding="utf-8")


def _parse_sort_key(text: str) -> list[str]:
    """Convert a SORT_KEYS value like 'USUBJID, AESEQ' to ['USUBJID', 'AESEQ']."""
    cols: list[str] = []
    for tok in text.split(","):
        tok = tok.strip()
        if not tok:
            continue
        # strip parenthetical comments
        tok = tok.split("(")[0].strip()
        cols.append(tok)
    return cols


# ============================================================================
# Driver
# ============================================================================

def main() -> None:
    g = _load_graph()
    emit_schemas(g)
    emit_specs(g)
    emit_dag()
    emit_tests()
    print("phase 4 outputs written:")
    print(f"  specs   : {len(list(SPECS_DIR.glob('*.md')))} files")
    print(f"  schemas : {len(list(SCHEMAS_DIR.glob('*.py')))} files")
    print(f"  tests   : {len(list(TESTS_DIR.glob('test_*.py')))} files")
    print(f"  dag     : build/dag/pipeline.json")


if __name__ == "__main__":
    main()
