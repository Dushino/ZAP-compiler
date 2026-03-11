from dataclasses import dataclass
from typing import Any, cast
from ast_nodes import Parameter, Declaration, ProcDecl, CallStmt
from symbols import StructFieldInfo, Symbol, SymbolTable, ProcTable, ProcSymbol, ScopedSymbolTable, SymbolLookup
from errors import SemanticError
from sema import DeclarationAnalyzer
from sema_shared import (
    map_debug_line, attach_source_text, map_stmt_info,
    build_local_symtab, build_init_set,
    check_uninitialized, validate_body_exprs,
)


@dataclass
class AnalyzedProc:
    """Result of semantic analysis for a procedure."""
    ast: ProcDecl
    locals: list[Symbol]
    symtab: SymbolLookup


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
        return map_debug_line(self.debug, fname, line)

    def _attach_source_text(self, err: SemanticError, fname: str | None) -> None:
        """Attach original source text to an error when available."""
        attach_source_text(self.debug, err, fname)

    def analyze_decl(self, proc: ProcDecl) -> None:
        """Register a procedure signature and enforce declaration rules."""
        required_params: int = sum(1 for p in proc.params if p.default_value is None)
        proc_src_map = self.debug.get('proc_src') or {}
        owner = None
        owner_is_module = False
        info = proc_src_map.get(proc.name)
        if info:
            owner = info[0]
            file_is_module_map = self.debug.get('file_is_module') or {}
            owner_is_module = file_is_module_map.get(owner, False)
        exported = True
        if owner_is_module and getattr(proc, 'noexport', False):
            exported = False
        try:
            psym = ProcSymbol(proc.name, len(proc.params), required_params, owner_file=owner, exported=exported)
            self.procs.define(psym, node=proc)
        except SemanticError as e:
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
        """Validate a procedure or function call against the procedure/function table."""
        caller_file = None
        if self.current_proc is not None:
            proc_src_map = self.debug.get('proc_src') or {}
            cur_info = proc_src_map.get(self.current_proc.name)
            if cur_info:
                caller_file = cur_info[0]
        try:
            proc_sym: ProcSymbol = self.procs.lookup(call.name, caller_file=caller_file)
        except SemanticError as proc_error:
            # If not a procedure, try to find it as a function (functions can be
            # called without using the return value).
            if self.func_table is not None:
                try:
                    fs = self.func_table.lookup(call.name, node=call)
                    if len(call.args) > fs.param_count:
                        extra_arg = call.args[fs.param_count]
                        _n, _g = fs.param_count, len(call.args)
                        raise SemanticError(
                            f"Function '{call.name}' expects {_n} parameter{'s' if _n != 1 else ''}, but {_g} {'were' if _g != 1 else 'was'} provided",
                            node=extra_arg
                        )
                    if len(call.args) < fs.required_params:
                        _n, _g = fs.param_count, len(call.args)
                        raise SemanticError(
                            f"Function '{call.name}' expects {_n} parameter{'s' if _n != 1 else ''}, but {_g} {'were' if _g != 1 else 'was'} provided",
                            node=call
                        )
                    return
                except SemanticError:
                    raise
                except KeyError:
                    pass

            stmt_src_map = self.debug.get("stmt_src") or {}
            info = stmt_src_map.get(id(call))
            if info:
                if len(info) == 3:
                    fname, line, _text = info
                    col = 1
                else:
                    fname, line, col, _text = info
                mapped_line = self._map_debug_line(fname, line)
                err = SemanticError(proc_error.message, line=mapped_line, col=col)
                err.filename = fname
                self._attach_source_text(err, fname)
                raise err
            raise proc_error

        if len(call.args) < proc_sym.required_params or len(call.args) > proc_sym.param_count:
            _n, _g = proc_sym.param_count, len(call.args)
            msg: str = (
                f"Procedure '{call.name}' expects {_n} parameter{'s' if _n != 1 else ''}, "
                f"but {_g} {'were' if _g != 1 else 'was'} provided"
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
            raise SemanticError(msg, node=call)

    def analyze_proc(
        self,
        proc: ProcDecl,
        global_symtab: SymbolTable
        ) -> 'AnalyzedProc':
        """Analyze a procedure body and build a scoped symbol table."""

        # Build local symbol table and register all parameters.
        local_symtab = build_local_symtab(proc.params, proc.name, self.struct_registry, self.debug)

        # Validate parameter ordering: parameters with defaults must come last.
        has_default = False
        for param in proc.params:
            if param.default_value is not None:
                has_default = True
            elif has_default:
                from errors import CompileError
                raise CompileError(
                    f"In procedure '{proc.name}': non-default parameter '{param.name}' "
                    f"cannot follow parameters with default values",
                    param.line, param.col
                )

        # Analyze local variable declarations.
        decl_an = DeclarationAnalyzer(
            local_symtab,
            self.struct_registry,
            self.func_table,
            global_symtab=global_symtab,
            debug_info=self.debug,
        )
        for d in proc.locals:
            decl_an.analyze(d)

        # Scoped lookup: locals first, then globals.
        scoped = ScopedSymbolTable(global_symtab)
        scoped.local = local_symtab

        # Type-check expressions in the body.
        if self.func_table is not None:
            from sema_expr import ExprTypeChecker
            tc = ExprTypeChecker(scoped, self.func_table, self.struct_registry)

            def _validate_expr(expr, stmt=None, read_check_enabled=True):
                """Type-check expr, mapping any error to the enclosing statement's location."""
                try:
                    return tc.check(expr, read_check_enabled)
                except SemanticError as e:
                    if stmt is not None:
                        info = map_stmt_info(self.debug, stmt)
                        if info and getattr(e, "filename", None) is None:
                            fname, line, col = info
                            err_line = getattr(e, "line", None) or line
                            err_col = getattr(e, "col", None) or col
                            err = SemanticError(e.message, line=err_line, col=err_col)
                            err.filename = fname
                            attach_source_text(self.debug, err, fname)
                            raise err
                    raise

            def _on_call_stmt(st, cur_initialized):
                """Validate each proc call argument for uninitialized reads."""
                from ast_nodes import StructLiteral
                for a in st.args:
                    if a is None:
                        continue
                    try:
                        if not isinstance(a, StructLiteral):
                            tc.check(a)
                        check_uninitialized(a, tc.symtab, proc.name, cur_initialized)
                    except SemanticError as e:
                        info = map_stmt_info(self.debug, st)
                        if info and getattr(e, "filename", None) is None:
                            fname, line, col = info
                            err_line = getattr(e, "line", None) or line
                            err_col = getattr(e, "col", None) or col
                            err = SemanticError(e.message, line=err_line, col=err_col)
                            err.filename = fname
                            attach_source_text(self.debug, err, fname)
                            raise err
                        raise

            def _on_return_stmt(st, cur_initialized):
                """Type-check the return expression (procs have no declared return type)."""
                if st.expr is not None:
                    try:
                        tc.check(st.expr)
                        check_uninitialized(st.expr, tc.symtab, proc.name, cur_initialized)
                    except SemanticError as e:
                        info = map_stmt_info(self.debug, st)
                        if info and getattr(e, "filename", None) is None:
                            fname, line, col = info
                            err_line = getattr(e, "line", None) or line
                            err_col = getattr(e, "col", None) or col
                            err = SemanticError(e.message, line=err_line, col=err_col)
                            err.filename = fname
                            attach_source_text(self.debug, err, fname)
                            raise err
                        raise

            init_set = build_init_set(proc.params, scoped.local, proc.name)
            validate_body_exprs(
                proc.body, init_set, _validate_expr, tc.symtab, self.debug, proc.name,
                on_call_stmt=_on_call_stmt,
                on_return_stmt=_on_return_stmt,
            )

        # Validate procedure calls inside the body (must refer to defined procs).
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
                # AssignStmt, ReturnStmt, Break/Continue need no proc-call validation.

        walk(proc.body)
        self.current_proc = None

        return AnalyzedProc(
            ast=proc,
            locals=list(local_symtab),
            symtab=scoped
        )
