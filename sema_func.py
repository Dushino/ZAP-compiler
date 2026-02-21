from dataclasses import dataclass
from typing import Any, cast
from typing import Any
from ast_nodes import Declaration, Expr, FuncDecl, Parameter, Parameter, ReturnStmt
from sema_types import ExprType
from sema_types import ExprType
from symbols import StructFieldInfo, Symbol, SymbolTable, ScopedSymbolTable, SymbolLookup, SemType, FuncTable, FuncSymbol
from errors import SemanticError
from sema import DeclarationAnalyzer
from sema_expr import ExprTypeChecker


@dataclass
class AnalyzedFunc:
    """Result of semantic analysis for a function."""
    ast: FuncDecl
    locals: list[Symbol]
    symtab: SymbolLookup
    ret_type: SemType


class FuncAnalyzer:
    """Performs semantic analysis for functions and their bodies."""
    def __init__(self, func_table: FuncTable, expr_tc: ExprTypeChecker, debug_info: dict | None = None, struct_registry=None) -> None:
        """Initialize with function table, expression type checker, and debug info."""
        self.func_table: FuncTable = func_table
        self.expr_tc: ExprTypeChecker = expr_tc
        self.debug = debug_info or {}
        self.struct_registry = struct_registry

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

    def analyze_decl(self, func: FuncDecl) -> None:
        """Register a function signature and enforce declaration rules."""
        ret_sem = self._resolve_ret_type(func.ret_type.base, func.ret_type.is_pointer)
        # Count required parameters (those without defaults)
        required_params: int = sum(1 for p in func.params if p.default_value is None)
        try:
            self.func_table.define(
                FuncSymbol(func.name, ret_sem, len(func.params), required_params)
            )
        except SemanticError as e:
            proc_src = self.debug.get("proc_src") or {}
            info = proc_src.get(func.name)
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

    def analyze_func(self, func: FuncDecl, global_symtab: SymbolTable) -> AnalyzedFunc:
        """Analyze a function body and build a scoped symbol table."""
        # lokály (stejně jako u PROC)
        local_symtab = SymbolTable()
        # Be defensive: func.name should be a string, but coerce to empty string if None to satisfy static typing
        local_symtab._proc_name = func.name or ""
        
        # add parameters to local symbol table
        for param in func.params:
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
                proc_name=func.name,
                array_dims=None
            )
            try:
                local_symtab.define(sym, node=param)
            except SemanticError as e:
                # Attach parameter source location
                raise SemanticError(f"Parameter '{param.name}': {e.message}", line=param.line, col=param.col)

        
        decl_an = DeclarationAnalyzer(
            local_symtab,
            self.struct_registry,
            self.func_table,
            global_symtab=global_symtab,
            debug_info=self.debug,
        )
        for d in func.locals:
            decl_an.analyze(d)

        scoped = ScopedSymbolTable(global_symtab)
        scoped.local = local_symtab

        # návratový typ
        ret_sem = self._resolve_ret_type(func.ret_type.base, func.ret_type.is_pointer)

        # update expr_tc to use scoped symbol table
        prev_symtab: SymbolLookup = self.expr_tc.symtab
        self.expr_tc.symtab = scoped

        # Helper to validate expressions with error reporting
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

        def validate_expr(expr, context_stmt=None, read_check_enabled: bool = True) -> ExprType:
            """Type-check an expression with contextual error reporting."""
            try:
                return self.expr_tc.check(expr, read_check_enabled)
            except SemanticError as e:
                if context_stmt:
                    info = _map_stmt_info(context_stmt)
                else:
                    info = None
                if info:
                    fname, line, col = info
                    err_line = getattr(e, "line", None) or line
                    # If the error line is from cleaned source, map it back to original
                    orig_map = (self.debug.get("orig_line_map_per_file") or {}).get(fname)
                    if orig_map and isinstance(err_line, int) and 1 <= err_line <= len(orig_map):
                        err_line = orig_map[err_line - 1]
                    err_col = getattr(e, "col", None) or col
                    err = SemanticError(e.message, line=err_line, col=err_col)
                    err.filename = fname
                    setattr(err, "_line_mapped", True)
                    orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                    if orig_src:
                        err.source_text = "\n".join(orig_src)
                    raise err
                raise

        # Validate all expressions in all statements
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
            """Type-check all expressions in a list of statements and track init state."""
            from ast_nodes import (
                AssignStmt, IfStmt, WhileStmt, RepeatUntilStmt, ForStmt,
                SwitchStmt, IntLiteral, Identifier, SubscriptExpr, FieldAccess,
                UnaryExpr, BinaryExpr, DerefExpr, CallExpr, UnOp, StructLiteral, ListInit
            )
            from constsubst import subst_const
            from constfold import fold_expr
            from sema_types import ExprKind

            def _check_uninitialized(expr, st) -> None:
                """Raise if a local identifier is read before initialization."""
                def walk(node) -> None:
                    if isinstance(node, Identifier):
                        try:
                            sym = self.expr_tc.symtab.lookup(node.name)
                        except Exception:
                            return
                        if sym.proc_name != func.name:
                            return
                        if sym.is_array:
                            return
                        if _is_considered_initialized(sym):
                            return
                        if sym.name.upper() not in initialized:
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
                        sym = self.expr_tc.symtab.lookup(name)
                    except Exception:
                        return
                    if sym.proc_name == func.name:
                        initialized.add(sym.name.upper())

            for st in statements:
                if isinstance(st, AssignStmt):
                    # Validate RHS (reads are checked)
                    validate_expr(st.rhs, st)
                    _check_uninitialized(st.rhs, st)
                    # Validate LHS but disable read-checking (this is a write context)
                    validate_expr(st.lhs, st, read_check_enabled=False)

                    # Now ensure write permission for port variables
                    def _get_base_ident(node):
                        """Extract base identifier name from an LHS expression."""
                        from ast_nodes import Identifier, SubscriptExpr, FieldAccess, DerefExpr
                        if isinstance(node, Identifier):
                            return node.name
                        if isinstance(node, SubscriptExpr):
                            return _get_base_ident(node.array)
                        if isinstance(node, FieldAccess):
                            # obj.field -> base can be Identifier or Deref/Subscript
                            return _get_base_ident(node.object)
                        # Other LHS forms are ignored for port checks
                        return None

                    base_name = _get_base_ident(st.lhs)
                    if base_name is not None:
                        try:
                            sym: Symbol = self.expr_tc.symtab.lookup(base_name)
                            # Field-level overrides
                            field_name: str | None = None
                            from ast_nodes import FieldAccess
                            if isinstance(st.lhs, FieldAccess):
                                field_name = st.lhs.field
                            if getattr(sym, 'is_port', False):
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
                                    # Attach contextual source info if available
                                    info = _map_stmt_info(st)
                                    err = SemanticError("Write to read-only port", node=st.lhs)
                                    if info:
                                        fname, _line, _col = info
                                        err.filename = fname
                                        orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                                        if orig_src:
                                            err.source_text = "\n".join(orig_src)
                                    raise err
                        except KeyError:
                            pass

                    _mark_initialized_from_lhs(st.lhs)

                elif isinstance(st, IfStmt):
                    validate_expr(st.cond, st)
                    _check_uninitialized(st.cond, st)
                    then_init = validate_stmt_exprs(st.then_body, set(initialized))
                    if st.else_body:
                        else_init = validate_stmt_exprs(st.else_body, set(initialized))
                        initialized = then_init & else_init
                    else:
                        initialized = set(initialized)
                elif isinstance(st, WhileStmt):
                    validate_expr(st.cond, st)
                    _check_uninitialized(st.cond, st)
                    validate_stmt_exprs(st.body, set(initialized))
                elif isinstance(st, RepeatUntilStmt):
                    body_init = validate_stmt_exprs(st.body, set(initialized))
                    initialized = body_init
                    validate_expr(st.cond, st)
                    _check_uninitialized(st.cond, st)
                    initialized = body_init
                elif isinstance(st, ForStmt):
                    validate_expr(st.start, st)
                    _check_uninitialized(st.start, st)
                    validate_expr(st.end, st)
                    _check_uninitialized(st.end, st)
                    if st.step is not None:
                        validate_expr(st.step, st)
                        _check_uninitialized(st.step, st)
                    # Mark loop variable as initialized before body
                    try:
                        loop_sym = self.expr_tc.symtab.lookup(st.var.name)
                        if loop_sym.proc_name == func.name:
                            initialized.add(loop_sym.name.upper())
                    except Exception:
                        pass
                    validate_stmt_exprs(st.body, set(initialized))
                elif isinstance(st, SwitchStmt):
                    sw_type = validate_expr(st.expr, st)
                    _check_uninitialized(st.expr, st)
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
                            validate_expr(label, st)
                            _check_uninitialized(label, st)
                            folded = fold_expr(subst_const(label, cast(SymbolTable, self.expr_tc.symtab)))
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
        for param in func.params:
            init_set.add(param.name.upper())
        local_tbl = getattr(scoped, "local", None)
        if local_tbl is not None:
            for sym in list(local_tbl):
                if sym.proc_name != func.name:
                    continue
                if _is_considered_initialized(sym):
                    init_set.add(sym.name.upper())

        validate_stmt_exprs(func.body, init_set)

        has_return = False
        from constfold import fold_expr
        from ast_nodes import IntLiteral
        for stmt in func.body:
            if isinstance(stmt, ReturnStmt):
                has_return = True
                # Type-check return expression; attach location if error occurs
                try:
                    et: ExprType | None = self.expr_tc.check(stmt.expr) if stmt.expr is not None else None
                except SemanticError as e:
                    info = _map_stmt_info(stmt)
                    if info:
                        fname, line, col = info
                        err_line = getattr(e, "line", None) or line
                        orig_map = (self.debug.get("orig_line_map_per_file") or {}).get(fname)
                        if orig_map and isinstance(err_line, int) and 1 <= err_line <= len(orig_map):
                            err_line = orig_map[err_line - 1]
                        err = SemanticError(e.message, line=err_line, col=col)
                        err.filename = fname
                        setattr(err, "_line_mapped", True)
                        raise err
                    raise

                # If return expression is a compile-time constant, validate it fits
                if stmt.expr is not None:
                    folded: Expr = fold_expr(stmt.expr)
                    if isinstance(folded, IntLiteral):
                        val: int = folded.value
                        # BYTE: must fit 0..255
                        if ret_sem.base == "BYTE" and not ret_sem.is_pointer and not ret_sem.is_struct:
                            if val < 0 or val > 0xFF:
                                msg = f"Return value {val} (0x{val:X}) does not fit in BYTE (0-255)"
                                raise SemanticError(msg, node=stmt.expr)
                        # WORD: must fit 0..65535
                        if ret_sem.base == "WORD" and not ret_sem.is_pointer and not ret_sem.is_struct:
                            if val < 0 or val > 0xFFFF:
                                msg = f"Return value {val} (0x{val:X}) does not fit in WORD (0-65535)"
                                raise SemanticError(msg, node=stmt.expr)

                if ret_sem.is_struct and not ret_sem.is_pointer:
                    if et is None or not et.sem_type.is_struct:
                        raise SemanticError(f"RETURN type mismatch: expected {ret_sem.base}", node=stmt)
                    # Allow struct literal or exact struct type match
                    if et.sem_type.base != ret_sem.base and et.sem_type.base != "STRUCT_LITERAL":
                        raise SemanticError(f"RETURN type mismatch: expected {ret_sem.base}, got {et.sem_type.base}", node=stmt)
                if et is not None and et.sem_type.base != ret_sem.base:
                    # Allow implicit narrowing from WORD to BYTE (use lower byte)
                    # Allow implicit widening from BYTE to WORD (zero-extend)
                    if (ret_sem.base == "BYTE" and et.sem_type.base == "WORD") or \
                       (ret_sem.base == "WORD" and et.sem_type.base == "BYTE") or \
                       (ret_sem.base == "LONG" and et.sem_type.base in {"BYTE", "WORD"}):
                        # This is allowed - implicit conversion
                        pass
                    else:
                        # Type mismatch - report error with context
                        stmt_src = self.debug.get("stmt_src") or {}
                        info = stmt_src.get(id(stmt))
                        if info:
                            if len(info) == 3:
                                fname, line, _text = info
                                col = 1
                            else:
                                fname, line, col, _text = info
                            msg: str = f"RETURN type mismatch: expected {ret_sem.base}, got {et.sem_type.base}"
                            err = SemanticError(msg, line=line, col=col)
                            err.filename = fname
                            raise err
                        # Attach the return statement node so an accurate source position is available
                        raise SemanticError(f"RETURN type mismatch: expected {ret_sem.base}, got {et.sem_type.base}", node=stmt)

        # restore previous symbol table
        self.expr_tc.symtab = prev_symtab

        if not has_return:
            proc_src = self.debug.get("proc_src") or {}
            info = proc_src.get(func.name)
            if info:
                if len(info) == 3:
                    fname, line, _text = info
                    col = 1
                else:
                    fname, line, col, _text = info
                err = SemanticError("FUNC must have RETURN", line=line, col=col)
                err.filename = fname
                raise err
            # Fall back to attaching the function AST node as context
            raise SemanticError("FUNC must have RETURN", node=func)

        # Return analyzed function info
        return AnalyzedFunc(
            ast=func,
            locals=list(local_symtab),
            symtab=scoped,
            ret_type=ret_sem
        )

    def _resolve_ret_type(self, base: str, is_pointer: bool) -> SemType:
        """Resolve function return type for enums and structs."""
        base_upper = base.upper()
        # Struct return (by value or pointer)
        if self.struct_registry and self.struct_registry.is_defined(base_upper):
            struct_info = self.struct_registry.lookup(base_upper)
            return SemType(base=base, is_pointer=is_pointer, is_struct=True, struct_info=struct_info)

        # Enum return -> map to enum base (BYTE/WORD)
        symtab = getattr(self.expr_tc, "symtab", None)
        enums = getattr(symtab, "_enums", None)
        if enums is None:
            parent = getattr(symtab, "parent", None)
            if parent is not None:
                enums = getattr(parent, "_enums", None)
        if enums and base_upper in enums and not is_pointer:
            enum_base = enums[base_upper].get("base", "BYTE")
            return SemType(base=enum_base, is_pointer=False)

        return SemType(base, is_pointer)
