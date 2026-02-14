from dataclasses import dataclass
from typing import Any, cast
from ast_nodes import Parameter, Declaration, ProcDecl, CallStmt
from symbols import StructFieldInfo, Symbol, SymbolTable, ProcTable, ProcSymbol, ScopedSymbolTable, SymbolLookup
from errors import SemanticError
from sema import DeclarationAnalyzer


@dataclass
class AnalyzedProc:
    """Result of semantic analysis for a procedure."""
    ast: ProcDecl
    locals: list[Symbol]
    symtab: SymbolLookup   # ← změna tady


class ProcAnalyzer:
    """Performs semantic analysis for procedures and their bodies."""
    def __init__(self, procs: ProcTable, debug_info: dict | None = None, struct_registry=None, func_table=None) -> None:
        """Initialize with procedure table and optional debug/struct info."""
        self.procs: ProcTable = procs
        self.debug = debug_info or {}
        self.struct_registry = struct_registry
        self.func_table = func_table
        # Track the currently-analyzed ProcDecl. May be None when no proc is active.
        self.current_proc: ProcDecl | None = None

    def _map_debug_line(self, fname: str | None, line: int | None) -> int | None:
        """Map cleaned-source line numbers back to original file lines."""
        if fname and isinstance(line, int):
            orig_map = (self.debug.get("orig_line_map_per_file") or {}).get(fname)
            if orig_map and 1 <= line <= len(orig_map):
                return orig_map[line - 1]
        return line

    def _attach_source_text(self, err: SemanticError, fname: str | None) -> None:
        """Attach original source text to an error when available."""
        if not fname:
            return
        orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
        if orig_src:
            err.source_text = "\n".join(orig_src)

    def analyze_decl(self, proc: ProcDecl) -> None:
        """Register a procedure signature and enforce declaration rules."""
        # Count required parameters (those without defaults)
        required_params: int = sum(1 for p in proc.params if p.default_value is None)
        # Determine owner file and exported flag (set by module system via debug maps)
        proc_src_map = self.debug.get('proc_src') or {}
        owner = None
        owner_is_module = False
        info = proc_src_map.get(proc.name)
        if info:
            # info may be (filename, line, col, text) or (filename, line, text)
            owner = info[0]
            file_is_module_map = self.debug.get('file_is_module') or {}
            owner_is_module = file_is_module_map.get(owner, False)
        exported = True
        if owner_is_module and getattr(proc, 'noexport', False):
            exported = False
        try:
            psym = ProcSymbol(proc.name, len(proc.params), required_params, owner_file=owner, exported=exported)
            # Provide the ProcDecl AST node so the ProcTable can attach source context on errors
            self.procs.define(psym, node=proc)
        except SemanticError as e:
            # Attach location of PROC header
            proc_src_map = self.debug.get("proc_src") or {}
            info = proc_src_map.get(proc.name)
            if info:
                if len(info) == 3:
                    fname, line, _text = info
                    col = 1
                else:
                    fname, line, col, _text = info
                mapped_line = self._map_debug_line(fname, line)
                err = SemanticError(e.message, line=mapped_line, col=col)
                err.filename = fname
                self._attach_source_text(err, fname)
                raise err
            raise

    def analyze_call(self, call: CallStmt) -> None:
        """Validate a procedure call against the procedure table."""
        # Determine caller file if available to support module visibility checks
        caller_file = None
        if self.current_proc is not None:
            proc_src_map = self.debug.get('proc_src') or {}
            cur_info = proc_src_map.get(self.current_proc.name)
            if cur_info:
                caller_file = cur_info[0]
        try:
            proc_sym: ProcSymbol = self.procs.lookup(call.name, caller_file=caller_file)
        except SemanticError as e:
            # If a function exists with this name, report parameter issues at arg position
            if self.func_table is not None:
                try:
                    fs = self.func_table.lookup(call.name, node=call)
                    if len(call.args) > fs.param_count:
                        extra_arg = call.args[fs.param_count]
                        raise SemanticError(
                            f"Function '{call.name}' expects {fs.param_count} parameters, but {len(call.args)} were provided",
                            node=extra_arg
                        )
                    if len(call.args) < fs.required_params:
                        raise SemanticError(
                            f"Function '{call.name}' expects {fs.param_count} parameters, but {len(call.args)} were provided",
                            node=call
                        )
                except SemanticError:
                    raise
                except KeyError:
                    pass

            # Re-raise with source location attached
            stmt_src_map = self.debug.get("stmt_src") or {}
            info = stmt_src_map.get(id(call))
            if info:
                if len(info) == 3:
                    fname, line, _text = info
                    col = 1
                else:
                    fname, line, col, _text = info
                mapped_line = self._map_debug_line(fname, line)
                err = SemanticError(e.message, line=mapped_line, col=col)
                err.filename = fname
                self._attach_source_text(err, fname)
                raise err
            raise
        # Allow arguments from required_params to param_count
        if len(call.args) < proc_sym.required_params or len(call.args) > proc_sym.param_count:
            msg: str = (
                f"Procedure '{call.name}' expects {proc_sym.param_count} parameters, "
                f"but {len(call.args)} were provided"
            )
            stmt_src_map = self.debug.get("stmt_src") or {}
            info = stmt_src_map.get(id(call))
            if info:
                if len(info) == 3:
                    fname, line, _text = info
                    col = 1
                else:
                    fname, line, col, _text = info
                mapped_line = self._map_debug_line(fname, line)
                err = SemanticError(msg, line=mapped_line, col=col)
                err.filename = fname
                self._attach_source_text(err, fname)
                raise err
            # Attach call node to provide source location when available
            raise SemanticError(msg, node=call)

    def analyze_proc(
        self,
        proc: ProcDecl,
        global_symtab: SymbolTable
        ) -> AnalyzedProc:
        """Analyze a procedure body and build a scoped symbol table."""

        local_symtab = SymbolTable()
        # Be defensive: proc.name should be a string, but coerce to empty string if None to satisfy static typing
        local_symtab._proc_name = proc.name or ""

        # add parameters to local symbol table
        for param in proc.params:
            from symbols import SemType, Symbol
            # Check if parameter type is a struct
            base_name: str = param.type.base.upper()
            is_struct = False
            struct_info = None
            
            if self.struct_registry and self.struct_registry.is_defined(base_name):
                is_struct = True
                struct_info = self.struct_registry.lookup(base_name)
            
            sem_type = SemType(
                base=param.type.base,
                is_pointer=param.type.is_pointer,
                is_struct=is_struct,
                struct_info=struct_info
            )
            sym = Symbol(
                name=param.name,
                type=sem_type,
                is_const=False,
                const_value=None,
                is_array=param.is_array,
                array_len=None,  # parameters don't have known size
                init=None,
                address=None,
                is_volatile=False,
                proc_name=proc.name,
                array_dims=None
            )
            try:
                # Attach the parameter AST node for precise error reporting
                local_symtab.define(sym, node=param)
            except SemanticError as e:
                # Attach parameter source location
                raise SemanticError(f"Parameter '{param.name}': {e.message}", line=param.line, col=param.col)


        # Validate parameter ordering: parameters with defaults must come after those without
        has_default = False
        for i, param in enumerate(proc.params):
            if param.default_value is not None:
                has_default = True
            elif has_default:
                # Found a non-default parameter after a default parameter
                from errors import CompileError
                raise CompileError(
                    f"In procedure '{proc.name}': non-default parameter '{param.name}' "
                    f"cannot follow parameters with default values",
                    param.line, param.col
                )

        decl_an = DeclarationAnalyzer(
            local_symtab,
            self.struct_registry,
            self.func_table,
            global_symtab=global_symtab,
            debug_info=self.debug,
        )
        for d in proc.locals:
            decl_an.analyze(d)

        # scoped lookup: nejdřív lokály, pak globály
        scoped = ScopedSymbolTable(global_symtab)
        scoped.local = local_symtab

        # Type-check expressions in statements to validate variable references
        if self.func_table is not None:
            from sema_expr import ExprTypeChecker
            tc = ExprTypeChecker(scoped, self.func_table, self.struct_registry)

            def _map_stmt_info(stmt):
                """Lookup source info for a statement using debug maps."""
                stmt_src = self.debug.get("stmt_src") or {}
                info = stmt_src.get(id(stmt))
                if not info:
                    return None
                if len(info) == 3:
                    fname, line, _text = info
                    col = 1
                else:
                    fname, line, col, _text = info

                orig_map = (self.debug.get("orig_line_map_per_file") or {}).get(fname)
                if orig_map and isinstance(line, int) and 1 <= line <= len(orig_map):
                    line = orig_map[line - 1]
                return fname, line, col

            def _is_considered_initialized(sym: "Symbol") -> bool:
                if sym.is_const:
                    return True
                if sym.address is not None:
                    return True
                if sym.init is not None:
                    return True
                if sym.type.is_struct:
                    return True
                return False

            def validate_stmt_exprs(statements: list, initialized: set[str]) -> set[str]:
                """Type-check expressions within a list of statements and track init state."""
                from ast_nodes import (
                    AssignStmt, ReturnStmt, IfStmt, WhileStmt, RepeatUntilStmt,
                    ForStmt, SwitchStmt, CallStmt, Identifier, SubscriptExpr,
                    FieldAccess, IntLiteral, UnaryExpr, BinaryExpr, DerefExpr,
                    CallExpr, UnOp, StructLiteral, ListInit
                )
                from constsubst import subst_const
                from constfold import fold_expr
                from sema_types import ExprKind

                def _local_name(sym: "Symbol") -> str:
                    return sym.name.upper()

                def _check_uninitialized(expr, st) -> None:
                    """Raise if a local identifier is read before initialization."""
                    def walk(node) -> None:
                        if isinstance(node, Identifier):
                            try:
                                sym = tc.symtab.lookup(node.name)
                            except Exception:
                                return
                            if sym.proc_name != proc.name:
                                return
                            if _is_considered_initialized(sym):
                                return
                            if _local_name(sym) not in initialized:
                                raise SemanticError(f"Use of uninitialized variable '{sym.name}'", node=node)
                            return
                        if isinstance(node, UnaryExpr):
                            if node.op == UnOp.ADDROF:
                                return
                            walk(node.expr)
                            return
                        if isinstance(node, BinaryExpr):
                            walk(node.left)
                            walk(node.right)
                            return
                        if isinstance(node, SubscriptExpr):
                            # Base address is always valid; check index expression only
                            walk(node.index)
                            return
                        if isinstance(node, FieldAccess):
                            # Address of struct is always valid; only check object for reads
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

                def _mark_initialized_from_lhs(lhs) -> None:
                    def base_ident(node):
                        if isinstance(node, Identifier):
                            return node.name
                        if isinstance(node, SubscriptExpr):
                            return base_ident(node.array)
                        if isinstance(node, FieldAccess):
                            return base_ident(node.object)
                        return None
                    name = base_ident(lhs)
                    if name:
                        try:
                            sym = tc.symtab.lookup(name)
                        except Exception:
                            return
                        if sym.proc_name == proc.name:
                            initialized.add(sym.name.upper())

                for st in statements:
                    if isinstance(st, AssignStmt):
                        # LHS write context: disable read checks (check LHS first so missing LHS is reported instead of RHS)
                        try:
                            tc.check(st.lhs, read_check_enabled=False)
                        except SemanticError as e:
                            info = _map_stmt_info(st)
                            if info and getattr(e, "filename", None) is None:
                                fname, line, col = info
                                err_line = getattr(e, "line", None) or line
                                err_col = getattr(e, "col", None) or col
                                err = SemanticError(e.message, line=err_line, col=err_col)
                                err.filename = fname
                                orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                                if orig_src:
                                    err.source_text = "\n".join(orig_src)
                                raise err
                            raise
                        # RHS is read context
                        try:
                            tc.check(st.rhs)
                            _check_uninitialized(st.rhs, st)
                        except SemanticError as e:
                            info = _map_stmt_info(st)
                            if info and getattr(e, "filename", None) is None:
                                fname, line, col = info
                                err_line = getattr(e, "line", None) or line
                                err_col = getattr(e, "col", None) or col
                                err = SemanticError(e.message, line=err_line, col=err_col)
                                err.filename = fname
                                orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                                if orig_src:
                                    err.source_text = "\n".join(orig_src)
                                raise err
                            raise

                        # Check write permission for ports
                        def _get_base_ident(node):
                            """Extract base identifier name from an LHS expression."""
                            from ast_nodes import Identifier, SubscriptExpr, FieldAccess
                            if isinstance(node, Identifier):
                                return node.name
                            if isinstance(node, SubscriptExpr):
                                return _get_base_ident(node.array)
                            if isinstance(node, FieldAccess):
                                return _get_base_ident(node.object)
                            return None

                        base_name = _get_base_ident(st.lhs)
                        if base_name is not None:
                            # Look up symbol via the SymbolLookup API and handle failures
                            # Symbol lookup may fail; start with None and populate if found
                            sym = None
                            try:
                                sym = tc.symtab.lookup(base_name)
                            except Exception:
                                sym = None

                            # If symbol lookup failed, skip port checks
                            if sym is None:
                                continue
                            # Narrow type for type checker by confirming presence of expected attributes
                            if getattr(sym, 'name', None) is None:
                                continue  # couldn't resolve symbol - skip port checks

                            # If this is a field access, consider field-level override
                            field_name: str | None = None
                            from ast_nodes import FieldAccess
                            if isinstance(st.lhs, FieldAccess):
                                field_name = st.lhs.field
                            # Ensure sym is not None before attribute access (helps static analysis)
                            if sym is not None and getattr(sym, 'is_port', False):
                                # Determine whether writes are allowed: field overrides symbol
                                allowed = True
                                if field_name and sym.type.is_struct and sym.type.struct_info:
                                    field_info: StructFieldInfo | None = sym.type.struct_info.get_field(field_name.upper())
                                    if field_info and (field_info.port_wr is not None or field_info.port_rd is not None):
                                        allowed = bool(field_info.port_wr)
                                    else:
                                        allowed: Any | bool = getattr(sym, 'port_wr', False)
                                else:
                                    allowed: Any | bool = getattr(sym, 'port_wr', False)

                                if not allowed:
                                    info = _map_stmt_info(st)
                                    err = SemanticError("Write to read-only port", node=st.lhs)
                                    if info:
                                        fname, _line, _col = info
                                        err.filename = fname
                                        orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                                        if orig_src:
                                            err.source_text = "\n".join(orig_src)
                                    raise err

                        _mark_initialized_from_lhs(st.lhs)

                    elif isinstance(st, CallStmt):
                        # Validate call arguments for uninitialized reads
                        for a in st.args:
                            if a is None:
                                continue
                            try:
                                if not isinstance(a, StructLiteral):
                                    tc.check(a)
                                _check_uninitialized(a, st)
                            except SemanticError as e:
                                info = _map_stmt_info(st)
                                if info and getattr(e, "filename", None) is None:
                                    fname, line, col = info
                                    err_line = getattr(e, "line", None) or line
                                    err_col = getattr(e, "col", None) or col
                                    err = SemanticError(e.message, line=err_line, col=err_col)
                                    err.filename = fname
                                    orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                                    if orig_src:
                                        err.source_text = "\n".join(orig_src)
                                    raise err
                                raise

                    elif isinstance(st, ReturnStmt):
                        if st.expr is not None:
                            try:
                                tc.check(st.expr)
                                _check_uninitialized(st.expr, st)
                            except SemanticError as e:
                                info = _map_stmt_info(st)
                                if info and getattr(e, "filename", None) is None:
                                    fname, line, col = info
                                    err_line = getattr(e, "line", None) or line
                                    err_col = getattr(e, "col", None) or col
                                    err = SemanticError(e.message, line=err_line, col=err_col)
                                    err.filename = fname
                                    orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                                    if orig_src:
                                        err.source_text = "\n".join(orig_src)
                                    raise err
                                raise
                    elif isinstance(st, IfStmt):
                        try:
                            tc.check(st.cond)
                            _check_uninitialized(st.cond, st)
                        except SemanticError as e:
                            info = _map_stmt_info(st)
                            if info and getattr(e, "filename", None) is None:
                                fname, line, col = info
                                err_line = getattr(e, "line", None) or line
                                err_col = getattr(e, "col", None) or col
                                err = SemanticError(e.message, line=err_line, col=err_col)
                                err.filename = fname
                                orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                                if orig_src:
                                    err.source_text = "\n".join(orig_src)
                                raise err
                            raise
                        then_init = validate_stmt_exprs(st.then_body, set(initialized))
                        if st.else_body:
                            else_init = validate_stmt_exprs(st.else_body, set(initialized))
                            initialized = then_init & else_init
                        else:
                            initialized = set(initialized)
                    elif isinstance(st, WhileStmt):
                        try:
                            tc.check(st.cond)
                            _check_uninitialized(st.cond, st)
                        except SemanticError as e:
                            info = _map_stmt_info(st)
                            if info and getattr(e, "filename", None) is None:
                                fname, line, col = info
                                err_line = getattr(e, "line", None) or line
                                err_col = getattr(e, "col", None) or col
                                err = SemanticError(e.message, line=err_line, col=err_col)
                                err.filename = fname
                                orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                                if orig_src:
                                    err.source_text = "\n".join(orig_src)
                                raise err
                            raise
                        validate_stmt_exprs(st.body, set(initialized))
                    elif isinstance(st, RepeatUntilStmt):
                        body_init = validate_stmt_exprs(st.body, set(initialized))
                        initialized = body_init
                        try:
                            tc.check(st.cond)
                            _check_uninitialized(st.cond, st)
                        except SemanticError as e:
                            info = _map_stmt_info(st)
                            if info and getattr(e, "filename", None) is None:
                                fname, line, col = info
                                err_line = getattr(e, "line", None) or line
                                err_col = getattr(e, "col", None) or col
                                err = SemanticError(e.message, line=err_line, col=err_col)
                                err.filename = fname
                                orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                                if orig_src:
                                    err.source_text = "\n".join(orig_src)
                                raise err
                            raise
                        initialized = body_init
                    elif isinstance(st, ForStmt):
                        try:
                            tc.check(st.start)
                            _check_uninitialized(st.start, st)
                        except SemanticError as e:
                            info = _map_stmt_info(st)
                            if info and getattr(e, "filename", None) is None:
                                fname, line, col = info
                                err_line = getattr(e, "line", None) or line
                                err_col = getattr(e, "col", None) or col
                                err = SemanticError(e.message, line=err_line, col=err_col)
                                err.filename = fname
                                orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                                if orig_src:
                                    err.source_text = "\n".join(orig_src)
                                raise err
                            raise
                        try:
                            tc.check(st.end)
                            _check_uninitialized(st.end, st)
                        except SemanticError as e:
                            info = _map_stmt_info(st)
                            if info and getattr(e, "filename", None) is None:
                                fname, line, col = info
                                err_line = getattr(e, "line", None) or line
                                err_col = getattr(e, "col", None) or col
                                err = SemanticError(e.message, line=err_line, col=err_col)
                                err.filename = fname
                                orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                                if orig_src:
                                    err.source_text = "\n".join(orig_src)
                                raise err
                            raise
                        if st.step is not None:
                            try:
                                tc.check(st.step)
                                _check_uninitialized(st.step, st)
                            except SemanticError as e:
                                info = _map_stmt_info(st)
                                if info and getattr(e, "filename", None) is None:
                                    fname, line, col = info
                                    err_line = getattr(e, "line", None) or line
                                    err_col = getattr(e, "col", None) or col
                                    err = SemanticError(e.message, line=err_line, col=err_col)
                                    err.filename = fname
                                    orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                                    if orig_src:
                                        err.source_text = "\n".join(orig_src)
                                    raise err
                                raise
                        # Mark loop variable as initialized before body
                        try:
                            loop_sym = tc.symtab.lookup(st.var.name)
                            if loop_sym.proc_name == proc.name:
                                initialized.add(_local_name(loop_sym))
                        except Exception:
                            pass
                        validate_stmt_exprs(st.body, set(initialized))
                    elif isinstance(st, SwitchStmt):
                        try:
                            sw_type = tc.check(st.expr)
                            _check_uninitialized(st.expr, st)
                        except SemanticError as e:
                            info = _map_stmt_info(st)
                            if info and getattr(e, "filename", None) is None:
                                fname, line, col = info
                                err = SemanticError(e.message, line=line, col=col)
                                err.filename = fname
                                raise err
                            raise

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
                                # Validate label expression and ensure it is constant
                                tc.check(label)
                                _check_uninitialized(label, st)
                                folded = fold_expr(subst_const(label, cast(SymbolTable, tc.symtab)))
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

                            case_inits.append(validate_stmt_exprs(case.body, set(initialized)))

                        if case_inits:
                            merged = set(initialized)
                            for ci in case_inits:
                                merged &= ci
                            initialized = merged

                return initialized

            # Build initial initialized set: parameters and locals with init/@/const
            init_set: set[str] = set()
            for param in proc.params:
                init_set.add(param.name.upper())
            local_tbl = getattr(scoped, "local", None)
            if local_tbl is not None:
                for sym in list(local_tbl):
                    if sym.proc_name != proc.name:
                        continue
                    if _is_considered_initialized(sym):
                        init_set.add(sym.name.upper())

            validate_stmt_exprs(proc.body, init_set)

        # validate procedure calls inside the body (must refer to defined procs)
        # set current_proc so analyze_call can check visibility
        self.current_proc = proc
        def walk(statements: list) -> None:
            from ast_nodes import CallStmt, IfStmt, WhileStmt, RepeatUntilStmt, ForStmt, SwitchStmt
            for st in statements:
                if isinstance(st, CallStmt):
                    self.analyze_call(st)
                elif isinstance(st, IfStmt):
                    walk(st.then_body)
                    if st.else_body:
                        walk(st.else_body)
                elif isinstance(st, WhileStmt):
                    walk(st.body)
                elif isinstance(st, RepeatUntilStmt):
                    walk(st.body)
                elif isinstance(st, ForStmt):
                    walk(st.body)
                elif isinstance(st, SwitchStmt):
                    for case in st.cases:
                        walk(case.body)
                # other statements (AssignStmt, ReturnStmt, Break/Continue) need no proc validation

        walk(proc.body)
        # clear current_proc after analysis
        self.current_proc = None

        return AnalyzedProc(
            ast=proc,
            locals=list(local_symtab),   # ← TADY vzniká local_symbols
            symtab=scoped
        )




