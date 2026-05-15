# Coverage report — SAS constructs handled by the parser

This report enumerates what the hand-rolled parser at `build/parser/` does
and does not cover. It is written in service of CLAUDE.md R5 ("Be honest
about what the synthetic codebase represents") so a reader knows where the
MVP would extend or break against a real client SAS estate.

## 1. Constructs handled

### DATA step
- `data <out>;` head with one or more output libraries
- `set <in>;` and `merge <a>(in=x) <b>(in=y);` (input-dataset extraction)
- `by <vars>;` (BY-group processing markers in CFG)
- `if <cond> then delete;` (filter detection)
- assignments `<col> = <expr>;` (LHS column write captured)
- if-then-else assignments (`if x then col=a; else col=b;`)
- SAS sum statement `<col> + <expr>;` (retain + add)
- `length <cols> $N;`, `format <cols> <fmt>;`, `label <col>='...';`
- `keep <cols>;`, `drop <cols>;`, `retain <var>;`, `rename old=new;`

### PROC blocks
- **`proc sort`** — input/output datasets, `by` keys
- **`proc sql`** — `create table <out> as select … from … [join … on …] [where …] [group by …] [order by …];`, `select … into :var` (macro var write)
- **`proc summary`** — `class` and `output out=` capture
- **`proc format`** — `value [$]<name> …` definitions registered

### Macros
- `%let var = value;` (incl. nested expansion)
- `%macro name(p1=, p2=v); body %mend;` (sibling macros — not nested defs)
- `%name(arg=val)` invocation with textual parameter substitution
- `&var` and `&var.` references with iterated fixpoint expansion
- `%include "path"` with project-root-relative resolution
- Macro reads/writes-globals scan: any unresolved `&var` in a body → reads;
  any `into :var` or `%let &var` → writes (catches cross-program coupling)

## 2. Constructs NOT handled (and why it doesn't matter for this codebase)

| Construct                                | Where used in this codebase | Status      |
| ---------------------------------------- | --------------------------- | ----------- |
| `%sysfunc(...)`                          | `setup.sas:16` (PROJ_ROOT)  | Left literal — only feeds `libname` and `%include`, both resolved by the parser via project-root candidates. Cosmetic. |
| Dynamic `&&var` / triple-amp references  | none                        | Not present — no work needed. |
| `%do … %end;` loops, `%eval`             | none                        | Not present — no work needed. |
| `proc datasets`, `proc transpose`, etc.  | none                        | Not present. Adding them requires extending the per-PROC handler list in `sas_parser.py::build_ast`. |
| PROC SQL passthrough (DBMS-specific)     | none                        | Not present. |
| Stored compiled macros (`mstored`)       | none                        | Not present. |
| User-written FCMP functions              | none                        | Not present. |
| `array … _temporary_;` and `do over`     | none                        | Not present. |

## 3. Constructs the *modernization pipeline* explicitly chooses not to map

| Topic                                | Decision                                                                            |
| ------------------------------------ | ----------------------------------------------------------------------------------- |
| `proc format` value-mapping codegen | Hard-coded into `build/target/common.py` (`SEX_DECODE_MAP`, `ARM_DECODE_MAP`) and `01_clean_dm.py` (`agegrp` function). A production rollout should auto-emit these from the parsed PROC FORMAT (already in `build/ast/_aggregate/`). |
| `options` statement                  | Ignored — affects SAS-only behavior (mprint, missing) with no Python equivalent.    |
| `libname` statement                  | Ignored — paths are project-relative in the modernized pipeline.                    |
| Vendor B `GRADE n` severity codes    | Intentionally NOT mapped (per spec §6.2 / SP-184) — preserves ground-truth blank rows. |
| TRTEMFL semantic discrepancy         | Resolved per ambiguity #1 to match running implementation, not spec-text literal.   |

## 4. What changes for production rollout

Even on a faithful parser, these realistic constructs would need work
beyond what is in this MVP. See SOLUTION.md §1.9 for the broader
recommendations; here are the parser-specific items:

1. Replace the hand-rolled parser with **tree-sitter SAS** (or ANTLR with
   a published grammar) once a real codebase introduces `%do %while`,
   `%eval`, `&&var`, or PROC SQL CTEs.
2. Add explicit handling for `proc datasets`, `proc transpose`,
   `proc means/freq/univariate`, and `proc tabulate` outputs.
3. Build a real macro evaluator (not just textual substitution) to handle
   `%sysfunc`, `%let` with macro expressions, conditional `%if` blocks
   that suppress code generation, and recursive macros.
4. Treat `libname` statements as configuration metadata to inform the
   physical storage of generated outputs (e.g., bucket prefixes).
5. Build PROC SQL into a proper SQL AST (not just regex-based `as <alias>`
   extraction) so column-level lineage is exact rather than heuristic.
