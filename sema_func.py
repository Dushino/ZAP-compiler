from dataclasses import dataclass
from typing import Any, cast
from ast_nodes import Declaration, Expr, FuncDecl, Parameter, ReturnStmt
from sema_types import ExprType
from symbols import StructFieldInfo, Symbol, SymbolTable, ScopedSymbolTable, SymbolLookup, SemType, FuncTable, FuncSymbol
from errors import SemanticError
from sema import DeclarationAnalyzer
from sema_expr import ExprTypeChecker
from sema_shared import (
    map_debug_line, attach_source_text, map_stmt_info,
    build_local_symtab, build_init_set,
    validate_body_exprs,
)


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
        return map_debug_line(self.debug, fname, line)

    def _attach_source_text(self, err: SemanticError, fname: str | None) -> None:
        """Attach original source text to an error when available."""
        attach_source_text(self.debug, err, fname)

    def analyze_decl(self, func: FuncDecl) -> None:
        """Register a function signature and enforce declaration rules."""
        ret_sem = self._resolve_ret_type(func.ret_type.base, func.ret_type.is_pointer)
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

    def analyze_func(self, func: FuncDecl, global_symtab: SymbolTable) -> 'AnalyzedFunc':
        """Analyze a function body and build a scoped symbol table."""

        # Build local symbol table and register all parameters.
        local_symtab = build_local_symtab(func.params, func.name, self.struct_registry, self.debug)

        # Analyze local variable declarations.
        decl_an = DeclarationAnalyzer(
            local_symtab,
            self.struct_registry,
            self.func_table,
            global_symtab=global_symtab,
            debug_info=self.debug,
        )
        for d in func.locals:
            decl_an.analyze(d)

        # Scoped lookup: locals first, then globals.
        scoped = ScopedSymbolTable(global_symtab)
        scoped.local = local_symtab

        ret_sem = self._resolve_ret_type(func.ret_type.base, func.ret_type.is_pointer)

        # Point the shared expression type-checker at the function's local scope.
        prev_symtab: SymbolLookup = self.expr_tc.symtab
        self.expr_tc.symtab = scoped

        def validate_expr(expr, context_stmt=None, read_check_enabled: bool = True) -> ExprType:
            """Type-check an expression with contextual error reporting.

            Applies two levels of line mapping: map_stmt_info maps the stmt's
            source position, then a second pass re-maps the error's own line in
            case it came from an AST node whose line is still in cleaned-source
            space.
            """
            try:
                return self.expr_tc.check(expr, read_check_enabled)
            except SemanticError as e:
                if context_stmt:
                    info = map_stmt_info(self.debug, context_stmt)
                else:
                    info = None
                if info:
                    fname, line, col = info
                    e_line = getattr(e, "line", None)
                    if e_line is not None:
                        # e.line is a clean-source line from an AST node — map to original
                        orig_map = (self.debug.get("orig_line_map_per_file") or {}).get(fname)
                        if orig_map and isinstance(e_line, int) and 1 <= e_line <= len(orig_map):
                            e_line = orig_map[e_line - 1]
                    else:
                        e_line = line  # map_stmt_info already returned the original line
                    err_col = getattr(e, "col", None) or col
                    err = SemanticError(e.message, line=e_line, col=err_col)
                    err.filename = fname
                    setattr(err, "_line_mapped", True)
                    orig_src = (self.debug.get("orig_source_lines_per_file") or {}).get(fname)
                    if orig_src:
                        err.source_text = "\n".join(orig_src)
                    raise err
                raise

        # Type-check all statements in the body.
        # on_return_stmt is None: top-level returns are validated separately
        # below so that full return-type checking can be applied.
        init_set = build_init_set(func.params, scoped.local, func.name)
        validate_body_exprs(
            func.body, init_set, validate_expr, self.expr_tc.symtab,
            self.debug, func.name,
        )

        # Validate return statements: type-check expression and check return type.
        has_return = False
        from constfold import fold_expr
        from ast_nodes import IntLiteral
        for stmt in func.body:
            if isinstance(stmt, ReturnStmt):
                has_return = True
                try:
                    et: ExprType | None = self.expr_tc.check(stmt.expr) if stmt.expr is not None else None
                except SemanticError as e:
                    info = map_stmt_info(self.debug, stmt)
                    if info:
                        fname, line, col = info
                        e_line = getattr(e, "line", None)
                        if e_line is not None:
                            orig_map = (self.debug.get("orig_line_map_per_file") or {}).get(fname)
                            if orig_map and isinstance(e_line, int) and 1 <= e_line <= len(orig_map):
                                e_line = orig_map[e_line - 1]
                        else:
                            e_line = line
                        err = SemanticError(e.message, line=e_line, col=col)
                        err.filename = fname
                        setattr(err, "_line_mapped", True)
                        raise err
                    raise

                # Validate that the return value fits the declared return type.
                if stmt.expr is not None:
                    folded: Expr = fold_expr(stmt.expr)
                    if isinstance(folded, IntLiteral):
                        val: int = folded.value
                        if ret_sem.base == "BYTE" and not ret_sem.is_pointer and not ret_sem.is_struct:
                            if val < 0 or val > 0xFF:
                                msg = f"Return value {val} (0x{val:X}) does not fit in BYTE (0-255)"
                                raise SemanticError(msg, node=stmt.expr)
                        if ret_sem.base == "WORD" and not ret_sem.is_pointer and not ret_sem.is_struct:
                            if val < 0 or val > 0xFFFF:
                                msg = f"Return value {val} (0x{val:X}) does not fit in WORD (0-65535)"
                                raise SemanticError(msg, node=stmt.expr)

                # Helper to raise a type-mismatch error with source context.
                def _ret_type_error(msg: str) -> None:
                    info = map_stmt_info(self.debug, stmt)
                    if info:
                        fname, line, col = info
                        err = SemanticError(msg, line=line, col=col)
                        err.filename = fname
                        self._attach_source_text(err, fname)
                        raise err
                    raise SemanticError(msg, node=stmt)

                if et is None:
                    _ret_type_error("RETURN in function must have an expression")

                ret_base: str = ret_sem.base.upper()
                expr_base: str = et.sem_type.base.upper()
                ret_is_ptr: bool = ret_sem.is_pointer
                expr_is_ptr: bool = et.sem_type.is_pointer

                # Struct return: exact type match required (or struct literal).
                if ret_sem.is_struct and not ret_is_ptr:
                    if not et.sem_type.is_struct:
                        _ret_type_error(f"RETURN type mismatch: expected struct '{ret_base}', got {expr_base}")
                    if expr_base != ret_base and expr_base != "STRUCT_LITERAL":
                        _ret_type_error(f"RETURN type mismatch: expected struct '{ret_base}', got struct '{expr_base}'")
                elif et.sem_type.is_struct and not expr_is_ptr:
                    _ret_type_error(f"RETURN type mismatch: expected {ret_base}, got struct '{expr_base}'")
                else:
                    # Scalar / pointer return: all scalar-to-scalar and
                    # pointer<->WORD conversions are permitted.
                    SCALARS = {"BYTE", "WORD", "LONG"}

                    def _effective_base(base: str, is_ptr: bool) -> str:
                        """Map pointer types to WORD for compatibility checking."""
                        return "WORD" if is_ptr else base

                    eff_ret = _effective_base(ret_base, ret_is_ptr)
                    eff_expr = _effective_base(expr_base, expr_is_ptr)
                    if eff_ret not in SCALARS or eff_expr not in SCALARS:
                        _ret_type_error(
                            f"RETURN type mismatch: expected {ret_base}{'^ ' if ret_is_ptr else ''}, "
                            f"got {expr_base}{'^' if expr_is_ptr else ''}"
                        )

        # Restore the shared expression type-checker to the caller's scope.
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
            raise SemanticError("FUNC must have RETURN", node=func)

        return AnalyzedFunc(
            ast=func,
            locals=list(local_symtab),
            symtab=scoped,
            ret_type=ret_sem
        )

    def _resolve_ret_type(self, base: str, is_pointer: bool) -> SemType:
        """Resolve function return type, handling enums and structs."""
        base_upper = base.upper()
        if self.struct_registry and self.struct_registry.is_defined(base_upper):
            struct_info = self.struct_registry.lookup(base_upper)
            return SemType(base=base, is_pointer=is_pointer, is_struct=True, struct_info=struct_info)

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
