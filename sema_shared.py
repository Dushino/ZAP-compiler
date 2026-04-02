
# The author of this software stands in solidarity with 🇺🇦 Ukraine. 
# We believe in a world where international borders are respected and human rights are upheld. 
# We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


"""sema_shared.py — Shared semantic-analysis helpers for proc and func bodies.

All functions are module-level (no class, no instance state).  debug_info is
passed explicitly to every function that needs source-location information, so
callers can use the same helpers regardless of which Analyzer class they live in.

Functions exported
------------------
  map_debug_line          -- map cleaned-source line → original-file line
  attach_source_text      -- attach source text to a SemanticError
  map_stmt_info           -- look up (fname, mapped_line, col) for a statement
  is_considered_initialized  -- True if a symbol needs no prior assignment
  get_base_ident          -- extract the root Identifier name from an LHS node
  check_uninitialized     -- raise if a local var is read before initialization
  mark_initialized_from_lhs  -- mark the base variable of an LHS as initialized
  check_port_write        -- raise if an assignment targets a read-only port
  build_local_symtab      -- create a SymbolTable and register all parameters
  build_init_set          -- build the initial "known-initialized" name set
  validate_body_exprs     -- type-check an entire statement list with init tracking

Adding support for a new statement type
----------------------------------------
Add a branch in validate_body_exprs() and update both sema_proc.py and
sema_func.py if the new statement requires unique proc-only or func-only
handling (supply it via the on_call_stmt or on_return_stmt callback slots, or
add a new callback parameter).
"""

from typing import Callable
from symbols import Symbol, SymbolTable, SemType, StructFieldInfo
from errors import SemanticError


# ---------------------------------------------------------------------------
# Debug / source-location helpers
# ---------------------------------------------------------------------------

def map_debug_line(debug: dict, fname: str | None, line: int | None) -> int | None:
    """Map a cleaned-source line number back to the original file line number.

    Uses orig_line_map_per_file from debug_info.  Returns line unchanged if
    no mapping is available.
    """
    if fname and isinstance(line, int):
        orig_map = (debug.get("orig_line_map_per_file") or {}).get(fname)
        if orig_map and 1 <= line <= len(orig_map):
            return orig_map[line - 1]
    return line


def attach_source_text(debug: dict, err: SemanticError, fname: str | None) -> None:
    """Attach the original source text to err.source_text when available."""
    if not fname:
        return
    orig_src = (debug.get("orig_source_lines_per_file") or {}).get(fname)
    if orig_src:
        err.source_text = "\n".join(orig_src)


def map_stmt_info(debug: dict, stmt) -> tuple | None:
    """Return (fname, mapped_line, col) for a statement, or None if not found.

    Looks up the statement by id() in the stmt_src debug map, then applies
    orig_line_map_per_file to translate cleaned-source lines to original lines.
    """
    stmt_src = debug.get("stmt_src") or {}
    info = stmt_src.get(id(stmt))
    if not info:
        return None
    if len(info) == 3:
        fname, line, _text = info
        col = 1
    else:
        fname, line, col, _text = info
    orig_map = (debug.get("orig_line_map_per_file") or {}).get(fname)
    if orig_map and isinstance(line, int) and 1 <= line <= len(orig_map):
        line = orig_map[line - 1]
    return fname, line, col


def _raise_with_stmt_info(e: SemanticError, debug: dict, stmt) -> None:
    """Re-raise e, attaching stmt source location if not already set."""
    info = map_stmt_info(debug, stmt)
    if info and getattr(e, "filename", None) is None:
        fname, line, col = info
        e_line = getattr(e, "line", None)
        if e_line is not None:
            orig_map = (debug.get("orig_line_map_per_file") or {}).get(fname)
            if orig_map and isinstance(e_line, int) and 1 <= e_line <= len(orig_map):
                e_line = orig_map[e_line - 1]
        else:
            e_line = line
        err_col = getattr(e, "col", None) or col
        err = SemanticError(e.message, line=e_line, col=err_col)
        err.filename = fname
        setattr(err, "_line_mapped", True)
        attach_source_text(debug, err, fname)
        raise err
    raise e


# ---------------------------------------------------------------------------
# Symbol / type helpers
# ---------------------------------------------------------------------------

def is_considered_initialized(sym: Symbol) -> bool:
    """Return True if sym is always safe to read without prior assignment.

    Covers: compile-time constants, fixed-address variables (hardware ports,
    @-declarations), variables with an initializer, and struct instances
    (whose fields are zero-initialised by convention).
    """
    if sym.is_const:
        return True
    if sym.address is not None:
        return True
    if sym.init is not None:
        return True
    if sym.type.is_struct:
        return True
    return False


def get_base_ident(node) -> str | None:
    """Return the root identifier name of an LHS expression, or None.

    Recurses through SubscriptExpr.array and FieldAccess.object chains.
    Returns None for pointer dereferences and other non-identifier forms.
    """
    from ast_nodes import Identifier, SubscriptExpr, FieldAccess
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, SubscriptExpr):
        return get_base_ident(node.array)
    if isinstance(node, FieldAccess):
        return get_base_ident(node.object)
    return None


# ---------------------------------------------------------------------------
# Uninitialized-variable checking
# ---------------------------------------------------------------------------

def check_uninitialized(
    expr,
    symtab,
    routine_name: str,
    initialized: set[str],
) -> None:
    """Raise SemanticError if a local variable is read before initialization.

    Walks the expression tree and checks every Identifier that refers to a local
    variable of `routine_name` against the `initialized` set (upper-case names).
    Arrays, constants, addressed variables, struct instances, and globals are
    silently skipped.

    symtab must support .lookup(name) returning a Symbol with proc_name, is_array.
    """
    from ast_nodes import (
        Identifier, UnaryExpr, BinaryExpr, SubscriptExpr, FieldAccess,
        DerefExpr, CallExpr, StructLiteral, ListInit, UnOp,
    )

    def walk(node) -> None:
        if isinstance(node, Identifier):
            try:
                sym = symtab.lookup(node.name)
            except Exception:
                return
            if sym.proc_name != routine_name:
                return
            if sym.is_array:
                return
            if is_considered_initialized(sym):
                return
            if sym.name.upper() not in initialized:
                raise SemanticError(
                    f"Use of uninitialized variable '{sym.name}'", node=node
                )
            return
        if isinstance(node, UnaryExpr):
            # Address-of (&var) does not read the variable's value.
            if node.op == UnOp.ADDROF:
                return
            walk(node.expr)
            return
        if isinstance(node, BinaryExpr):
            walk(node.left)
            walk(node.right)
            return
        if isinstance(node, SubscriptExpr):
            # Base address is always valid; only the index expression is read.
            walk(node.index)
            return
        if isinstance(node, FieldAccess):
            walk(node.object)
            return
        if isinstance(node, DerefExpr):
            walk(node.pointer)
            return
        if isinstance(node, CallExpr):
            for a in node.args:
                if a is not None:
                    walk(a)
            return
        if isinstance(node, StructLiteral):
            def walk_init(val) -> None:
                if isinstance(val, ListInit):
                    for item in val.values:
                        walk_init(item)
                    return
                walk(val)
            for v in node.values:
                walk_init(v)
            return

    walk(expr)


def mark_initialized_from_lhs(
    lhs,
    symtab,
    routine_name: str,
    initialized: set[str],
) -> None:
    """Mark the base variable of an LHS assignment expression as initialized.

    After `lhs = ...`, the root identifier (resolved through array subscripts
    and field accesses) is added to `initialized` if it belongs to routine_name.
    """
    name = get_base_ident(lhs)
    if name:
        try:
            sym = symtab.lookup(name)
        except Exception:
            return
        if sym.proc_name == routine_name:
            initialized.add(sym.name.upper())


# ---------------------------------------------------------------------------
# Port-write checking
# ---------------------------------------------------------------------------

def check_port_write(lhs, symtab, debug: dict, stmt) -> None:
    """Raise SemanticError if lhs is a write to a read-only port variable.

    Resolves the base identifier of lhs in symtab.  If the symbol is a port
    variable with write disabled (#RD-only), raises with source location from
    debug attached.  Field-level port modifiers take precedence over the
    symbol-level modifier.
    """
    from typing import Any
    base_name = get_base_ident(lhs)
    if base_name is None:
        return
    try:
        sym = symtab.lookup(base_name)
    except Exception:
        return
    if sym is None or not getattr(sym, 'is_port', False):
        return

    # Field-level modifiers override the symbol-level direction.
    field_name: str | None = None
    from ast_nodes import FieldAccess
    if isinstance(lhs, FieldAccess):
        field_name = lhs.field

    allowed: bool = True
    if field_name and sym.type.is_struct and sym.type.struct_info:
        field_info: StructFieldInfo | None = sym.type.struct_info.get_field(field_name.upper())
        if field_info and (field_info.port_wr is not None or field_info.port_rd is not None):
            allowed = bool(field_info.port_wr)
        else:
            allowed = bool(getattr(sym, 'port_wr', False))
    else:
        allowed = bool(getattr(sym, 'port_wr', False))

    if not allowed:
        err = SemanticError("Write to read-only port", node=lhs)
        info = map_stmt_info(debug, stmt)
        if info:
            fname, _line, _col = info
            err.filename = fname
            attach_source_text(debug, err, fname)
        raise err


# ---------------------------------------------------------------------------
# Local symbol table construction
# ---------------------------------------------------------------------------

def build_local_symtab(
    params,
    routine_name: str,
    struct_registry,
    debug: dict,
) -> SymbolTable:
    """Build and populate a SymbolTable by registering all parameters as Symbols.

    Resolves struct types via struct_registry when applicable.  On a
    duplicate-name error, attaches the source filename from the proc_src debug
    map before re-raising.

    Callers are responsible for subsequently attaching local declarations via
    DeclarationAnalyzer and wrapping in ScopedSymbolTable.
    """
    local_symtab = SymbolTable()
    local_symtab._proc_name = routine_name or ""

    for param in params:
        base_name_up: str = param.type.base.upper()
        is_struct = False
        struct_info = None
        if struct_registry and struct_registry.is_defined(base_name_up):
            is_struct = True
            struct_info = struct_registry.lookup(base_name_up)

        sem_type = SemType(
            base=param.type.base,
            is_pointer=param.type.is_pointer,
            is_struct=is_struct,
            struct_info=struct_info,
        )
        sym = Symbol(
            name=param.name,
            type=sem_type,
            is_const=False,
            const_value=None,
            is_array=param.is_array,
            array_len=None,   # parameters don't have a statically-known size
            init=None,
            address=None,
            is_volatile=False,
            proc_name=routine_name,
            array_dims=None,
        )
        try:
            local_symtab.define(sym, node=param)
        except SemanticError as e:
            proc_src_map = debug.get("proc_src") or {}
            info = proc_src_map.get(routine_name)
            fname = info[0] if info else None
            err = SemanticError(
                f"Parameter '{param.name}': {e.message}",
                line=param.line,
                col=param.col,
            )
            if fname:
                err.filename = fname
                attach_source_text(debug, err, fname)
            raise err

    return local_symtab


# ---------------------------------------------------------------------------
# Init-set construction
# ---------------------------------------------------------------------------

def build_init_set(params, local_tbl, routine_name: str) -> set[str]:
    """Return the initial set of upper-case names known to be initialized.

    Seeds with all parameter names (always initialized at call entry), then
    adds locals that are considered initialized by declaration (const, @addr,
    explicit initializer, or struct instance).
    """
    init_set: set[str] = set()
    for param in params:
        init_set.add(param.name.upper())
    if local_tbl is not None:
        for sym in list(local_tbl):
            if sym.proc_name != routine_name:
                continue
            if is_considered_initialized(sym):
                init_set.add(sym.name.upper())
    return init_set


# ---------------------------------------------------------------------------
# Unified body expression validator
# ---------------------------------------------------------------------------

def validate_body_exprs(
    statements: list,
    initialized: set[str],
    validate_expr_fn: Callable,
    symtab,
    debug: dict,
    routine_name: str,
    *,
    on_call_stmt: Callable | None = None,
    on_return_stmt: Callable | None = None,
) -> set[str]:
    """Type-check all expressions in a statement list and track initialization.

    Parameters
    ----------
    statements       : list of statement AST nodes
    initialized      : mutable set of upper-case local names known initialized
                       at entry; updated in-place and also returned
    validate_expr_fn : callable(expr, stmt=None, read_check_enabled=True) -> ExprType
                       Caller-supplied wrapper around ExprTypeChecker.check() that
                       maps any SemanticError to the enclosing statement's location.
    symtab           : SymbolLookup — used for uninit checks and mark_initialized
    debug            : debug_info dict for source-location attachment
    routine_name     : name of the enclosing proc or func
    on_call_stmt     : optional callable(stmt, initialized) — called for CallStmt.
                       Proc supplies a function that validates each argument for
                       uninitialized reads.  Func passes None.
    on_return_stmt   : optional callable(stmt, initialized) — called for ReturnStmt.
                       Proc supplies a function that type-checks the return
                       expression.  Func passes None (top-level returns are
                       handled separately in analyze_func for full return-type
                       checking).

    Returns the updated initialized set after processing all statements.

    Statement types handled
    -----------------------
    AssignStmt      LHS (write context) then RHS; port-write check; init tracking
    CallStmt        delegated to on_call_stmt if provided; skipped if None
    ReturnStmt      delegated to on_return_stmt if provided; skipped if None
    IfStmt          cond checked; then/else recursed; init set intersected
    WhileStmt       cond checked; body recursed
    RepeatUntilStmt body recursed; cond checked after; init propagated from body
    ForStmt         start/end/step checked; loop var marked initialized; body recursed
    SwitchStmt      expr checked; case labels validated (constant, in-range, unique);
                    case bodies recursed; init set intersected across all cases
    """
    from ast_nodes import (
        AssignStmt, ReturnStmt, IfStmt, WhileStmt, RepeatUntilStmt,
        ForStmt, SwitchStmt, CallStmt, IntLiteral,
    )
    from constsubst import subst_const
    from constfold import fold_expr
    from sema_types import ExprKind
    from symbols import SymbolTable
    from typing import cast

    def _check_uninit(expr, stmt) -> None:
        """check_uninitialized with stmt source-location attached on error."""
        try:
            check_uninitialized(expr, symtab, routine_name, initialized)
        except SemanticError as e:
            _raise_with_stmt_info(e, debug, stmt)

    for st in statements:
        if isinstance(st, AssignStmt):
            # Validate LHS first (write context) so a missing target is reported
            # before a missing source.
            validate_expr_fn(st.lhs, st, read_check_enabled=False)
            validate_expr_fn(st.rhs, st)
            _check_uninit(st.rhs, st)
            check_port_write(st.lhs, symtab, debug, st)
            mark_initialized_from_lhs(st.lhs, symtab, routine_name, initialized)

        elif on_call_stmt is not None and isinstance(st, CallStmt):
            on_call_stmt(st, initialized)

        elif on_return_stmt is not None and isinstance(st, ReturnStmt):
            on_return_stmt(st, initialized)

        elif isinstance(st, IfStmt):
            validate_expr_fn(st.cond, st)
            _check_uninit(st.cond, st)
            then_init = validate_body_exprs(
                st.then_body, set(initialized), validate_expr_fn,
                symtab, debug, routine_name,
                on_call_stmt=on_call_stmt, on_return_stmt=on_return_stmt,
            )
            if st.else_body:
                else_init = validate_body_exprs(
                    st.else_body, set(initialized), validate_expr_fn,
                    symtab, debug, routine_name,
                    on_call_stmt=on_call_stmt, on_return_stmt=on_return_stmt,
                )
                initialized = then_init & else_init
            else:
                initialized = set(initialized)

        elif isinstance(st, WhileStmt):
            validate_expr_fn(st.cond, st)
            _check_uninit(st.cond, st)
            validate_body_exprs(
                st.body, set(initialized), validate_expr_fn,
                symtab, debug, routine_name,
                on_call_stmt=on_call_stmt, on_return_stmt=on_return_stmt,
            )

        elif isinstance(st, RepeatUntilStmt):
            body_init = validate_body_exprs(
                st.body, set(initialized), validate_expr_fn,
                symtab, debug, routine_name,
                on_call_stmt=on_call_stmt, on_return_stmt=on_return_stmt,
            )
            initialized = body_init
            validate_expr_fn(st.cond, st)
            _check_uninit(st.cond, st)
            initialized = body_init

        elif isinstance(st, ForStmt):
            validate_expr_fn(st.start, st)
            _check_uninit(st.start, st)
            validate_expr_fn(st.end, st)
            _check_uninit(st.end, st)
            if st.step is not None:
                validate_expr_fn(st.step, st)
                _check_uninit(st.step, st)
            # Mark the loop variable as initialized before entering the body.
            try:
                loop_sym = symtab.lookup(st.var.name)
                if loop_sym.proc_name == routine_name:
                    initialized.add(loop_sym.name.upper())
            except Exception:
                pass
            validate_body_exprs(
                st.body, set(initialized), validate_expr_fn,
                symtab, debug, routine_name,
                on_call_stmt=on_call_stmt, on_return_stmt=on_return_stmt,
            )

        elif isinstance(st, SwitchStmt):
            sw_type = validate_expr_fn(st.expr, st)
            _check_uninit(st.expr, st)
            # Validate the switch structure: kind, case uniqueness, label ranges.
            try:
                if sw_type.kind != ExprKind.VALUE:
                    raise SemanticError("SWITCH expression must be a value", node=st.expr)

                seen_default = False
                seen_values: set[int] = set()
                case_inits: list[set[str]] = []

                for case in st.cases:
                    if case.is_default:
                        if seen_default:
                            raise SemanticError("Duplicate DEFAULT in SWITCH", node=st)
                        seen_default = True

                    for label in case.labels:
                        validate_expr_fn(label, st)
                        _check_uninit(label, st)
                        folded = fold_expr(subst_const(label, cast(SymbolTable, symtab)))
                        if not isinstance(folded, IntLiteral):
                            raise SemanticError("CASE label must be constant", node=label)
                        val = folded.value
                        if sw_type.sem_type.base == "BYTE" and not sw_type.sem_type.is_pointer:
                            if val < 0 or val > 0xFF:
                                raise SemanticError("CASE label out of range for BYTE", node=label)
                        if sw_type.sem_type.base == "WORD" and not sw_type.sem_type.is_pointer:
                            if val < 0 or val > 0xFFFF:
                                raise SemanticError("CASE label out of range for WORD", node=label)
                        if val in seen_values:
                            raise SemanticError("Duplicate CASE label", node=label)
                        seen_values.add(val)

                    case_inits.append(validate_body_exprs(
                        case.body, set(initialized), validate_expr_fn,
                        symtab, debug, routine_name,
                        on_call_stmt=on_call_stmt, on_return_stmt=on_return_stmt,
                    ))

            except SemanticError as e:
                _raise_with_stmt_info(e, debug, st)

            if case_inits:
                merged = set(initialized)
                for ci in case_inits:
                    merged &= ci
                initialized = merged

    return initialized
