# SAS Modernization Solution Design Specification

> This is the team's design document, included verbatim for reference by
> Claude Code. The operating instructions in `CLAUDE.md` implement the
> pipeline described here.

## 1. Summary

This solution defines a GenAI-assisted, semantics-preserving SAS
modernization approach that transforms legacy SAS code into a modern data
platform implementation in a controlled, explainable, and verifiable
manner.

Rather than directly rewriting SAS code, the solution first reconstructs
technical structure, lineage, intent, and behavioral contracts from the
source code. These artifacts are then used to drive target-state code
generation and validation, minimizing semantic drift and operational risk.

## 2. Goals / Non-Goals

### 2.1 Goals
- Safely modernize SAS workloads while preserving business and data semantics
- Make legacy SAS logic understandable, explainable, and auditable
- Use GenAI to accelerate understanding and refactoring, not to guess behavior
- Provide objective validation of modernization results
- Establish a repeatable modernization factory, not a one-off migration

### 2.2 Non-Goals
- Blind or regex-based SAS-to-SQL rewriting
- Full SAS runtime emulation
- Performance tuning or cost optimization in the MVP phase
- Automatic resolution of ambiguous business logic
- One-click modernization without human validation

## 3. Pipeline (5 phases)

```
SAS Codebase          Documentation
     |                       |
     v                       v
AST + CFG Parser       Doc NLP Pipeline
     |                       |
     +-----------+-----------+
                 v
          Knowledge Graph
       (datasets, columns, procs,
        macros, dependencies, lineage)
                 |
     +-----------+-----------+-----------+
     v           v           v           v
  Spec docs  Data schema  Lineage/   Test stubs
                          DAG
     +-----------+-----------+-----------+
                 v
          AI pair programmer
         (spec-driven codegen)
                 v
           PySpark codebase
```

### Phase 1 — Parse the codebase into a graph
Build a two-pass parser: first a macro expander (`%let`, `%macro`/`%mend`,
`%include`, symbol tables), then an AST over the expanded output. Derive
a Control Flow Graph per program and a cross-program Data Flow Graph
(what each step reads and writes). Together they give column-level lineage
without running anything.

### Phase 2 — Parse documentation into the same graph
Connect doc entities back to code entities. A spec saying "the
CLAIMS_CLEAN dataset must never contain nulls in MEMBER_ID" becomes an
edge from the dataset node to a constraint node. Use an LLM (with
structured output) to extract dataset and column mentions, business rules,
SLAs, and ownership. Chunk by logical section, not by token count.

### Phase 3 — Build the knowledge graph
Node types: Dataset, Column, Proc, Macro, Variable, BusinessRule, Owner.
Edge types: reads, writes, calls, depends_on, implements, validates.
The graph is the single source of truth — queryable and auditable.
Every downstream artifact is generated from graph queries, not from
re-parsing source.

### Phase 4 — Regenerate artifacts from the graph
- **Functional specs**: one markdown per logical job
- **Data schemas**: Spark StructType (or Delta DDL) with nullability
- **Execution DAG**: Airflow or Databricks Workflows compatible
- **Test stubs**: pytest fixtures with golden Parquet files

### Phase 5 — AI pair programming from specs
Feed the regenerated spec to the codegen step, not raw SAS. Prompt
structure: system prompt (PySpark coding standards), then functional spec,
then input/output schemas, then "implement this as a PySpark job". The
human engineer reviews and iterates; the AI does not need to understand
SAS at all.

## 4. Risks called out by the spec
- Macro side effects and dynamic code generation
- Implicit DATA step loops, BY-group semantics
- Missing vs NULL vs blank handling
- Implicit type casting, date/time format dependencies
- Silent semantic drift during transformation
- Over-interpretation by GenAI
