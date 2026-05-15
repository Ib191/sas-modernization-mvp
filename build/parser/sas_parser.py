"""SAS parser: tokenize, expand macros, build a structural AST.

The parser is intentionally pragmatic: it is statement-level (split on `;`),
identifies blocks (`data ... run;`, `proc ... run;|quit;`, `%macro ... %mend;`),
and extracts the dataset/column reads and writes needed for the downstream
flow graphs and knowledge graph. It is NOT a faithful SAS evaluator.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# 1. Comment stripping
# ---------------------------------------------------------------------------

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
# Star-line comments in SAS are statement-level: a line starting with `*`
# (after whitespace) until the next `;`. Keep this conservative so we don't
# eat real expressions.
_STAR_COMMENT = re.compile(r"(?m)^\s*\*[^;]*;")


def strip_comments(source: str) -> str:
    s = _BLOCK_COMMENT.sub(" ", source)
    s = _STAR_COMMENT.sub(" ", s)
    # SAS allows `%mend` to follow an expression with no preceding semicolon
    # (the macro body's last expression doesn't need to be a complete
    # statement). Inject one so split_statements sees `%mend` cleanly.
    s = re.sub(r"(?i)(?<![;\s])\s*%mend\b", "; %mend", s)
    return s


# ---------------------------------------------------------------------------
# 2. Statement splitting (respecting string literals)
# ---------------------------------------------------------------------------

def split_statements(source: str) -> list[tuple[int, str]]:
    """Split SAS source into (line_number, statement_text) tuples.

    A statement ends at `;` outside of single- or double-quoted strings.
    Line numbers refer to the line where the statement *starts* in the
    original source.
    """
    out: list[tuple[int, str]] = []
    buf: list[str] = []
    line_no = 1
    start_line = 1
    in_single = False
    in_double = False
    for ch in source:
        if ch == "\n":
            line_no += 1
        if not in_double and ch == "'":
            in_single = not in_single
        elif not in_single and ch == '"':
            in_double = not in_double
        if ch == ";" and not in_single and not in_double:
            stmt = "".join(buf).strip()
            if stmt:
                out.append((start_line, stmt))
            buf = []
            start_line = line_no
            continue
        if not buf and ch.strip() == "":
            # absorb leading whitespace; track line number instead
            if ch == "\n":
                start_line = line_no
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        out.append((start_line, tail))
    return out


# ---------------------------------------------------------------------------
# 3. Macro symbol table + expansion (Pass A)
# ---------------------------------------------------------------------------

@dataclass
class MacroDef:
    name: str
    params: list[tuple[str, Optional[str]]]  # (name, default)
    body: str
    source_file: str
    source_line: int
    reads_globals: list[str] = field(default_factory=list)
    writes_globals: list[str] = field(default_factory=list)


@dataclass
class MacroCallSite:
    macro: str
    file: str
    line: int
    arg_text: str


# Identifier patterns (SAS-style: letters, digits, underscores; not starting
# with a digit). Macro vars allowed to be any identifier.
_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"

_MACRO_DEF_HEAD = re.compile(
    rf"^%macro\s+({_IDENT})\s*(?:\(([^)]*)\))?\s*$",
    re.IGNORECASE,
)
_LET_STMT = re.compile(
    rf"^%let\s+({_IDENT})\s*=\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_INCLUDE_STMT = re.compile(
    r"^%include\s+(?P<q>['\"])(.+?)(?P=q)\s*$",
    re.IGNORECASE,
)
_MACRO_INVOKE = re.compile(
    rf"%({_IDENT})\s*\(([^()]*)\)",
)
_MACRO_VAR = re.compile(r"&(\.?){0}".format(""))  # placeholder, real one below
_MACRO_VAR = re.compile(rf"&({_IDENT})\.?")
_INTO_VAR = re.compile(rf"\binto\s*:\s*({_IDENT})", re.IGNORECASE)


def _split_args(arg_text: str) -> dict[str, str]:
    """Split `a=1, b=foo` into {a: '1', b: 'foo'}. Positional args become
    `__pos<i>__`; this codebase uses keyword args exclusively."""
    out: dict[str, str] = {}
    if not arg_text.strip():
        return out
    parts = [p.strip() for p in arg_text.split(",") if p.strip()]
    for i, p in enumerate(parts):
        if "=" in p:
            k, v = p.split("=", 1)
            out[k.strip().lower()] = v.strip()
        else:
            out[f"__pos{i}__"] = p.strip()
    return out


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
    # Dedup preserving order
    reads = list(dict.fromkeys(reads))
    writes = list(dict.fromkeys(writes))
    return reads, writes


class MacroTable:
    def __init__(self) -> None:
        self.symbols: dict[str, str] = {}        # %let symbols (lowercased keys)
        self.macros: dict[str, MacroDef] = {}    # %macro defs
        self.call_sites: list[MacroCallSite] = []

    def let(self, var: str, value: str) -> None:
        self.symbols[var.lower()] = value

    def define(self, m: MacroDef) -> None:
        self.macros[m.name.lower()] = m

    def expand_vars(self, text: str) -> str:
        """Substitute `&var` / `&var.` by symbol-table value. Unknown vars
        are left as-is (they may be set at runtime, e.g. &TRT_START_DT)."""
        def repl(match: re.Match[str]) -> str:
            name = match.group(1).lower()
            if name in self.symbols:
                return self.symbols[name]
            return match.group(0)
        prev = None
        cur = text
        # iterate to a fixpoint to handle nested refs
        while prev != cur:
            prev = cur
            cur = _MACRO_VAR.sub(repl, cur)
        return cur

    def expand_calls(self, text: str, *, file: str, line: int) -> str:
        """Substitute `%name(args)` invocations by their macro body, with
        parameters textually replaced. Iterates to handle nested calls."""
        prev = None
        cur = text
        while prev != cur:
            prev = cur

            def repl(match: re.Match[str]) -> str:
                name = match.group(1).lower()
                if name not in self.macros:
                    return match.group(0)
                args = _split_args(match.group(2))
                m = self.macros[name]
                self.call_sites.append(
                    MacroCallSite(macro=m.name, file=file, line=line,
                                  arg_text=match.group(2))
                )
                body = m.body
                # Resolve params (with defaults) and substitute &param
                merged: dict[str, str] = {}
                for pname, pdef in m.params:
                    merged[pname.lower()] = pdef if pdef is not None else ""
                merged.update(args)
                for pname, pval in merged.items():
                    body = re.sub(
                        rf"&{re.escape(pname)}\.?",
                        pval,
                        body,
                        flags=re.IGNORECASE,
                    )
                return f"({body})"

            cur = _MACRO_INVOKE.sub(repl, cur)
        return cur


# ---------------------------------------------------------------------------
# 4. Two-pass driver: macro expansion, then structural AST
# ---------------------------------------------------------------------------

@dataclass
class Block:
    kind: str                                 # 'data' | 'proc' | 'macro_def' | 'misc'
    proc_name: Optional[str]                  # for kind=='proc'
    output_datasets: list[str] = field(default_factory=list)
    input_datasets: list[str] = field(default_factory=list)
    statements: list[dict] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0
    raw_text: str = ""
    name: Optional[str] = None                # for macro_def


@dataclass
class ProgramAST:
    program: str                              # filename stem, e.g. '01_clean_dm'
    source_file: str                          # full path
    blocks: list[Block] = field(default_factory=list)
    expanded_source: str = ""
    macro_call_sites: list[MacroCallSite] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)


# ---- Statement classifiers ------------------------------------------------

_DATA_HEAD = re.compile(rf"^data\s+(.+)$", re.IGNORECASE | re.DOTALL)
_PROC_HEAD = re.compile(rf"^proc\s+({_IDENT})\b(.*)$", re.IGNORECASE | re.DOTALL)
_RUN_QUIT = re.compile(r"^(run|quit)\b", re.IGNORECASE)
_SET_STMT = re.compile(rf"^set\s+(.+)$", re.IGNORECASE | re.DOTALL)
_MERGE_STMT = re.compile(rf"^merge\s+(.+)$", re.IGNORECASE | re.DOTALL)
_BY_STMT = re.compile(rf"^by\s+(.+)$", re.IGNORECASE | re.DOTALL)
_KEEP_STMT = re.compile(rf"^keep\s+(.+)$", re.IGNORECASE | re.DOTALL)
_DROP_STMT = re.compile(rf"^drop\s+(.+)$", re.IGNORECASE | re.DOTALL)
_LENGTH_STMT = re.compile(rf"^length\s+(.+)$", re.IGNORECASE | re.DOTALL)
_LABEL_STMT = re.compile(rf"^label\s+(.+)$", re.IGNORECASE | re.DOTALL)
_FORMAT_STMT = re.compile(rf"^format\s+(.+)$", re.IGNORECASE | re.DOTALL)
_RETAIN_STMT = re.compile(rf"^retain\s+(.+)$", re.IGNORECASE | re.DOTALL)
_RENAME_STMT = re.compile(rf"^rename\s+(.+)$", re.IGNORECASE | re.DOTALL)
_IF_DELETE = re.compile(r"^if\s+.+\s+then\s+delete\b", re.IGNORECASE | re.DOTALL)
_ASSIGN_STMT = re.compile(
    rf"^({_IDENT})\s*(?:\+\s*)?=\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_IF_THEN_ASSIGN = re.compile(
    rf"^if\s+(.+?)\s+then\s+({_IDENT})\s*=\s*(.+?)(?:\s*;\s*else\s+({_IDENT})?\s*=\s*(.+))?$",
    re.IGNORECASE | re.DOTALL,
)

_DATAREF = re.compile(rf"({_IDENT}\.{_IDENT}|{_IDENT})(?:\s*\([^)]*\))?")


def _strip_options(text: str) -> str:
    """Remove `(in=x ...)` / `(keep=...)` style dataset options."""
    return re.sub(r"\([^()]*\)", "", text)


def _collect_data_refs(text: str) -> list[str]:
    """Extract dataset references like `adam.dm_clean` or `work.dm_stage`.
    Returns lowercased names."""
    out: list[str] = []
    for m in _DATAREF.finditer(_strip_options(text)):
        token = m.group(1).lower()
        # skip pure keywords
        if token in {"data", "proc", "set", "merge", "by", "from", "as"}:
            continue
        out.append(token)
    return out


def _split_keep_drop(text: str) -> list[str]:
    parts = re.split(r"\s+", text.strip())
    return [p.lower() for p in parts if p]


def _data_head_targets(head_args: str) -> list[str]:
    """`data adam.dm_clean(label='...');` -> ['adam.dm_clean']."""
    out: list[str] = []
    for tok in head_args.split():
        tok = tok.split("(")[0].strip()
        if tok:
            out.append(tok.lower())
    return out


def _proc_data_in(head_args: str) -> tuple[Optional[str], Optional[str]]:
    """Extract `data=X out=Y` from PROC head args."""
    data_m = re.search(rf"data\s*=\s*({_IDENT}(?:\.{_IDENT})?)", head_args, re.IGNORECASE)
    out_m = re.search(rf"out\s*=\s*({_IDENT}(?:\.{_IDENT})?)", head_args, re.IGNORECASE)
    d = data_m.group(1).lower() if data_m else None
    o = out_m.group(1).lower() if out_m else None
    return d, o


# ---------------------------------------------------------------------------
# 5. PROC SQL parsing
# ---------------------------------------------------------------------------

_SQL_CREATE = re.compile(
    rf"create\s+table\s+({_IDENT}(?:\.{_IDENT})?)\s+as\s+(select\s+.+)$",
    re.IGNORECASE | re.DOTALL,
)
_SQL_FROM = re.compile(
    rf"\bfrom\s+({_IDENT}(?:\.{_IDENT})?)(?:\s+as\s+{_IDENT})?",
    re.IGNORECASE,
)
_SQL_JOIN = re.compile(
    rf"\b(?:left\s+|right\s+|inner\s+|full\s+)?join\s+({_IDENT}(?:\.{_IDENT})?)(?:\s+as\s+{_IDENT})?",
    re.IGNORECASE,
)
_SQL_INTO = re.compile(rf"\binto\s*:\s*({_IDENT})", re.IGNORECASE)


def _parse_sql_block(stmts: list[tuple[int, str]]) -> list[dict]:
    """Parse the inside of a PROC SQL ... QUIT block. Returns a list of
    dict statements: {kind, target, sources, into_macro_var, raw}."""
    out: list[dict] = []
    for line_no, s in stmts:
        sl = s.lower().lstrip()
        if sl.startswith("create"):
            m = _SQL_CREATE.match(s.strip())
            if m:
                target = m.group(1).lower()
                sources = [x.lower() for x in _SQL_FROM.findall(s)]
                joins = [x.lower() for x in _SQL_JOIN.findall(s)]
                out.append({
                    "kind": "sql_create_table",
                    "target": target,
                    "from": sources,
                    "join": joins,
                    "into_macro_var": None,
                    "line": line_no,
                    "raw": s,
                })
                continue
        if sl.startswith("select"):
            into = _SQL_INTO.search(s)
            sources = [x.lower() for x in _SQL_FROM.findall(s)]
            joins = [x.lower() for x in _SQL_JOIN.findall(s)]
            out.append({
                "kind": "sql_select",
                "target": None,
                "from": sources,
                "join": joins,
                "into_macro_var": into.group(1) if into else None,
                "line": line_no,
                "raw": s,
            })
            continue
        # noprint, quit handled by outer
    return out


# ---------------------------------------------------------------------------
# 6. Pass A: macro expansion
# ---------------------------------------------------------------------------

def _resolve_include_path(arg: str, base_dir: Path, project_root: Path) -> Optional[Path]:
    arg = arg.replace("&PROJ_ROOT/", "").replace("&PROJ_ROOT.", "")
    arg = arg.replace("&PROJ_ROOT", "")
    arg = arg.lstrip("/").lstrip("\\")
    candidates = [
        project_root / arg,
        base_dir / arg,
        base_dir.parent / arg,
        # programs/ live one dir below sas_codebase/, %include "config/setup.sas" must
        # resolve relative to sas_codebase/
        project_root / "sas_codebase" / arg,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def expand_macros(
    source: str,
    *,
    file_path: Path,
    macro_table: MacroTable,
    project_root: Path,
    visited_includes: Optional[set[str]] = None,
) -> str:
    """Pass A. Returns expanded source. Mutates macro_table with discovered
    %let symbols, %macro defs, and call sites. Includes are inlined."""
    visited = visited_includes if visited_includes is not None else set()
    src = strip_comments(source)
    # first pass: handle %include / %let / %macro at the statement level
    stmts = split_statements(src)
    out_parts: list[str] = []
    i = 0
    while i < len(stmts):
        line_no, s = stmts[i]
        s_stripped = s.strip()
        # %include "path"
        m_inc = _INCLUDE_STMT.match(s_stripped)
        if m_inc:
            inc_arg = m_inc.group(2)
            # expand any &PROJ_ROOT etc first
            inc_arg = macro_table.expand_vars(inc_arg)
            inc_path = _resolve_include_path(inc_arg, file_path.parent, project_root)
            if inc_path and str(inc_path) not in visited:
                visited.add(str(inc_path))
                inc_text = inc_path.read_text(encoding="utf-8")
                # recursive expansion of the included file
                expanded_inc = expand_macros(
                    inc_text,
                    file_path=inc_path,
                    macro_table=macro_table,
                    project_root=project_root,
                    visited_includes=visited,
                )
                out_parts.append(f"/* %include {inc_path.name} expanded */")
                out_parts.append(expanded_inc)
            i += 1
            continue
        # %let var = value;
        m_let = _LET_STMT.match(s_stripped)
        if m_let:
            var = m_let.group(1)
            val = macro_table.expand_vars(m_let.group(2).strip())
            # %let value may use %sysfunc(...) — leave literal but record
            macro_table.let(var, val)
            out_parts.append(f"%let {var} = {val};")
            i += 1
            continue
        # %macro name(params); ... %mend;
        m_def = _MACRO_DEF_HEAD.match(s_stripped)
        if m_def:
            mname = m_def.group(1)
            mparams_text = m_def.group(2) or ""
            # Collect body up to next %mend. SAS allows nested macros, but
            # this codebase uses only sibling top-level macros, so we stop
            # at the first %mend rather than tracking depth.
            body_parts: list[str] = []
            j = i + 1
            while j < len(stmts):
                _, t = stmts[j]
                if re.match(r"^\s*%mend\b", t, re.IGNORECASE):
                    break
                body_parts.append(t)
                j += 1
            body = "; ".join(body_parts).strip()
            # parse params: `var=` or `var=default`
            params: list[tuple[str, Optional[str]]] = []
            for p in mparams_text.split(","):
                p = p.strip()
                if not p:
                    continue
                if "=" in p:
                    k, v = p.split("=", 1)
                    params.append((k.strip(), v.strip() if v.strip() else None))
                else:
                    params.append((p, None))
            reads, writes = _scan_macro_globals(
                body, [p[0] for p in params]
            )
            mdef = MacroDef(
                name=mname,
                params=params,
                body=body,
                source_file=str(file_path),
                source_line=line_no,
                reads_globals=reads,
                writes_globals=writes,
            )
            macro_table.define(mdef)
            out_parts.append(f"/* %macro {mname} registered ({len(params)} params) */")
            i = j + 1  # skip past %mend
            continue
        # %put — leave as-is (no semantic effect for our parser)
        if re.match(r"^\s*%put\b", s_stripped, re.IGNORECASE):
            out_parts.append(s_stripped + ";")
            i += 1
            continue
        # %if / %symexist — leave inline (cosmetic in this codebase)
        if re.match(r"^\s*%(if|do|end|symexist)\b", s_stripped, re.IGNORECASE):
            out_parts.append(s_stripped + ";")
            i += 1
            continue
        # Default: substitute macro vars and macro calls inline
        s_expanded = macro_table.expand_vars(s_stripped)
        s_expanded = macro_table.expand_calls(
            s_expanded, file=str(file_path), line=line_no
        )
        out_parts.append(s_expanded + ";")
        i += 1
    return "\n".join(out_parts)


# ---------------------------------------------------------------------------
# 7. Pass B: structural AST from expanded source
# ---------------------------------------------------------------------------

def build_ast(expanded: str, *, program_name: str, source_file: str) -> ProgramAST:
    ast = ProgramAST(program=program_name, source_file=source_file,
                     expanded_source=expanded)
    stmts = split_statements(strip_comments(expanded))

    i = 0
    while i < len(stmts):
        line_no, s = stmts[i]
        s_stripped = s.strip()
        sl = s_stripped.lower()

        # DATA step
        m_data = _DATA_HEAD.match(s_stripped)
        if m_data:
            head_args = m_data.group(1)
            targets = _data_head_targets(head_args)
            blk = Block(kind="data", proc_name=None, line_start=line_no,
                         output_datasets=targets, raw_text=s_stripped)
            i += 1
            while i < len(stmts):
                ln2, t = stmts[i]
                if _RUN_QUIT.match(t.strip()):
                    blk.line_end = ln2
                    i += 1
                    break
                _absorb_data_stmt(blk, t, ln2)
                i += 1
            ast.blocks.append(blk)
            continue

        # PROC block
        m_proc = _PROC_HEAD.match(s_stripped)
        if m_proc:
            pname = m_proc.group(1).lower()
            head_args = m_proc.group(2) or ""
            data_in, out_ds = _proc_data_in(head_args)
            blk = Block(kind="proc", proc_name=pname, line_start=line_no,
                         raw_text=s_stripped)
            if data_in:
                blk.input_datasets.append(data_in)
            if out_ds:
                blk.output_datasets.append(out_ds)
            i += 1
            inner: list[tuple[int, str]] = []
            while i < len(stmts):
                ln2, t = stmts[i]
                if _RUN_QUIT.match(t.strip()):
                    blk.line_end = ln2
                    i += 1
                    break
                inner.append((ln2, t))
                i += 1
            if pname == "sql":
                sql_stmts = _parse_sql_block(inner)
                blk.statements.extend(sql_stmts)
                # roll up inputs/outputs from sql substatements
                for st in sql_stmts:
                    if st["target"]:
                        blk.output_datasets.append(st["target"])
                    blk.input_datasets.extend(st["from"])
                    blk.input_datasets.extend(st["join"])
            elif pname == "summary":
                _absorb_summary_block(blk, inner)
            elif pname == "sort":
                _absorb_sort_block(blk, inner)
            elif pname == "format":
                _absorb_format_block(blk, inner)
            else:
                for ln2, t in inner:
                    blk.statements.append({"kind": "raw", "raw": t, "line": ln2})
            # dedup
            blk.input_datasets = list(dict.fromkeys(blk.input_datasets))
            blk.output_datasets = list(dict.fromkeys(blk.output_datasets))
            ast.blocks.append(blk)
            continue

        # Top-level misc statement (options, libname, %put, %let after expansion)
        ast.blocks.append(Block(
            kind="misc", proc_name=None, line_start=line_no, line_end=line_no,
            raw_text=s_stripped,
        ))
        i += 1

    return ast


def _absorb_data_stmt(blk: Block, stmt: str, line_no: int) -> None:
    s = stmt.strip()
    sl = s.lower()
    if (m := _SET_STMT.match(s)):
        for ds in _collect_data_refs(m.group(1)):
            blk.input_datasets.append(ds)
        blk.statements.append({"kind": "set", "raw": s, "line": line_no})
        return
    if (m := _MERGE_STMT.match(s)):
        for ds in _collect_data_refs(m.group(1)):
            blk.input_datasets.append(ds)
        blk.statements.append({"kind": "merge", "raw": s, "line": line_no})
        return
    if _BY_STMT.match(s):
        blk.statements.append({"kind": "by", "raw": s, "line": line_no})
        return
    if (m := _KEEP_STMT.match(s)):
        cols = _split_keep_drop(m.group(1))
        blk.statements.append({"kind": "keep", "cols": cols, "line": line_no, "raw": s})
        return
    if (m := _DROP_STMT.match(s)):
        cols = _split_keep_drop(m.group(1))
        blk.statements.append({"kind": "drop", "cols": cols, "line": line_no, "raw": s})
        return
    if _LENGTH_STMT.match(s):
        blk.statements.append({"kind": "length", "raw": s, "line": line_no})
        return
    if _LABEL_STMT.match(s):
        blk.statements.append({"kind": "label", "raw": s, "line": line_no})
        return
    if _FORMAT_STMT.match(s):
        blk.statements.append({"kind": "format", "raw": s, "line": line_no})
        return
    if _RETAIN_STMT.match(s):
        blk.statements.append({"kind": "retain", "raw": s, "line": line_no})
        return
    if (m := _RENAME_STMT.match(s)):
        blk.statements.append({"kind": "rename", "raw": s, "line": line_no})
        return
    if _IF_DELETE.match(s):
        blk.statements.append({"kind": "if_delete", "raw": s, "line": line_no})
        return
    if (m := _IF_THEN_ASSIGN.match(s)):
        col = m.group(2).lower()
        expr = m.group(3).strip()
        else_col = (m.group(4) or "").lower() or col
        else_expr = (m.group(5) or "").strip()
        blk.statements.append({
            "kind": "if_assign",
            "col": col, "expr": expr,
            "else_col": else_col or None,
            "else_expr": else_expr or None,
            "line": line_no, "raw": s,
        })
        return
    if (m := _ASSIGN_STMT.match(s)):
        col = m.group(1).lower()
        expr = m.group(2).strip()
        kind = "sum_assign" if "+ =" in s.replace(" ", "+ =") or re.match(rf"^{_IDENT}\s*\+", s) else "assign"
        # detect SAS sum statement: `aeseq + 1;` => sum statement
        if re.match(rf"^{_IDENT}\s*\+\s*[^=]", s) and "=" not in s:
            blk.statements.append({"kind": "sum", "col": col, "raw": s, "line": line_no})
            return
        blk.statements.append({"kind": kind, "col": col, "expr": expr,
                               "line": line_no, "raw": s})
        return
    blk.statements.append({"kind": "raw", "raw": s, "line": line_no})


def _absorb_sort_block(blk: Block, inner: list[tuple[int, str]]) -> None:
    for ln, t in inner:
        if _BY_STMT.match(t.strip()):
            blk.statements.append({"kind": "by", "raw": t, "line": ln})
        else:
            blk.statements.append({"kind": "raw", "raw": t, "line": ln})


def _absorb_summary_block(blk: Block, inner: list[tuple[int, str]]) -> None:
    for ln, t in inner:
        ts = t.strip()
        tsl = ts.lower()
        if tsl.startswith("class"):
            blk.statements.append({"kind": "class", "raw": ts, "line": ln,
                                    "cols": _split_keep_drop(ts[5:])})
        elif tsl.startswith("output"):
            m = re.search(rf"out\s*=\s*({_IDENT}(?:\.{_IDENT})?)", ts, re.IGNORECASE)
            if m:
                blk.output_datasets.append(m.group(1).lower())
            blk.statements.append({"kind": "output", "raw": ts, "line": ln})
        else:
            blk.statements.append({"kind": "raw", "raw": ts, "line": ln})


def _absorb_format_block(blk: Block, inner: list[tuple[int, str]]) -> None:
    """PROC FORMAT — capture each `value` as a format definition."""
    for ln, t in inner:
        ts = t.strip()
        if re.match(r"^value\b", ts, re.IGNORECASE):
            m = re.match(rf"^value\s+(\$?{_IDENT})\s+(.*)$", ts, re.IGNORECASE | re.DOTALL)
            if m:
                blk.statements.append({
                    "kind": "format_def",
                    "name": m.group(1).lower(),
                    "body": m.group(2).strip(),
                    "line": ln, "raw": ts,
                })
                continue
        blk.statements.append({"kind": "raw", "raw": ts, "line": ln})


# ---------------------------------------------------------------------------
# 8. Public entry point
# ---------------------------------------------------------------------------

def parse_program(file_path: Path, *, project_root: Path,
                  shared_macro_table: MacroTable) -> ProgramAST:
    """Top-level: expand macros (Pass A), build AST (Pass B)."""
    raw = file_path.read_text(encoding="utf-8")
    expanded = expand_macros(
        raw, file_path=file_path, macro_table=shared_macro_table,
        project_root=project_root,
    )
    ast = build_ast(expanded, program_name=file_path.stem,
                    source_file=str(file_path))
    ast.macro_call_sites = list(shared_macro_table.call_sites)
    return ast


def ast_to_dict(ast: ProgramAST) -> dict:
    """Make ProgramAST JSON-serializable."""
    return {
        "program": ast.program,
        "source_file": ast.source_file,
        "blocks": [
            {
                "kind": b.kind,
                "proc_name": b.proc_name,
                "name": b.name,
                "output_datasets": b.output_datasets,
                "input_datasets": b.input_datasets,
                "statements": b.statements,
                "line_start": b.line_start,
                "line_end": b.line_end,
                "raw_text_head": b.raw_text[:160],
            }
            for b in ast.blocks
        ],
        "includes": ast.includes,
        "macro_call_sites": [asdict(c) for c in ast.macro_call_sites],
    }
