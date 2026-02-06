from dataclasses import dataclass
from typing import Any
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
    ast: FuncDecl
    locals: list[Symbol]
    symtab: SymbolLookup
    ret_type: SemType


class FuncAnalyzer:
    def __init__(self, func_table: FuncTable, expr_tc: ExprTypeChecker, debug_info: dict | None = None, struct_registry=None) -> None:
        self.func_table: FuncTable = func_table
        self.expr_tc: ExprTypeChecker = expr_tc
        self.debug = debug_info or {}
        self.struct_registry = struct_registry

    def analyze_decl(self, func: FuncDecl) -> None:
        ret_sem = SemType(func.ret_type.base, func.ret_type.is_pointer)
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
                err = SemanticError(e.message, line=line, col=col)
                err.filename = fname
                raise err
            raise

    def analyze_func(self, func: FuncDecl, global_symtab: SymbolTable) -> AnalyzedFunc:
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

        
        decl_an = DeclarationAnalyzer(local_symtab, self.struct_registry, self.func_table, global_symtab=global_symtab)
        for d in func.locals:
            decl_an.analyze(d)

        scoped = ScopedSymbolTable(global_symtab)
        scoped.local = local_symtab

        # návratový typ
        ret_sem = SemType(func.ret_type.base, func.ret_type.is_pointer)

        # update expr_tc to use scoped symbol table
        prev_symtab: SymbolLookup = self.expr_tc.symtab
        self.expr_tc.symtab = scoped

        # Helper to validate expressions with error reporting
        def validate_expr(expr, context_stmt=None, read_check_enabled: bool = True) -> ExprType:
            try:
                return self.expr_tc.check(expr, read_check_enabled)
            except SemanticError as e:
                if context_stmt:
                    stmt_src = self.debug.get("stmt_src") or {}
                    info = stmt_src.get(id(context_stmt))
                else:
                    info = None
                if info:
                    if len(info) == 3:
                        fname, line, _text = info
                        col = 1
                    else:
                        fname, line, col, _text = info
                    err = SemanticError(e.message, line=line, col=col)
                    err.filename = fname
                    raise err
                raise

        # Validate all expressions in all statements
        def validate_stmt_exprs(statements: list) -> None:
            from ast_nodes import AssignStmt, IfStmt, WhileStmt, ForStmt
            for st in statements:
                if isinstance(st, AssignStmt):
                    # Validate RHS (reads are checked)
                    validate_expr(st.rhs, st)
                    # Validate LHS but disable read-checking (this is a write context)
                    validate_expr(st.lhs, st, read_check_enabled=False)

                    # Now ensure write permission for port variables
                    def _get_base_ident(node):
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
                                    stmt_src = self.debug.get("stmt_src") or {}
                                    info = stmt_src.get(id(st))
                                    if info:
                                        if len(info) == 3:
                                            fname, line, _text = info
                                            col = 1
                                        else:
                                            fname, line, col, _text = info
                                        err = SemanticError("Write to read-only port", line=line, col=col)
                                        err.filename = fname
                                        raise err
                                    # Fall back to providing the AST node so the error has a source location
                                    raise SemanticError("Write to read-only port", node=st)
                        except KeyError:
                            pass

                elif isinstance(st, IfStmt):
                    validate_expr(st.cond, st)
                    validate_stmt_exprs(st.then_body)
                    if st.else_body:
                        validate_stmt_exprs(st.else_body)
                elif isinstance(st, WhileStmt):
                    validate_expr(st.cond, st)
                    validate_stmt_exprs(st.body)
                elif isinstance(st, ForStmt):
                    validate_expr(st.start, st)
                    validate_expr(st.end, st)
                    if st.step is not None:
                        validate_expr(st.step, st)
                    validate_stmt_exprs(st.body)

        validate_stmt_exprs(func.body)

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
                    stmt_src = self.debug.get("stmt_src") or {}
                    info = stmt_src.get(id(stmt))
                    if info:
                        if len(info) == 3:
                            fname, line, _text = info
                            col = 1
                        else:
                            fname, line, col, _text = info
                        err = SemanticError(e.message, line=line, col=col)
                        err.filename = fname
                        raise err
                    raise

                # If return expression is a compile-time constant, validate it fits
                if stmt.expr is not None:
                    folded: Expr = fold_expr(stmt.expr)
                    if isinstance(folded, IntLiteral):
                        val: int = folded.value
                        # BYTE: must fit 0..255
                        if ret_sem.base == "BYTE" and not ret_sem.is_pointer:
                            if val < 0 or val > 0xFF:
                                stmt_src = self.debug.get("stmt_src") or {}
                                info = stmt_src.get(id(stmt))
                                msg = f"Return value {val} (0x{val:X}) does not fit in BYTE (0-255)"
                                if info:
                                    if len(info) == 3:
                                        fname, line, _text = info
                                        col = 1
                                    else:
                                        fname, line, col, _text = info
                                    err = SemanticError(msg, line=line, col=col)
                                    err.filename = fname
                                    raise err
                                raise SemanticError(msg, node=stmt)
                        # WORD: must fit 0..65535
                        if ret_sem.base == "WORD" and not ret_sem.is_pointer:
                            if val < 0 or val > 0xFFFF:
                                stmt_src = self.debug.get("stmt_src") or {}
                                info = stmt_src.get(id(stmt))
                                msg = f"Return value {val} (0x{val:X}) does not fit in WORD (0-65535)"
                                if info:
                                    if len(info) == 3:
                                        fname, line, _text = info
                                        col = 1
                                    else:
                                        fname, line, col, _text = info
                                    err = SemanticError(msg, line=line, col=col)
                                    err.filename = fname
                                    raise err
                                raise SemanticError(msg, node=stmt)

                if et is not None and et.sem_type.base != ret_sem.base:
                    # Allow implicit narrowing from WORD to BYTE (use lower byte)
                    # Allow implicit widening from BYTE to WORD (zero-extend)
                    if (ret_sem.base == "BYTE" and et.sem_type.base == "WORD") or \
                       (ret_sem.base == "WORD" and et.sem_type.base == "BYTE"):
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
