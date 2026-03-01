from ast_nodes import Program, ProcDecl, FuncDecl, IncbinDirective, StructDef
from symbols import SymbolTable, ProcTable, FuncTable, StructRegistry, Symbol, SemType, StructInfo
from sema import DeclarationAnalyzer, StructAnalyzer, EnumAnalyzer
from sema_expr import ExprTypeChecker
from sema_proc import ProcAnalyzer
from sema_func import FuncAnalyzer
from codegen_expr import CodeGen
from dce import dce_block
from errors import SemanticError
from collections import deque
from typing import Optional, Set, Dict, Tuple, List, Any


def _walk_expr(expr, ctx, global_symtab):
    """Walk an expression and record global usage and calls."""
    from ast_nodes import (
        IntLiteral, StringLiteral, Identifier, BinaryExpr, UnaryExpr, DerefExpr,
        SubscriptExpr, CallExpr, FieldAccess
    )

    if isinstance(expr, (IntLiteral, StringLiteral)):
        return

    if isinstance(expr, Identifier):
        # Mark global usage (locals shadow automatically via scope lookup)
        sym = global_symtab._symbols.get(global_symtab._key(expr.name))
        if sym is not None and not getattr(sym, "proc_name", ""):
            ctx["used_globals"].add(global_symtab._key(expr.name))
        return

    if isinstance(expr, FieldAccess):
        # For field access like global_pt.x, mark the object as used
        _walk_expr(expr.object, ctx, global_symtab)
        return

    if isinstance(expr, CallExpr):
        if expr.name.upper() not in {"LOW", "HIGH", "SIZEOF", "LOWW", "HIGHW"}:
            ctx["func_calls"].add(expr.name)
        for a in expr.args:
            _walk_expr(a, ctx, global_symtab)
        return

    if isinstance(expr, BinaryExpr):
        _walk_expr(expr.left, ctx, global_symtab)
        _walk_expr(expr.right, ctx, global_symtab)
        return

    if isinstance(expr, UnaryExpr):
        _walk_expr(expr.expr, ctx, global_symtab)
        return

    if isinstance(expr, DerefExpr):
        _walk_expr(expr.pointer, ctx, global_symtab)
        return

    if isinstance(expr, SubscriptExpr):
        _walk_expr(expr.array, ctx, global_symtab)
        _walk_expr(expr.index, ctx, global_symtab)
        return


def _walk_stmt(stmt, ctx, global_symtab):
    """Walk a statement tree and record global usage and calls."""
    from ast_nodes import (
        CallStmt, AssignStmt, ReturnStmt, IfStmt, WhileStmt, RepeatUntilStmt, ForStmt, SwitchStmt, BreakStmt,
        ContinueStmt
    )

    if isinstance(stmt, CallStmt):
        # Parser emits CallStmt for both proc calls and func calls used as
        # statements (return value discarded). Add to both sets so prune_unused
        # finds functions that are only called this way.
        ctx["proc_calls"].add(stmt.name)
        ctx["func_calls"].add(stmt.name)
        for a in stmt.args:
            _walk_expr(a, ctx, global_symtab)
        return

    if isinstance(stmt, AssignStmt):
        _walk_expr(stmt.lhs, ctx, global_symtab)
        _walk_expr(stmt.rhs, ctx, global_symtab)
        return

    if isinstance(stmt, ReturnStmt):
        _walk_expr(stmt.expr, ctx, global_symtab)
        return

    if isinstance(stmt, IfStmt):
        _walk_expr(stmt.cond, ctx, global_symtab)
        for s in stmt.then_body:
            _walk_stmt(s, ctx, global_symtab)
        if stmt.else_body:
            for s in stmt.else_body:
                _walk_stmt(s, ctx, global_symtab)
        return

    if isinstance(stmt, WhileStmt):
        _walk_expr(stmt.cond, ctx, global_symtab)
        for s in stmt.body:
            _walk_stmt(s, ctx, global_symtab)
        return

    if isinstance(stmt, RepeatUntilStmt):
        for s in stmt.body:
            _walk_stmt(s, ctx, global_symtab)
        _walk_expr(stmt.cond, ctx, global_symtab)
        return

    if isinstance(stmt, ForStmt):
        _walk_expr(stmt.var, ctx, global_symtab)
        _walk_expr(stmt.start, ctx, global_symtab)
        _walk_expr(stmt.end, ctx, global_symtab)
        if stmt.step:
            _walk_expr(stmt.step, ctx, global_symtab)
        for s in stmt.body:
            _walk_stmt(s, ctx, global_symtab)
        return

    if isinstance(stmt, SwitchStmt):
        _walk_expr(stmt.expr, ctx, global_symtab)
        for case in stmt.cases:
            for label in case.labels:
                _walk_expr(label, ctx, global_symtab)
            for s in case.body:
                _walk_stmt(s, ctx, global_symtab)
        return

    # Break/Continue and others carry no identifiers/calls
    if isinstance(stmt, (BreakStmt, ContinueStmt)):
        return


def _walk_initializer(init, ctx, global_symtab):
    """Walk an initializer expression for global usage and calls."""
    from ast_nodes import ExprInit, ListInit, StringInit
    if isinstance(init, ExprInit):
        _walk_expr(init.expr, ctx, global_symtab)
    elif isinstance(init, ListInit):
        for v in init.values:
            _walk_expr(v, ctx, global_symtab)
    elif isinstance(init, StringInit):
        return


def prune_unused(program, analyzed_procs, analyzed_funcs, global_symtab):
    """Prune unreachable procedures/functions and unused globals."""
    # Defensive checks: ensure analyzers returned valid results
    none_proc_indices = [i for i, p in enumerate(analyzed_procs) if p is None]
    if none_proc_indices:
        # Try to provide helpful context: map indices back to source PROC names when available
        proc_names = [ (program.procs[i].name if i < len(program.procs) and hasattr(program.procs[i], 'name') else None) for i in none_proc_indices ]
        raise RuntimeError(f"Internal compiler error: analyzed_procs contains None at indices {none_proc_indices}, corresponding to source procs {proc_names}")
    none_func_indices = [i for i, f in enumerate(analyzed_funcs) if f is None]
    if none_func_indices:
        func_names = [ (program.procs[i].name if i < len(program.procs) and hasattr(program.procs[i], 'name') else None) for i in none_func_indices ]
        raise RuntimeError(f"Internal compiler error: analyzed_funcs contains None at indices {none_func_indices}, corresponding to source procs {func_names}")

    proc_map = {p.ast.name: p for p in analyzed_procs if p is not None}
    func_map = {f.ast.name: f for f in analyzed_funcs if f is not None}
    all_proc_names = set(proc_map.keys())

    referenced_globals: set[str] = set()
    fixed_globals: set[str] = set(
        name
        for name, sym in list(global_symtab._symbols.items())
        if getattr(sym, "proc_name", "") == "" and sym.address is not None
    )

    ctx = {
        "used_globals": referenced_globals,
        "proc_calls": set(),
        "func_calls": set(),
    }

    # Seed with MAIN and any kept procs/constructors
    constructors = set(getattr(program, "constructors", []) or [])
    keep_procs = {p.ast.name for p in analyzed_procs if getattr(p.ast, "keep", False)}
    reachable_procs = set(["MAIN"]) | constructors | keep_procs
    reachable_funcs = set()

    # Global initializers and declarations may reference globals/funcs
    for decl in program.decls:
        # Skip items that are not variable declarations (e.g., EnumDecl, StructDef, directives)
        if not hasattr(decl, 'declarators'):
            continue
        for d in decl.declarators:
            if d.address is not None:
                _walk_expr(d.address, ctx, global_symtab)
            if d.array_size is not None:
                _walk_expr(d.array_size, ctx, global_symtab)
            if d.initializer is not None:
                _walk_initializer(d.initializer, ctx, global_symtab)
            # Declarator's own symbol should be kept if referenced via init above

    proc_queue = deque(sorted(reachable_procs))
    func_queue = deque()

    while proc_queue or func_queue:
        if proc_queue:
            pname = proc_queue.popleft()
            proc = proc_map.get(pname)
            if proc is None:
                continue
            # Local declarations can reference globals in initializers/addresses
            for decl in proc.ast.locals:
                for d in decl.declarators:
                    if d.address is not None:
                        _walk_expr(d.address, ctx, global_symtab)
                    if d.array_size is not None:
                        _walk_expr(d.array_size, ctx, global_symtab)
                    if d.initializer is not None:
                        _walk_initializer(d.initializer, ctx, global_symtab)
            for st in proc.ast.body:
                _walk_stmt(st, ctx, global_symtab)
            for called in ctx["proc_calls"]:
                if called not in reachable_procs:
                    reachable_procs.add(called)
                    proc_queue.append(called)
            for fcalled in ctx["func_calls"]:
                if fcalled not in reachable_funcs:
                    reachable_funcs.add(fcalled)
                    func_queue.append(fcalled)
            ctx["proc_calls"].clear()
            ctx["func_calls"].clear()
        else:
            fname = func_queue.popleft()
            func = func_map.get(fname)
            if func is None:
                continue
            # Local declarations can reference globals in initializers/addresses
            for decl in func.ast.locals:
                for d in decl.declarators:
                    if d.address is not None:
                        _walk_expr(d.address, ctx, global_symtab)
                    if d.array_size is not None:
                        _walk_expr(d.array_size, ctx, global_symtab)
                    if d.initializer is not None:
                        _walk_initializer(d.initializer, ctx, global_symtab)
            for st in func.ast.body:
                _walk_stmt(st, ctx, global_symtab)
            for called in ctx["proc_calls"]:
                if called not in reachable_procs:
                    reachable_procs.add(called)
                    proc_queue.append(called)
            for fcalled in ctx["func_calls"]:
                if fcalled not in reachable_funcs:
                    reachable_funcs.add(fcalled)
                    func_queue.append(fcalled)
            ctx["proc_calls"].clear()
            ctx["func_calls"].clear()

    # Filter globals to only used (referenced) or fixed-address or have initializers
    global_symtab._symbols = {
        name: sym
        for name, sym in global_symtab._symbols.items()
        if getattr(sym, "proc_name", "") != "" or name in referenced_globals or name in fixed_globals or getattr(sym, "init", None) is not None or getattr(sym, 'is_keep', False)
    }

    # Filter procs/funcs
    pruned_procs = [p for p in analyzed_procs if p.ast.name in reachable_procs or getattr(p.ast, 'keep', False)]
    pruned_funcs = [f for f in analyzed_funcs if f.ast.name in reachable_funcs or getattr(f.ast, 'keep', False)]

    removed_procs = sorted(
        name for name in all_proc_names
        if name not in reachable_procs and not (proc_map.get(name) and getattr(proc_map[name].ast, 'keep', False))
    )

    return pruned_procs, pruned_funcs, referenced_globals, removed_procs


import re as _re
_SOURCE_COMMENT_RE: _re.Pattern[str] = _re.compile(r'^;\s+\S+\.zap\s+\d+:')
_STRIP_MARKERS: frozenset[str] = frozenset({"; __ZAPC_FOOTER_BLOCK__"})


def _is_source_comment(ln: str) -> bool:
    """Return True if ln is a source-path comment emitted by gen_proc()."""
    return bool(_SOURCE_COMMENT_RE.match(ln))


def _format_assembly(lines: list[str], *, seg_zp: str = "ZEROPAGE", seg_bss: str = "BSS") -> list[str]:
    """Compact and reformat assembly output for readability."""
    flat: list[str] = []
    for line in lines:
        parts = line.splitlines()
        if not parts:
            flat.append("")
        else:
            flat.extend(parts)

    # Change 1: strip internal ; ZAP_EXPORTS comment from final output
    flat = [ln for ln in flat if not ln.strip().startswith("; ZAP_EXPORTS")]

    compact = [ln for ln in flat if ln.strip() != ""]

    def is_block_start(ln: str) -> bool:
        """Check whether a line starts a new assembly block."""
        stripped = ln.strip()
        return (
            stripped.startswith("; -- Procedure ") or   # procedures
            stripped.startswith("; -- Function ") or    # functions
            stripped.startswith(".segment ") or          # Change 2: all .segment directives
            stripped in _STRIP_MARKERS                   # Change 3: footer routine markers
        )

    out: list[str] = []
    for ln in compact:
        stripped = ln.strip()

        # Change 3: footer block marker — insert 2 blank lines then discard the marker
        if stripped in _STRIP_MARKERS:
            if out:
                out.append("")
                out.append("")
            continue

        is_proc_or_func = (
            ln.startswith("; -- Procedure ") or
            ln.startswith("; -- Function ")
        )

        if is_block_start(ln) and out:
            # Change 4: if the last emitted line is a source-path comment and we're
            # about to open a procedure/function block, move the comment to sit
            # directly above the header (after the 2 blank lines).
            if is_proc_or_func and _is_source_comment(out[-1]):
                src_comment = out.pop()
                out.append("")
                out.append("")
                out.append(src_comment)
                # No extra blanks — the comment now immediately precedes the header
            else:
                out.append("")
                out.append("")

        out.append(ln)

    # Normalize bare #0 immediate to #$00 for consistent hex formatting
    out = [_re.sub(r'#0\b', '#$00', ln) for ln in out]
    return out


def _walk_expr_locals(expr, used: set[str], local_symtab):
    """Walk an expression and collect referenced local symbols."""
    from ast_nodes import (
        IntLiteral, StringLiteral, Identifier, BinaryExpr, UnaryExpr, DerefExpr,
        SubscriptExpr, CallExpr, FieldAccess
    )

    if isinstance(expr, (IntLiteral, StringLiteral)):
        return

    if isinstance(expr, Identifier):
        if local_symtab._key(expr.name) in local_symtab._symbols:
            used.add(local_symtab._key(expr.name))
        return

    if isinstance(expr, CallExpr):
        for a in expr.args:
            _walk_expr_locals(a, used, local_symtab)
        return

    if isinstance(expr, BinaryExpr):
        _walk_expr_locals(expr.left, used, local_symtab)
        _walk_expr_locals(expr.right, used, local_symtab)
        return

    if isinstance(expr, UnaryExpr):
        _walk_expr_locals(expr.expr, used, local_symtab)
        return

    if isinstance(expr, DerefExpr):
        _walk_expr_locals(expr.pointer, used, local_symtab)
        return

    if isinstance(expr, SubscriptExpr):
        _walk_expr_locals(expr.array, used, local_symtab)
        _walk_expr_locals(expr.index, used, local_symtab)
        return

    if isinstance(expr, FieldAccess):
        _walk_expr_locals(expr.object, used, local_symtab)
        return


def _walk_stmt_locals(stmt, used: set[str], local_symtab):
    """Walk a statement and collect referenced local symbols."""
    from ast_nodes import (
        CallStmt, AssignStmt, ReturnStmt, IfStmt, WhileStmt, RepeatUntilStmt, ForStmt, SwitchStmt, BreakStmt,
        ContinueStmt
    )

    if isinstance(stmt, CallStmt):
        for a in stmt.args:
            _walk_expr_locals(a, used, local_symtab)
        return

    if isinstance(stmt, AssignStmt):
        _walk_expr_locals(stmt.lhs, used, local_symtab)
        _walk_expr_locals(stmt.rhs, used, local_symtab)
        return

    if isinstance(stmt, ReturnStmt):
        _walk_expr_locals(stmt.expr, used, local_symtab)
        return

    if isinstance(stmt, IfStmt):
        _walk_expr_locals(stmt.cond, used, local_symtab)
        for s in stmt.then_body:
            _walk_stmt_locals(s, used, local_symtab)
        if stmt.else_body:
            for s in stmt.else_body:
                _walk_stmt_locals(s, used, local_symtab)
        return

    if isinstance(stmt, WhileStmt):
        _walk_expr_locals(stmt.cond, used, local_symtab)
        for s in stmt.body:
            _walk_stmt_locals(s, used, local_symtab)
        return

    if isinstance(stmt, RepeatUntilStmt):
        for s in stmt.body:
            _walk_stmt_locals(s, used, local_symtab)
        _walk_expr_locals(stmt.cond, used, local_symtab)
        return

    if isinstance(stmt, ForStmt):
        _walk_expr_locals(stmt.var, used, local_symtab)
        _walk_expr_locals(stmt.start, used, local_symtab)
        _walk_expr_locals(stmt.end, used, local_symtab)
        if stmt.step:
            _walk_expr_locals(stmt.step, used, local_symtab)
        for s in stmt.body:
            _walk_stmt_locals(s, used, local_symtab)
        return

    if isinstance(stmt, SwitchStmt):
        _walk_expr_locals(stmt.expr, used, local_symtab)
        for case in stmt.cases:
            for label in case.labels:
                _walk_expr_locals(label, used, local_symtab)
            for s in case.body:
                _walk_stmt_locals(s, used, local_symtab)
        return

    if isinstance(stmt, (BreakStmt, ContinueStmt)):
        return


def _walk_initializer_locals(init, used: set[str], local_symtab):
    """Walk an initializer to collect referenced local symbols."""
    from ast_nodes import ExprInit, ListInit, StringInit
    if isinstance(init, ExprInit):
        _walk_expr_locals(init.expr, used, local_symtab)
    elif isinstance(init, ListInit):
        for v in init.values:
            _walk_expr_locals(v, used, local_symtab)
    elif isinstance(init, StringInit):
        return


def prune_unused_locals(analyzed_procs, analyzed_funcs):
    """Remove unused local symbols from analyzed procs and funcs."""
    def prune_one(body, locals_list, local_symtab, params):
        """Prune a single routine's locals based on usage in its body."""
        used: set[str] = set(p.name for p in params)  # always keep params

        for sym in locals_list:
            if sym.init is not None:
                _walk_initializer_locals(sym.init, used, local_symtab)

        for st in body:
            _walk_stmt_locals(st, used, local_symtab)

        new_symbols = {
            name: sym
            for name, sym in local_symtab._symbols.items()
            if name in used or sym.address is not None  # keep fixed-address locals
        }
        local_symtab._symbols = new_symbols
        return [sym for sym in locals_list if sym.name in used or sym.address is not None]

    for ap in analyzed_procs:
        ap.locals = prune_one(ap.ast.body, ap.locals, ap.symtab.local, ap.ast.params)

    for af in analyzed_funcs:
        af.locals = prune_one(af.ast.body, af.locals, af.symtab.local, af.ast.params)


def _expr_used_locals(expr, name_to_id: dict[str, str]) -> set[str]:
    """Return IDs of locals referenced by an expression."""
    from ast_nodes import (
        IntLiteral, StringLiteral, Identifier, BinaryExpr, UnaryExpr, DerefExpr,
        SubscriptExpr, CallExpr, FieldAccess
    )

    used: set[str] = set()

    if expr is None:
        return used

    if isinstance(expr, (IntLiteral, StringLiteral)):
        return used

    if isinstance(expr, Identifier):
        key = expr.name.upper() if isinstance(expr.name, str) else expr.name
        local_id = name_to_id.get(key)
        if local_id:
            used.add(local_id)
        return used

    if isinstance(expr, CallExpr):
        for a in expr.args:
            used |= _expr_used_locals(a, name_to_id)
        return used

    if isinstance(expr, BinaryExpr):
        used |= _expr_used_locals(expr.left, name_to_id)
        used |= _expr_used_locals(expr.right, name_to_id)
        return used

    if isinstance(expr, UnaryExpr):
        used |= _expr_used_locals(expr.expr, name_to_id)
        return used

    if isinstance(expr, DerefExpr):
        used |= _expr_used_locals(expr.pointer, name_to_id)
        return used

    if isinstance(expr, SubscriptExpr):
        used |= _expr_used_locals(expr.array, name_to_id)
        used |= _expr_used_locals(expr.index, name_to_id)
        return used

    if isinstance(expr, FieldAccess):
        used |= _expr_used_locals(expr.object, name_to_id)
        return used

    return used


def _init_used_locals(init, name_to_id: dict[str, str]) -> set[str]:
    """Return IDs of locals referenced by an initializer."""
    from ast_nodes import ExprInit, ListInit, StringInit
    used: set[str] = set()
    if init is None:
        return used
    if isinstance(init, ExprInit):
        return _expr_used_locals(init.expr, name_to_id)
    if isinstance(init, ListInit):
        for v in init.values:
            if isinstance(v, ExprInit):
                used |= _expr_used_locals(v.expr, name_to_id)
            elif isinstance(v, ListInit):
                used |= _init_used_locals(v, name_to_id)
            elif isinstance(v, StringInit):
                continue
            else:
                used |= _expr_used_locals(v, name_to_id)
        return used
    if isinstance(init, StringInit):
        return used
    return used


def _expr_call_names(expr) -> set[str]:
    """Collect function/procedure call names within an expression."""
    from ast_nodes import (
        IntLiteral, StringLiteral, Identifier, BinaryExpr, UnaryExpr, DerefExpr,
        SubscriptExpr, CallExpr, FieldAccess
    )

    calls: set[str] = set()

    if expr is None:
        return calls

    if isinstance(expr, (IntLiteral, StringLiteral, Identifier)):
        return calls

    if isinstance(expr, CallExpr):
        calls.add(expr.name)
        for a in expr.args:
            calls |= _expr_call_names(a)
        return calls

    if isinstance(expr, BinaryExpr):
        calls |= _expr_call_names(expr.left)
        calls |= _expr_call_names(expr.right)
        return calls

    if isinstance(expr, UnaryExpr):
        calls |= _expr_call_names(expr.expr)
        return calls

    if isinstance(expr, DerefExpr):
        calls |= _expr_call_names(expr.pointer)
        return calls

    if isinstance(expr, SubscriptExpr):
        calls |= _expr_call_names(expr.array)
        calls |= _expr_call_names(expr.index)
        return calls

    if isinstance(expr, FieldAccess):
        calls |= _expr_call_names(expr.object)
        return calls

    return calls


def _init_call_names(init) -> set[str]:
    """Collect function/procedure call names within an initializer."""
    from ast_nodes import ExprInit, ListInit, StringInit
    calls: set[str] = set()
    if init is None:
        return calls
    if isinstance(init, ExprInit):
        return _expr_call_names(init.expr)
    if isinstance(init, ListInit):
        for v in init.values:
            if isinstance(v, ExprInit):
                calls |= _expr_call_names(v.expr)
            elif isinstance(v, ListInit):
                calls |= _init_call_names(v)
            elif isinstance(v, StringInit):
                continue
            else:
                calls |= _expr_call_names(v)
        return calls
    if isinstance(init, StringInit):
        return calls
    return calls


def _stmt_call_names(stmt) -> set[str]:
    """Collect function/procedure call names within a statement tree."""
    from ast_nodes import (
        CallStmt, AssignStmt, ReturnStmt, IfStmt, WhileStmt, RepeatUntilStmt, ForStmt,
        SwitchStmt, BreakStmt, ContinueStmt, SwitchCase
    )

    calls: set[str] = set()

    if isinstance(stmt, CallStmt):
        calls.add(stmt.name)
        for a in stmt.args:
            calls |= _expr_call_names(a)
        return calls

    if isinstance(stmt, AssignStmt):
        calls |= _expr_call_names(stmt.lhs)
        calls |= _expr_call_names(stmt.rhs)
        return calls

    if isinstance(stmt, ReturnStmt):
        calls |= _expr_call_names(stmt.expr)
        return calls

    if isinstance(stmt, IfStmt):
        calls |= _expr_call_names(stmt.cond)
        for s in stmt.then_body:
            calls |= _stmt_call_names(s)
        if stmt.else_body:
            for s in stmt.else_body:
                calls |= _stmt_call_names(s)
        return calls

    if isinstance(stmt, WhileStmt):
        calls |= _expr_call_names(stmt.cond)
        for s in stmt.body:
            calls |= _stmt_call_names(s)
        return calls

    if isinstance(stmt, RepeatUntilStmt):
        for s in stmt.body:
            calls |= _stmt_call_names(s)
        calls |= _expr_call_names(stmt.cond)
        return calls

    if isinstance(stmt, ForStmt):
        calls |= _expr_call_names(stmt.start)
        calls |= _expr_call_names(stmt.end)
        if stmt.step is not None:
            calls |= _expr_call_names(stmt.step)
        for s in stmt.body:
            calls |= _stmt_call_names(s)
        return calls

    if isinstance(stmt, SwitchStmt):
        calls |= _expr_call_names(stmt.expr)
        for case in stmt.cases:
            for label in case.labels:
                calls |= _expr_call_names(label)
            for s in case.body:
                calls |= _stmt_call_names(s)
        return calls

    if isinstance(stmt, (BreakStmt, ContinueStmt)):
        return calls

    return calls


def _add_interference(live_set: set[str], graph: dict[str, set[str]], class_key: dict[str, tuple]) -> None:
    """Add pairwise interference edges for a live set."""
    live_list = list(live_set)
    for i in range(len(live_list)):
        a = live_list[i]
        for j in range(i + 1, len(live_list)):
            b = live_list[j]
            if class_key.get(a) != class_key.get(b):
                continue
            graph.setdefault(a, set()).add(b)
            graph.setdefault(b, set()).add(a)


def _add_edge(a: str, b: str, graph: dict[str, set[str]], class_key: dict[str, tuple]) -> None:
    """Add an interference edge between two compatible locals."""
    if a == b:
        return
    if class_key.get(a) != class_key.get(b):
        return
    graph.setdefault(a, set()).add(b)
    graph.setdefault(b, set()).add(a)


def _liveness_block(
    statements: list,
    live_out: set[str],
    name_to_id: dict[str, str],
    valid_callees: set[str],
    call_live_across: dict[tuple[str, str], set[str]],
    caller_name: str,
    graph: dict[str, set[str]],
    class_key: dict[str, tuple],
    for_temp_map: dict[int, set[str]] | None = None,
    break_live: set[str] | None = None,
    continue_live: set[str] | None = None,
) -> set[str]:
    """Compute live-in set for a statement block and build interference graph."""
    from ast_nodes import (
        CallStmt, AssignStmt, ReturnStmt, IfStmt, WhileStmt, RepeatUntilStmt, ForStmt, SwitchStmt,
        BreakStmt, ContinueStmt, Identifier, AsmBlock
    )

    live: set[str] = set(live_out)

    for st in reversed(statements):
        if isinstance(st, AsmBlock):
            live = set(name_to_id.values()) | live
            _add_interference(live, graph, class_key)
            continue

        if isinstance(st, CallStmt):
            for callee in [st.name]:
                if callee in valid_callees:
                    call_live_across.setdefault((caller_name, callee), set()).update(live)
            uses: set[str] = set()
            for a in st.args:
                uses |= _expr_used_locals(a, name_to_id)
            live = live | uses
            _add_interference(live, graph, class_key)
            continue

        if isinstance(st, AssignStmt):
            uses_rhs = _expr_used_locals(st.rhs, name_to_id)
            uses_lhs = set()
            if not isinstance(st.lhs, Identifier):
                uses_lhs = _expr_used_locals(st.lhs, name_to_id)

            call_names = _stmt_call_names(st)
            for callee in call_names:
                if callee in valid_callees:
                    call_live_across.setdefault((caller_name, callee), set()).update(live | uses_rhs | uses_lhs)

            defs: set[str] = set()
            if isinstance(st.lhs, Identifier):
                key = st.lhs.name.upper() if isinstance(st.lhs.name, str) else st.lhs.name
                if key in name_to_id:
                    defs.add(name_to_id[key])
            else:
                uses_lhs = _expr_used_locals(st.lhs, name_to_id)

            for d in defs:
                for l in live:
                    _add_edge(d, l, graph, class_key)
            live = (live - defs) | uses_rhs | uses_lhs
            _add_interference(live, graph, class_key)
            continue

        if isinstance(st, ReturnStmt):
            uses = _expr_used_locals(st.expr, name_to_id)
            call_names = _stmt_call_names(st)
            for callee in call_names:
                if callee in valid_callees:
                    call_live_across.setdefault((caller_name, callee), set()).update(uses)
            live = uses
            _add_interference(live, graph, class_key)
            continue

        if isinstance(st, IfStmt):
            then_in = _liveness_block(
                st.then_body,
                live,
                name_to_id,
                valid_callees,
                call_live_across,
                caller_name,
                graph,
                class_key,
                for_temp_map=for_temp_map,
                break_live=break_live,
                continue_live=continue_live,
            )
            else_in = live
            if st.else_body:
                else_in = _liveness_block(
                    st.else_body,
                    live,
                    name_to_id,
                    valid_callees,
                    call_live_across,
                    caller_name,
                    graph,
                    class_key,
                    for_temp_map=for_temp_map,
                    break_live=break_live,
                    continue_live=continue_live,
                )
            cond_uses = _expr_used_locals(st.cond, name_to_id)
            cond_calls = _expr_call_names(st.cond)
            cond_live_out = then_in | else_in
            for callee in cond_calls:
                if callee in valid_callees:
                    call_live_across.setdefault((caller_name, callee), set()).update(cond_live_out | cond_uses)
            live = cond_uses | cond_live_out
            _add_interference(live, graph, class_key)
            continue

        if isinstance(st, WhileStmt):
            loop_live_in = set(live)
            while True:
                body_in = _liveness_block(
                    st.body,
                    loop_live_in,
                    name_to_id,
                    valid_callees,
                    call_live_across,
                    caller_name,
                    graph,
                    class_key,
                    for_temp_map=for_temp_map,
                    break_live=live,
                    continue_live=loop_live_in,
                )
                cond_uses = _expr_used_locals(st.cond, name_to_id)
                new_live_in = cond_uses | body_in
                if new_live_in == loop_live_in:
                    break
                loop_live_in = new_live_in
            cond_calls = _expr_call_names(st.cond)
            cond_live_out = body_in | live
            for callee in cond_calls:
                if callee in valid_callees:
                    call_live_across.setdefault((caller_name, callee), set()).update(cond_live_out | cond_uses)
            live = loop_live_in
            _add_interference(live, graph, class_key)
            continue

        if isinstance(st, RepeatUntilStmt):
            loop_live_in = set(live)
            while True:
                body_in = _liveness_block(
                    st.body,
                    loop_live_in,
                    name_to_id,
                    valid_callees,
                    call_live_across,
                    caller_name,
                    graph,
                    class_key,
                    for_temp_map=for_temp_map,
                    break_live=live,
                    continue_live=loop_live_in,
                )
                cond_uses = _expr_used_locals(st.cond, name_to_id)
                new_live_in = cond_uses | body_in
                if new_live_in == loop_live_in:
                    break
                loop_live_in = new_live_in
            cond_calls = _expr_call_names(st.cond)
            cond_live_out = body_in | live
            for callee in cond_calls:
                if callee in valid_callees:
                    call_live_across.setdefault((caller_name, callee), set()).update(cond_live_out | cond_uses)
            live = loop_live_in
            _add_interference(live, graph, class_key)
            continue

        if isinstance(st, ForStmt):
            loop_live_in = set(live)
            loop_uses = _expr_used_locals(st.start, name_to_id)
            loop_uses |= _expr_used_locals(st.end, name_to_id)
            if st.step is not None:
                loop_uses |= _expr_used_locals(st.step, name_to_id)
            
            # Model implicit assignment: for_end_temp = end_expr
            # This allows for_end_temp to share slots with end_expr locals after they're consumed
            for_end_defs: set[str] = set()
            if for_temp_map is not None:
                temp_names = for_temp_map.get(id(st))
                if temp_names:
                    for temp_name in temp_names:
                        # FOR_END_* temps are implicitly assigned from end expression
                        if "END" in temp_name.upper():
                            key = temp_name.upper() if isinstance(temp_name, str) else temp_name
                            if key in name_to_id:
                                for_end_defs.add(name_to_id[key])
                        else:
                            # FOR_STEP_* temps are used in loop body
                            key = temp_name.upper() if isinstance(temp_name, str) else temp_name
                            if key in name_to_id:
                                loop_uses.add(name_to_id[key])
            
            # Add edges from for_end_temp defs to live-out before assignment
            end_uses = _expr_used_locals(st.end, name_to_id)
            for d in for_end_defs:
                for l in live:
                    _add_edge(d, l, graph, class_key)
            # The for_end_temp is defined, but end_expr locals are used (don't remove them)
            # They may still be needed if referenced in loop body
            loop_uses = loop_uses | for_end_defs
            
            # Be conservative: treat loop var as used by control logic
            key = st.var.name.upper() if isinstance(st.var.name, str) else st.var.name
            if key in name_to_id:
                loop_uses.add(name_to_id[key])

            loop_calls = _expr_call_names(st.start) | _expr_call_names(st.end)
            if st.step is not None:
                loop_calls |= _expr_call_names(st.step)

            while True:
                body_in = _liveness_block(
                    st.body,
                    loop_live_in,
                    name_to_id,
                    valid_callees,
                    call_live_across,
                    caller_name,
                    graph,
                    class_key,
                    for_temp_map=for_temp_map,
                    break_live=live,
                    continue_live=loop_live_in,
                )
                new_live_in = loop_uses | body_in
                if new_live_in == loop_live_in:
                    break
                loop_live_in = new_live_in

            for callee in loop_calls:
                if callee in valid_callees:
                    call_live_across.setdefault((caller_name, callee), set()).update(loop_live_in | loop_uses)

            live = loop_live_in
            _add_interference(live, graph, class_key)
            continue

        if isinstance(st, SwitchStmt):
            case_ins: list[set[str]] = []
            for case in st.cases:
                case_in = _liveness_block(
                    case.body,
                    live,
                    name_to_id,
                    valid_callees,
                    call_live_across,
                    caller_name,
                    graph,
                    class_key,
                    for_temp_map=for_temp_map,
                    break_live=live,  # break inside a switch exits the switch
                    continue_live=continue_live,
                )
                case_ins.append(case_in)
            cond_uses = _expr_used_locals(st.expr, name_to_id)
            cond_calls = _expr_call_names(st.expr)
            merged = set()
            for ci in case_ins:
                merged |= ci
            for callee in cond_calls:
                if callee in valid_callees:
                    call_live_across.setdefault((caller_name, callee), set()).update(merged | cond_uses)
            live = cond_uses | merged
            _add_interference(live, graph, class_key)
            continue

        if isinstance(st, BreakStmt):
            live = set(break_live or set())
            _add_interference(live, graph, class_key)
            continue

        if isinstance(st, ContinueStmt):
            live = set(continue_live or set())
            _add_interference(live, graph, class_key)
            continue

    return live


def _liveness_inits(
    locals_list: list,
    live_out: set[str],
    name_to_id: dict[str, str],
    valid_callees: set[str],
    call_live_across: dict[tuple[str, str], set[str]],
    caller_name: str,
    graph: dict[str, set[str]],
    class_key: dict[str, tuple],
) -> set[str]:
    """Compute live-in set contributed by initializers in reverse order."""
    live = set(live_out)
    for sym in reversed(locals_list):
        init = getattr(sym, "init", None)
        if init is None:
            continue

        uses = _init_used_locals(init, name_to_id)
        call_names = _init_call_names(init)
        for callee in call_names:
            if callee in valid_callees:
                call_live_across.setdefault((caller_name, callee), set()).update(live | uses)
        defs: set[str] = set()
        key = sym.name.upper() if isinstance(sym.name, str) else sym.name
        if key in name_to_id:
            defs.add(name_to_id[key])

        for d in defs:
            for l in live:
                _add_edge(d, l, graph, class_key)

        live = (live - defs) | uses
        _add_interference(live, graph, class_key)

    return live


def share_locals_liveness(analyzed_procs, analyzed_funcs, for_temp_map: dict[int, set[str]] | None = None) -> dict[str, str]:
    """
    Perform liveness-based variable slot sharing.
    Returns a dict mapping system temp names to their assigned shared slots.
    """
    from symbols import Symbol

    def is_eligible(sym: Symbol) -> bool:
        """Check whether a symbol can participate in slot sharing."""
        if sym.is_const:
            return False
        if sym.address is not None:
            return False
        if sym.is_port:
            return False
        if sym.is_static:
            return False
        if sym.is_array and sym.get_total_array_size() == 0:
            return False
        return True

    def sym_size(sym: Symbol) -> int:
        """Return the storage size in bytes for a symbol."""
        if sym.is_array:
            return sym.get_total_array_size()
        if sym.type.is_struct and sym.type.struct_info:
            return sym.type.struct_info.size
        return sym.type.width

    def class_for(sym: Symbol) -> tuple | None:
        """Classify a symbol for compatibility in slot sharing."""
        size = sym_size(sym)
        if size <= 0:
            return None
        if sym.type.is_pointer:
            if sym.is_array:
                return ("ptr_array", size)
            return ("ptr_scalar", size)
        if sym.is_array:
            return ("array", size)
        if sym.type.is_struct:
            return ("struct", size)
        if sym.type.base == "BYTE":
            return ("byte", size)
        return ("word", size)

    proc_names = {ap.ast.name for ap in analyzed_procs}
    func_names = {af.ast.name for af in analyzed_funcs}
    valid_callees = proc_names | func_names

    # Local identity mapping
    local_info: dict[str, Symbol] = {}
    local_class: dict[str, tuple] = {}
    routine_locals: dict[str, list[str]] = {}

    def _add_local(sym: Symbol, routine_name: str, ids: list[str]) -> None:
        """Register an eligible local symbol for liveness analysis."""
        if not is_eligible(sym):
            return
        key = class_for(sym)
        if key is None:
            return
        local_id = f"{routine_name}::{sym.name}"
        if local_id in local_info:
            return
        local_info[local_id] = sym
        local_class[local_id] = key
        ids.append(local_id)

    for ap in analyzed_procs:
        ids: list[str] = []
        for sym in ap.locals:
            _add_local(sym, ap.ast.name, ids)
        local_tbl: Any | None = getattr(ap.symtab, "local", None)
        if local_tbl is not None:
            for sym in list(local_tbl):
                _add_local(sym, ap.ast.name, ids)
        routine_locals[ap.ast.name] = ids

    for af in analyzed_funcs:
        ids: list[str] = []
        for sym in af.locals:
            _add_local(sym, af.ast.name, ids)
        local_tbl: Any | None = getattr(af.symtab, "local", None)
        if local_tbl is not None:
            for sym in list(local_tbl):
                _add_local(sym, af.ast.name, ids)
        routine_locals[af.ast.name] = ids

    # Add system temporaries as shareable "locals"
    # These are compiler-generated temps used during expression evaluation
    from symbols import Symbol, SemType
    system_temps: list[tuple[str, int]] = [
        ("MATH_STACK", 8),
        ("MATH0", 4),
        ("MATH1", 2),
        ("TMP0", 2),
        ("TMP2", 2),
        ("TMP3", 2),
        ("TMP4", 2),
    ]
    
    system_ids: list[str] = []
    for temp_name, temp_size in system_temps:
        # Create a symbol for the system temp
        # Treat it as a byte array to get the correct size
        temp_sym = Symbol(
            name=temp_name,
            type=SemType(base="BYTE", is_pointer=False),
            is_const=False,
            const_value=None,
            is_array=True,
            array_len=temp_size,
            array_dims=[temp_size],
            init=None,
            address=None,
            is_volatile=False,
            proc_name="__SYSTEM__",
            is_generated=True,
        )
        temp_id = f"__SYSTEM__::{temp_name}"
        temp_key = ("array", temp_size)  # Treat as byte array with specific size
        local_info[temp_id] = temp_sym
        local_class[temp_id] = temp_key
        system_ids.append(temp_id)
    
    routine_locals["__SYSTEM__"] = system_ids

    if not local_info:
        return {}

    # Liveness + interference
    graph: dict[str, set[str]] = {}
    call_live_across: dict[tuple[str, str], set[str]] = {}

    for ap in analyzed_procs:
        name_to_id = {
            local_id.split("::", 1)[1].upper(): local_id
            for local_id in routine_locals.get(ap.ast.name, [])
        }
        live_after_body = _liveness_block(
            ap.ast.body,
            set(),
            name_to_id,
            valid_callees,
            call_live_across,
            ap.ast.name,
            graph,
            local_class,
            for_temp_map=for_temp_map,
        )
        _liveness_inits(
            ap.locals,
            live_after_body,
            name_to_id,
            valid_callees,
            call_live_across,
            ap.ast.name,
            graph,
            local_class,
        )

    for af in analyzed_funcs:
        name_to_id = {
            local_id.split("::", 1)[1].upper(): local_id
            for local_id in routine_locals.get(af.ast.name, [])
        }
        live_after_body = _liveness_block(
            af.ast.body,
            set(),
            name_to_id,
            valid_callees,
            call_live_across,
            af.ast.name,
            graph,
            local_class,
            for_temp_map=for_temp_map,
        )
        _liveness_inits(
            af.locals,
            live_after_body,
            name_to_id,
            valid_callees,
            call_live_across,
            af.ast.name,
            graph,
            local_class,
        )

    # Build direct call graph
    direct_calls: dict[str, set[str]] = {}
    for (caller, callee) in call_live_across.keys():
        direct_calls.setdefault(caller, set()).add(callee)

    # Compute transitive closure of the call graph
    transitive_calls: dict[str, set[str]] = {}
    for caller in valid_callees:
        transitive_calls[caller] = set(direct_calls.get(caller, set()))

    changed = True
    while changed:
        changed = False
        for caller in valid_callees:
            current_callees = list(transitive_calls[caller])
            for callee in current_callees:
                for indirect_callee in transitive_calls.get(callee, set()):
                    if indirect_callee not in transitive_calls[caller]:
                        transitive_calls[caller].add(indirect_callee)
                        changed = True

    # Cross-call interference: locals live across a call interfere with callee locals
    # AND all transitively called locals.
    for (caller, callee), live_ids in call_live_across.items():
        active_routines = {callee} | transitive_calls.get(callee, set())
        for routine in active_routines:
            callee_ids = routine_locals.get(routine, [])
            if not callee_ids:
                continue
            for caller_id in live_ids:
                for callee_id in callee_ids:
                    _add_edge(caller_id, callee_id, graph, local_class)

    # Parameter-to-parameter interference: all parameters of a function/procedure are simultaneously
    # live at function entry and must not share slots
    for ap in analyzed_procs:
        param_ids: list[str] = []
        for param in ap.ast.params:
            param_id = f"{ap.ast.name}::{param.name}"
            if param_id in local_info:
                param_ids.append(param_id)
        # Add mutual interference between all parameters
        for i, p1 in enumerate(param_ids):
            for p2 in param_ids[i + 1:]:
                _add_edge(p1, p2, graph, local_class)

    for af in analyzed_funcs:
        param_ids: list[str] = []
        for param in af.ast.params:
            param_id = f"{af.ast.name}::{param.name}"
            if param_id in local_info:
                param_ids.append(param_id)
        # Add mutual interference between all parameters
        for i, p1 in enumerate(param_ids):
            for p2 in param_ids[i + 1:]:
                _add_edge(p1, p2, graph, local_class)

    # System temps MUST have mutual interference because they can be used
    # simultaneously during expression evaluation (e.g., __ARRCPY uses __TMP0, __TMP2, __TMP3 together)
    system_ids = routine_locals.get("__SYSTEM__", [])
    for i, t1 in enumerate(system_ids):
        for t2 in system_ids[i + 1:]:
            _add_edge(t1, t2, graph, local_class)

    # Color per class
    by_class: dict[tuple, list[str]] = {}
    for local_id, key in local_class.items():
        by_class.setdefault(key, []).append(local_id)

    slot_counter = 0
    for key, ids in by_class.items():
        # Greedy coloring
        ids.sort(key=lambda i: len(graph.get(i, set())), reverse=True)
        color_of: dict[str, int] = {}
        for local_id in ids:
            neighbor_colors = {color_of[n] for n in graph.get(local_id, set()) if n in color_of}
            color = 0
            while color in neighbor_colors:
                color += 1
            color_of[local_id] = color

        # Group by color and assign shared slots where used by multiple locals
        color_groups: dict[int, list[str]] = {}
        for local_id, color in color_of.items():
            color_groups.setdefault(color, []).append(local_id)

        for _, group in sorted(color_groups.items()):
            # Assign shared slot to ALL locals in this color (even single-variable groups)
            # This provides consistent naming and better readability
            slot_counter += 1
            slot_label = f"__LVSLOT_{slot_counter}"
            for local_id in group:
                sym = local_info.get(local_id)
                if sym is not None:
                    sym.shared_slot = slot_label

    # Extract system temp slot mappings
    system_temp_slots: dict[str, str] = {}
    for temp_id in routine_locals.get("__SYSTEM__", []):
        # temp_id format: "__SYSTEM__::TEMPNAME"
        temp_name = temp_id.split("::", 1)[1]
        sym = local_info.get(temp_id)
        if sym and sym.shared_slot:
            system_temp_slots[temp_name] = sym.shared_slot

    # Remap BSS slots to avoid conflicts with ZP slots
    # Collect which slots are used for ZP vs BSS variables
    zp_slots: set[str] = set()
    bss_slots: set[str] = set()
    
    for local_id, sym in local_info.items():
        if sym and sym.shared_slot:
            # Decide if this variable goes to BSS or ZP (same logic as in gen_vars)
            # System temps always go to ZP
            use_bss = False
            if "__SYSTEM__" not in local_id:  # Regular locals, not system temps
                if sym.is_array and not sym.type.is_pointer:
                    use_bss = True
                elif sym.type.is_struct:
                    use_bss = True
            
            if use_bss:
                bss_slots.add(sym.shared_slot)
            else:
                zp_slots.add(sym.shared_slot)
    
    # If any slot appears in both ZP and BSS, remap BSS variables to __BSSSLOT_N
    conflicting_slots = zp_slots & bss_slots
    if conflicting_slots:
        bss_slot_remap: dict[str, str] = {}
        for slot_label in sorted(conflicting_slots):
            new_label = slot_label.replace("__LVSLOT_", "__BSSSLOT_")
            bss_slot_remap[slot_label] = new_label
        
        # Update all BSS variables to use the new slot names
        for local_id, sym in local_info.items():
            if sym and sym.shared_slot and sym.shared_slot in bss_slot_remap:
                # System temps always stay in ZP, don't remap them
                use_bss = False
                if "__SYSTEM__" not in local_id:  # Regular locals, not system temps
                    if sym.is_array and not sym.type.is_pointer:
                        use_bss = True
                    elif sym.type.is_struct:
                        use_bss = True
                if use_bss:
                    sym.shared_slot = bss_slot_remap[sym.shared_slot]

    return system_temp_slots


def _predeclare_for_loop_temps(analyzed_procs, analyzed_funcs, func_table, struct_registry) -> dict[int, set[str]]:
    """Create stable temp names for FOR loop end/step values."""
    from ast_nodes import ForStmt, IfStmt, WhileStmt, RepeatUntilStmt, SwitchStmt, IntLiteral, Identifier
    from symbols import SemType, Symbol

    for_temp_map: dict[int, set[str]] = {}
    for_id = 0

    def next_for_name(base: str) -> str:
        """Generate a unique FOR temp name with a stable counter."""
        nonlocal for_id
        for_id += 1
        return f"FOR_{base}_{for_id}"

    def declare_temp(local_tbl: SymbolTable, proc_name: str, name: str, type_base: str) -> None:
        """Declare a temp symbol in the local table if absent."""
        key = local_tbl._key(name)
        if key in local_tbl._symbols:
            return
        sym = Symbol(
            name=name,
            type=SemType(type_base, False),
            is_const=False,
            const_value=None,
            is_array=False,
            array_len=None,
            init=None,
            address=None,
            is_volatile=False,
            proc_name=proc_name,
            array_dims=None,
        )
        local_tbl.define(sym)

    def scan_stmts(stmts: list, tc: ExprTypeChecker, local_tbl: SymbolTable, proc_name: str) -> None:
        """Scan statements to predeclare FOR-loop temporaries."""
        for st in stmts:
            if isinstance(st, ForStmt):
                step_expr = st.step if st.step is not None else IntLiteral(1)

                var_t = tc.check(st.var)
                temp_names: set[str] = set()

                # Mirror codegen: FOR_END temp only when end is not a simple Identifier
                # (_gen_for_const_step and _gen_for_general both skip the temp for Identifier ends)
                if not isinstance(st.end, Identifier):
                    end_t = tc.check(st.end)
                    end_is_word = (
                        var_t.sem_type.base == "WORD" or var_t.sem_type.is_pointer or
                        end_t.sem_type.base == "WORD" or end_t.sem_type.is_pointer
                    )
                    end_width = max(var_t.sem_type.width, end_t.sem_type.width)
                    end_type_base = "LONG" if end_width == 4 else ("WORD" if end_is_word else "BYTE")
                    end_name = next_for_name("END")
                    declare_temp(local_tbl, proc_name, end_name, end_type_base)
                    temp_names.add(end_name)

                # Mirror codegen: FOR_STEP temp only when step is neither IntLiteral nor Identifier
                # (_gen_for_general uses Identifier steps directly; IntLiteral uses _gen_for_const_step)
                if not isinstance(step_expr, IntLiteral) and not isinstance(step_expr, Identifier):
                    step_t = tc.check(step_expr)
                    step_is_word = (
                        var_t.sem_type.base == "WORD" or var_t.sem_type.is_pointer or
                        step_t.sem_type.base == "WORD" or step_t.sem_type.is_pointer
                    )
                    step_width = max(var_t.sem_type.width, step_t.sem_type.width)
                    step_type_base = "LONG" if step_width == 4 else ("WORD" if step_is_word else "BYTE")
                    step_name = next_for_name("STEP")
                    declare_temp(local_tbl, proc_name, step_name, step_type_base)
                    temp_names.add(step_name)

                for_temp_map[id(st)] = temp_names
                scan_stmts(st.body, tc, local_tbl, proc_name)
                continue

            if isinstance(st, IfStmt):
                scan_stmts(st.then_body, tc, local_tbl, proc_name)
                if st.else_body:
                    scan_stmts(st.else_body, tc, local_tbl, proc_name)
                continue

            if isinstance(st, WhileStmt):
                scan_stmts(st.body, tc, local_tbl, proc_name)
                continue

            if isinstance(st, RepeatUntilStmt):
                scan_stmts(st.body, tc, local_tbl, proc_name)
                continue

            if isinstance(st, SwitchStmt):
                for case in st.cases:
                    scan_stmts(case.body, tc, local_tbl, proc_name)
                continue

    for ap in analyzed_procs:
        local_tbl: Any | None = getattr(ap.symtab, "local", None)
        if local_tbl is None:
            continue
        tc = ExprTypeChecker(ap.symtab, func_table, struct_registry)
        scan_stmts(ap.ast.body, tc, local_tbl, ap.ast.name)

    for af in analyzed_funcs:
        local_tbl = getattr(af.symtab, "local", None)
        if local_tbl is None:
            continue
        tc = ExprTypeChecker(af.symtab, func_table, struct_registry)
        scan_stmts(af.ast.body, tc, local_tbl, af.ast.name)

    return for_temp_map


def prioritize_locals_to_zp(analyzed_procs, analyzed_funcs) -> None:
    """Analyze load/store frequency for scalar locals and prioritize to ZP.
    
    Allocation priority:
    1. All pointers/pointer-arrays → ZP (mandatory for fast dereferencing)
    2. High-frequency scalar locals → ZP (space permitting)
    3. Arrays, fixed-address, static → always BSS
    
    Frequency scoring accounts for:
    - Loop nesting depth (inner loops heavily weighted)
    - Combined load/store operations
    """
    from symbols import Symbol
    from ast_nodes import Identifier, WhileStmt, RepeatUntilStmt, ForStmt
    
    def count_local_accesses(node, symtab: SymbolTable, proc_name: str) -> dict[str, int]:
        """Count loop-weighted frequency for each local scalar.
        
        Variables in loops get exponentially higher weights:
        - Base (outside loops): weight = 1
        - Loop depth 1: weight = 10x
        - Loop depth 2: weight = 100x
        - Loop depth 3+: weight = 1000x+
        """
        freq = {}
        
        def visit(n, loop_depth=0):
            """Walk the AST and accumulate loop-weighted access counts."""
            nonlocal freq
            if n is None:
                return
            
            if hasattr(n, '__class__'):
                name = n.__class__.__name__
                
                # Calculate weight factor based on loop depth
                # Exponential growth model: weight = 10^loop_depth
                weight_factor = 10 ** max(0, loop_depth)
                
                # Count identifier references (loads)
                if name == 'Identifier':
                    try:
                        sym = symtab.lookup(n.name)
                        if sym and sym.proc_name and not sym.is_array and not sym.is_port and sym.address is None:
                            local_id = f"{proc_name}::{sym.name}"
                            freq[local_id] = freq.get(local_id, 0) + weight_factor
                    except:
                        pass
                
                # Detect loop constructs and increase depth for their bodies
                if name in ('WhileStmt', 'RepeatUntilStmt', 'ForStmt'):
                    # Visit condition/init at current depth
                    if name in ('WhileStmt', 'RepeatUntilStmt'):
                        condition = getattr(n, 'cond', None)
                        if condition:
                            visit(condition, loop_depth)
                        # Visit body with increased depth
                        body = getattr(n, 'body', None)
                        if body:
                            if isinstance(body, list):
                                for stmt in body:
                                    visit(stmt, loop_depth + 1)
                            else:
                                visit(body, loop_depth + 1)
                    elif name == 'ForStmt':
                        # Visit init, condition, step at current depth
                        for attr in ['init', 'condition', 'step']:
                            child = getattr(n, attr, None)
                            if child:
                                visit(child, loop_depth)
                        # Visit body with increased depth
                        body = getattr(n, 'body', None)
                        if body:
                            if isinstance(body, list):
                                for stmt in body:
                                    visit(stmt, loop_depth + 1)
                            else:
                                visit(body, loop_depth + 1)
                    return  # Don't double-process children below
                
                # Recursively visit other children at same depth
                for attr in ['left', 'right', 'operand', 'condition', 'then_stmt', 'else_stmt', 
                             'init', 'body', 'expr', 'base', 'index', 'object', 'args', 'value']:
                    child = getattr(n, attr, None)
                    if child is not None:
                        if isinstance(child, list):
                            for item in child:
                                visit(item, loop_depth)
                        else:
                            visit(child, loop_depth)
        
        visit(node)
        return freq
    
    # Collect frequency for all locals
    total_freq = {}
    
    for proc in analyzed_procs:
        freq = count_local_accesses(proc.ast.body, proc.symtab, proc.ast.name)
        total_freq.update(freq)
    
    for func in analyzed_funcs:
        freq = count_local_accesses(func.ast.body, func.symtab, func.ast.name)
        total_freq.update(freq)
    
    # Allocate high-frequency locals to ZP
    # Priority order:
    # 1. All pointers (mandatory for fast dereferencing) → ZP
    # 2. High-frequency scalars (by frequency score) → ZP
    # 3. Arrays, fixed-address, static → always BSS
    
    def sym_size(sym: Symbol) -> int:
        """Get size of symbol in bytes."""
        if sym.is_array:
            return sym.get_total_array_size()
        if sym.type.is_struct and sym.type.struct_info:
            return sym.type.struct_info.size
        return sym.type.width
    
    # Collect candidates for ZP allocation
    zp_candidates = []  # List of (proc_name, sym) tuples
    
    for proc in analyzed_procs:
        for sym in proc.locals:
            # Skip ineligible symbols
            if sym.is_const or sym.is_array or sym.address is not None or sym.is_port or sym.is_static:
                continue
            
            # Pointers get priority (always allocate to ZP)
            is_pointer = sym.type.is_pointer
            local_id = f"{proc.ast.name}::{sym.name}"
            freq = total_freq.get(local_id, 0)
            
            zp_candidates.append((sym, proc.ast.name, is_pointer, freq, sym_size(sym)))
    
    for func in analyzed_funcs:
        for sym in func.locals:
            # Skip ineligible symbols
            if sym.is_const or sym.is_array or sym.address is not None or sym.is_port or sym.is_static:
                continue
            
            is_pointer = sym.type.is_pointer
            local_id = f"{func.ast.name}::{sym.name}"
            freq = total_freq.get(local_id, 0)
            
            zp_candidates.append((sym, func.ast.name, is_pointer, freq, sym_size(sym)))
    
    # Sort candidates: pointers first (by frequency), then non-pointers by frequency
    # Key: (not is_pointer, -freq, -size) puts pointers first, then sorts by desc frequency
    zp_candidates.sort(key=lambda x: (not x[2], -x[3], -x[4]))
    
    # Estimate available ZP space (256 bytes total minus system vars)
    # System: MATH_STACK(8), MATH0(4), MATH1(2), TMP0-4(10) = 24 bytes
    # Fixed vars: typically ~0-50 bytes depending on config
    # Conservative estimate: 150 bytes available for local allocation
    zp_available = 150  # bytes
    zp_used = 0
    
    # Mark symbols that fit in ZP
    for sym, proc_name, is_pointer, freq, size in zp_candidates:
        if zp_used + size <= zp_available:
            sym.zp_priority = freq  # Mark with frequency score as priority
            zp_used += size
        else:
            sym.zp_priority = -1  # Mark as "not allocated to ZP"


def compile_program(program: Program, *, target_6502: bool = False, command_line: str | None = None, defined_symbols: Optional[Set[str]] = None, enable_peephole: bool = False, seg_zp: str = "ZEROPAGE", seg_bss: str = "BSS", seg_code: str = "CODE") -> str:
    """Run the full compile pipeline from AST to assembly output."""
    # --- symbol tables ---
    global_symtab = SymbolTable()
    proc_table = ProcTable()
    func_table = FuncTable()
    struct_registry = StructRegistry()

    # --- enums (compile-time constants) ---
    enum_an = EnumAnalyzer(global_symtab)
    # Run enum analyzer first so their members are available as consts for later declarations
    for d in program.decls:
        from ast_nodes import EnumDecl
        if isinstance(d, EnumDecl):
            enum_an.analyze(d)

    # --- struct definitions ---
    struct_an = StructAnalyzer(struct_registry, enum_symtab=global_symtab)
    for item in program.procs:
        if isinstance(item, StructDef):
            struct_an.analyze(item)

    # --- declarations ---    
    decl_an = DeclarationAnalyzer(
        global_symtab,
        struct_registry,
        func_table,
        global_symtab=None,
        debug_info=getattr(program, "debug", None),
    )
    for d in program.decls:
        # Skip enum declarations; they were processed above
        from ast_nodes import EnumDecl
        if isinstance(d, EnumDecl):
            continue
        decl_an.analyze(d)
    
    # --- debug info ---
    debug = getattr(program, "debug", None) or {}

    def _map_debug_line(fname: str | None, line: int | None) -> int | None:
        """Map cleaned-source line numbers back to original file lines."""
        if fname and isinstance(line, int):
            orig_map = (debug.get("orig_line_map_per_file") or {}).get(fname)
            if orig_map and 1 <= line <= len(orig_map):
                return orig_map[line - 1]
        return line

    def _attach_source_text(err, fname: str | None) -> None:
        """Attach original source text to an error when available."""
        if not fname:
            return
        orig_src = (debug.get("orig_source_lines_per_file") or {}).get(fname)
        if orig_src:
            err.source_text = "\n".join(orig_src)
            return
        file_lines = (debug.get("file_lines") or {}).get(fname)
        if file_lines:
            err.source_text = "\n".join(file_lines)

    # Check for collisions with .define symbols
    if defined_symbols:
        for name in list(global_symtab._symbols.keys()):
            if name in defined_symbols or name.upper() in defined_symbols:
                gdecl = debug.get("global_decl_src") or {}
                info = gdecl.get(name)
                if info:
                    fname, line, col, _text = info
                    mapped_line = _map_debug_line(fname, line)
                    e = SemanticError(f"Variable '{name}' conflicts with .define symbol", line=mapped_line, col=col)
                    e.filename = fname
                    _attach_source_text(e, fname)
                    raise e
                # No per-declaration source info available; attach a fallback position
                raise SemanticError(f"Variable '{name}' conflicts with .define symbol", line=1, col=1)

    # --- expression type checker ---
    expr_tc = ExprTypeChecker(global_symtab, func_table, struct_registry)

    # --- procedures and functions ---
    proc_an = ProcAnalyzer(proc_table, debug_info=debug, struct_registry=struct_registry, func_table=func_table)
    func_an = FuncAnalyzer(func_table, expr_tc, debug_info=debug, struct_registry=struct_registry)
    analyzed_procs = []
    analyzed_funcs = []
    
    # first pass: register all proc/func signatures
    for p in program.procs:
        if isinstance(p, ProcDecl):
            proc_an.analyze_decl(p)
            # Check for collision with existing global variables
            if global_symtab._key(p.name) in global_symtab._symbols:
                proc_src = debug.get("proc_src") or {}
                info = proc_src.get(p.name)
                if info:
                    fname, line, col, _text = info
                    mapped_line = _map_debug_line(fname, line)
                    e = SemanticError(f"Procedure '{p.name}' conflicts with existing variable", line=mapped_line, col=col)
                    e.filename = fname
                    _attach_source_text(e, fname)
                    raise e
                # No per-proc source info available; attach a fallback position
                raise SemanticError(f"Procedure '{p.name}' conflicts with existing variable", line=1, col=1)
            # Check for collision with .define symbols
            if defined_symbols and p.name.upper() in defined_symbols:
                proc_src = debug.get("proc_src") or {}
                info = proc_src.get(p.name)
                if info:
                    fname, line, col, _text = info
                    mapped_line = _map_debug_line(fname, line)
                    e = SemanticError(f"Procedure '{p.name}' conflicts with .define symbol", line=mapped_line, col=col)
                    e.filename = fname
                    _attach_source_text(e, fname)
                    raise e
                # No per-proc source info available; attach a fallback position
                raise SemanticError(f"Procedure '{p.name}' conflicts with .define symbol", line=1, col=1)
        elif isinstance(p, FuncDecl):
            func_an.analyze_decl(p)
            # Check for collision with existing global variables
            if global_symtab._key(p.name) in global_symtab._symbols:
                proc_src = debug.get("proc_src") or {}
                info = proc_src.get(p.name)
                if info:
                    fname, line, col, _text = info
                    mapped_line = _map_debug_line(fname, line)
                    e = SemanticError(f"Function '{p.name}' conflicts with existing variable", line=mapped_line, col=col)
                    e.filename = fname
                    _attach_source_text(e, fname)
                    raise e
                # No per-func source info available; attach a fallback position
                raise SemanticError(f"Function '{p.name}' conflicts with existing variable", line=1, col=1)
            # Check for collision with .define symbols
            if defined_symbols and p.name.upper() in defined_symbols:
                proc_src = debug.get("proc_src") or {}
                info = proc_src.get(p.name)
                if info:
                    fname, line, col, _text = info
                    mapped_line = _map_debug_line(fname, line)
                    e = SemanticError(f"Function '{p.name}' conflicts with .define symbol", line=mapped_line, col=col)
                    e.filename = fname
                    _attach_source_text(e, fname)
                    raise e
                # No per-func source info available; attach a fallback position
                raise SemanticError(f"Function '{p.name}' conflicts with .define symbol", line=1, col=1)
    
    # Ensure main() procedure exists (required for initialization code)
    try:
        proc_table.lookup("MAIN")
    except KeyError:
        # Give a stable fallback location if main() is missing
        raise SemanticError("Program must have a 'main()' procedure", line=1, col=1)
    
    # second pass: analyze bodies
    for p in program.procs:
        if isinstance(p, ProcDecl):
            ap = proc_an.analyze_proc(p, global_symtab)
            if ap is None:
                raise RuntimeError(f"Internal compiler error: Proc analyzer returned None for procedure '{p.name}'")
            analyzed_procs.append(ap)
        elif isinstance(p, FuncDecl):
            af = func_an.analyze_func(p, global_symtab)
            if af is None:
                raise RuntimeError(f"Internal compiler error: Func analyzer returned None for function '{p.name}'")
            analyzed_funcs.append(af)

    # --- codegen ---
    # reuse func_table from analysis (already has all functions registered)
    tc = ExprTypeChecker(global_symtab, func_table, struct_registry)
    pruned_procs, pruned_funcs, used_globals, removed_procs = prune_unused(
        program, analyzed_procs, analyzed_funcs, global_symtab
    )
    analyzed_procs, analyzed_funcs = pruned_procs, pruned_funcs

    # Add generated return buffers for struct-returning functions.
    # Must be done AFTER prune_unused so these generated globals are not pruned.
    func_return_buffers: dict[str, tuple[str, StructInfo]] = {}
    for af in analyzed_funcs:
        ret_sem = af.ret_type
        if ret_sem.is_struct and not ret_sem.is_pointer and ret_sem.struct_info is not None:
            buf_name = f"RETBUF_{af.ast.name}"
            try:
                global_symtab.define(
                    Symbol(
                        name=buf_name,
                        type=SemType(
                            base=ret_sem.base,
                            is_pointer=False,
                            is_struct=True,
                            struct_info=ret_sem.struct_info,
                        ),
                        is_const=False,
                        const_value=None,
                        is_array=False,
                        array_len=None,
                        init=None,
                        address=None,
                        proc_name="",
                        array_dims=None,
                        is_generated=True,
                    )
                )
            except SemanticError:
                # If it already exists, reuse it
                pass
            sym = global_symtab.lookup(buf_name)
            func_return_buffers[af.ast.name] = (sym.asm_name(), ret_sem.struct_info)

    # Build parameter specs for procedures and functions (name -> [(param, width, default_value)])
    def _build_param_specs_procs(procs):
        """Build procedure parameter specs for code generation."""
        specs: dict[str, list[tuple[str, int, object, SemType]]] = {}
        for ap in procs:
            params: list[tuple[str, int, object, SemType]] = []
            for prm in ap.ast.params:
                base_name: str = prm.type.base.upper()
                is_struct = struct_registry.is_defined(base_name) if struct_registry else False
                struct_info = struct_registry.lookup(base_name) if is_struct else None
                sem_type = SemType(
                    base=prm.type.base,
                    is_pointer=prm.type.is_pointer,
                    is_struct=is_struct,
                    struct_info=struct_info
                )
                params.append((prm.name, sem_type.width, prm.default_value, sem_type))
            specs[ap.ast.name] = params
        return specs

    def _build_param_specs_funcs(funcs):
        """Build function parameter specs for code generation."""
        specs: dict[str, list[tuple[str, int, object, SemType]]] = {}
        for af in funcs:
            params: list[tuple[str, int, object, SemType]] = []
            for prm in af.ast.params:
                base_name: str = prm.type.base.upper()
                is_struct = struct_registry.is_defined(base_name) if struct_registry else False
                struct_info = struct_registry.lookup(base_name) if is_struct else None
                sem_type = SemType(
                    base=prm.type.base,
                    is_pointer=prm.type.is_pointer,
                    is_struct=is_struct,
                    struct_info=struct_info
                )
                params.append((prm.name, sem_type.width, prm.default_value, sem_type))
            specs[af.ast.name] = params
        return specs

    proc_param_specs = _build_param_specs_procs(analyzed_procs)
    func_param_specs = _build_param_specs_funcs(analyzed_funcs)

    cg = CodeGen(
        global_symtab,
        tc,
        is_65c02=not target_6502,
        used_globals=used_globals,
        debug_info=getattr(program, "debug", None),
        command_line=command_line,
        proc_param_specs=proc_param_specs,
        func_param_specs=func_param_specs,
        pruned_procs=removed_procs,
        struct_registry=struct_registry,
        func_return_buffers=func_return_buffers,
        system_temp_slots={},  # Will be updated after liveness analysis
        seg_zp=seg_zp,
        seg_bss=seg_bss,
        seg_code=seg_code,
    )
    # Recompute exports to reflect pruned (removed) procs/funcs and globals
    original_exports = set(getattr(program, 'exports', set()) or set())
    final_proc_names = set(ap.ast.name for ap in analyzed_procs)
    final_func_names = set(af.ast.name for af in analyzed_funcs)
    final_global_names = set(sym.name for sym in global_symtab)
    cg.exports = {name for name in original_exports if (name in final_proc_names or name in final_func_names or name in final_global_names)}

    # Populate fixed-address labels EARLY (before code generation) to protect hardware variables
    # from peephole optimization. Fixed-address variables may have side effects on read/write.
    for sym in global_symtab:
        if hasattr(sym, "address") and sym.address is not None:
            cg.fixed_address_labels.add(sym.asm_name())
    for proc in analyzed_procs:
        for sym in proc.locals:
            if hasattr(sym, "address") and sym.address is not None:
                cg.fixed_address_labels.add(sym.asm_name())
    for func in analyzed_funcs:
        for sym in func.locals:
            if hasattr(sym, "address") and sym.address is not None:
                cg.fixed_address_labels.add(sym.asm_name())

    prune_unused_locals(analyzed_procs, analyzed_funcs)

    cg.gen_file_header()

    # globals init
    cg.gen_globals_header()
    for sym in global_symtab:
        cg.gen_init(sym)
    
    # Collect and initialize static local variables (initialized once at program start)
    static_locals = []
    for proc in analyzed_procs:
        for sym in proc.locals:
            if sym.is_static:
                static_locals.append(sym)
    for func in analyzed_funcs:
        for sym in func.locals:
            if sym.is_static:
                static_locals.append(sym)
    
    for sym in static_locals:
        cg.gen_init(sym, is_global_init=True)
    
    # Emit module constructor calls (after all global/static inits), in dependency order
    for ctor in getattr(program, 'constructors', []) or []:
        cg.emit(f"\tJSR {cg.asm_symbol_name(ctor)}")

    cg.gen_globals_footer()

    # Initialize stmt_src tracking for DCE
    from dce import init_stmt_src_tracking, get_updated_stmt_src
    original_debug = getattr(program, "debug", {})
    if original_debug:
        init_stmt_src_tracking(original_debug.get("stmt_src", {}))

    # procedures and functions - First pass: apply DCE to all procs and funcs
    for p in program.procs:
        if isinstance(p, ProcDecl):
            ap = next((ap for ap in analyzed_procs if ap.ast.name == p.name), None)
            if ap:
                ap.ast = ProcDecl(
                    name=ap.ast.name,
                    params=ap.ast.params,
                    locals=ap.ast.locals,
                    body=dce_block(ap.ast.body),
                    keep=getattr(ap.ast, 'keep', False),
                    noexport=getattr(ap.ast, 'noexport', False),
                    export=getattr(ap.ast, 'export', False),
                )
        elif isinstance(p, FuncDecl):
            af = next((af for af in analyzed_funcs if af.ast.name == p.name), None)
            if af:
                af.ast = FuncDecl(
                    name=af.ast.name,
                    ret_type=af.ast.ret_type,
                    params=af.ast.params,
                    locals=af.ast.locals,
                    body=dce_block(af.ast.body),
                    keep=getattr(af.ast, 'keep', False),
                    noexport=getattr(af.ast, 'noexport', False),
                    export=getattr(af.ast, 'export', False),
                )
    
    # Update program.debug and CodeGen's stmt_src with new mappings after all DCE
    # Update in place to preserve references
    if original_debug:
        updated_stmt_src = get_updated_stmt_src()
        original_debug["stmt_src"].clear()
        original_debug["stmt_src"].update(updated_stmt_src)

    # Predeclare for-loop temps so liveness can track them safely
    for_temp_map = _predeclare_for_loop_temps(analyzed_procs, analyzed_funcs, func_table, struct_registry)

    # Liveness-based local sharing (after DCE updates)
    system_temp_slots = share_locals_liveness(analyzed_procs, analyzed_funcs, for_temp_map=for_temp_map)
    
    # Update CodeGen with system temp slot assignments
    cg.system_temp_slots = system_temp_slots
    
    # ZP prioritization (analyze frequency for optimal ZP allocation)
    prioritize_locals_to_zp(analyzed_procs, analyzed_funcs)
    
    # Assign zero-page variables before code emission so optimizations can rely on sym.in_zeropage
    cg.assign_zeropage(analyzed_procs, analyzed_funcs)
    
    # Now generate code with updated stmt_src
    for p in program.procs:
        if isinstance(p, IncbinDirective):
            cg.emit(f'.incbin "{p.filename}"')
            continue
            
        if isinstance(p, ProcDecl):
            ap = next((ap for ap in analyzed_procs if ap.ast.name == p.name), None)
            if ap:
                cg.gen_proc(ap)
        elif isinstance(p, FuncDecl):
            af = next((af for af in analyzed_funcs if af.ast.name == p.name), None)
            if af:
                cg.gen_func(af)

    # Keep code legal
    cg.legalize_illegal_ops()

    # Build variable block (now that dynamic temps are known)
    vars_block = cg.gen_vars_block(analyzed_procs, analyzed_funcs)

    # Insert vars in front of the first CODE segment to keep ZP symbols ahead of use
    try:
        code_start = next(i for i, ln in enumerate(cg.code) if ln.strip().startswith(f'.segment "{seg_code}"'))
    except StopIteration:
        code_start = 0
    cg.code = cg.code[:code_start] + vars_block + cg.code[code_start:]

    cg.gen_file_footer()

    # Keep code legal
    cg.legalize_illegal_ops()
    # Apply peephole optimizations only when explicitly enabled
    if enable_peephole:
        cg.peephole_optimize()
    cg.code = _format_assembly(cg.code, seg_zp=seg_zp, seg_bss=seg_bss)
    return "\n".join(cg.code)

