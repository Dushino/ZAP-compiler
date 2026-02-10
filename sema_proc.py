from dataclasses import dataclass
from typing import Any, cast
from ast_nodes import Parameter, Declaration, ProcDecl, CallStmt
from symbols import StructFieldInfo, Symbol, SymbolTable, ProcTable, ProcSymbol, ScopedSymbolTable, SymbolLookup
from errors import SemanticError
from sema import DeclarationAnalyzer


@dataclass
class AnalyzedProc:
    ast: ProcDecl
    locals: list[Symbol]
    symtab: SymbolLookup   # ← změna tady


class ProcAnalyzer:
    def __init__(self, procs: ProcTable, debug_info: dict | None = None, struct_registry=None, func_table=None) -> None:
        self.procs: ProcTable = procs
        self.debug = debug_info or {}
        self.struct_registry = struct_registry
        self.func_table = func_table
        # Track the currently-analyzed ProcDecl. May be None when no proc is active.
        self.current_proc: ProcDecl | None = None

    def _map_debug_line(self, fname: str | None, line: int | None) -> int | None:
        if fname and isinstance(line, int):
            orig_map = (self.debug.get("orig_line_map_per_file") or {}).get(fname)
            if orig_map and 1 <= line <= len(orig_map):
                return orig_map[line - 1]
        return line

    def _attach_source_text(self, err: SemanticError, fname: str | None) -> None:
        if not fname:
            return
        orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
        if orig_src:
            err.source_text = "\n".join(orig_src)

    def analyze_decl(self, proc: ProcDecl) -> None:
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

            def validate_stmt_exprs(statements: list) -> None:
                from ast_nodes import AssignStmt, ReturnStmt, IfStmt, WhileStmt, ForStmt, SwitchStmt, Identifier, SubscriptExpr, FieldAccess, IntLiteral
                from constsubst import subst_const
                from constfold import fold_expr
                from sema_types import ExprKind
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

                    elif isinstance(st, ReturnStmt):
                        if st.expr is not None:
                            try:
                                tc.check(st.expr)
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
                        validate_stmt_exprs(st.then_body)
                        if st.else_body:
                            validate_stmt_exprs(st.else_body)
                    elif isinstance(st, WhileStmt):
                        try:
                            tc.check(st.cond)
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
                        validate_stmt_exprs(st.body)
                    elif isinstance(st, ForStmt):
                        try:
                            tc.check(st.start)
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
                        validate_stmt_exprs(st.body)
                    elif isinstance(st, SwitchStmt):
                        try:
                            sw_type = tc.check(st.expr)
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

                        for case in st.cases:
                            if case.is_default:
                                if seen_default:
                                    raise SemanticError("Duplicate DEFAULT in SWITCH", node=st)
                                seen_default = True

                            for label in case.labels:
                                # Validate label expression and ensure it is constant
                                tc.check(label)
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

                            validate_stmt_exprs(case.body)

            validate_stmt_exprs(proc.body)

        # validate procedure calls inside the body (must refer to defined procs)
        # set current_proc so analyze_call can check visibility
        self.current_proc = proc
        def walk(statements: list) -> None:
            from ast_nodes import CallStmt, IfStmt, WhileStmt, ForStmt, SwitchStmt
            for st in statements:
                if isinstance(st, CallStmt):
                    self.analyze_call(st)
                elif isinstance(st, IfStmt):
                    walk(st.then_body)
                    if st.else_body:
                        walk(st.else_body)
                elif isinstance(st, WhileStmt):
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




