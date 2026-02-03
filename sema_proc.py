from dataclasses import dataclass
from ast_nodes import ProcDecl, CallStmt
from symbols import Symbol, SymbolTable, ProcTable, ProcSymbol, ScopedSymbolTable, SymbolLookup
from errors import SemanticError
from sema import DeclarationAnalyzer


@dataclass
class AnalyzedProc:
    ast: ProcDecl
    locals: list[Symbol]
    symtab: SymbolLookup   # ← změna tady


class ProcAnalyzer:
    def __init__(self, procs: ProcTable, debug_info: dict | None = None, struct_registry=None, func_table=None):
        self.procs = procs
        self.debug = debug_info or {}
        self.struct_registry = struct_registry
        self.func_table = func_table

    def analyze_decl(self, proc: ProcDecl):
        # Count required parameters (those without defaults)
        required_params = sum(1 for p in proc.params if p.default_value is None)
        # Determine owner file and exported flag (set by module system via debug maps)
        proc_src_map = self.debug.get('proc_src', {})
        owner = None
        owner_is_module = False
        info = proc_src_map.get(proc.name)
        if info:
            # info may be (filename, line, col, text) or (filename, line, text)
            owner = info[0]
            owner_is_module = self.debug.get('file_is_module', {}).get(owner, False)
        exported = True
        if owner_is_module and getattr(proc, 'noexport', False):
            exported = False
        try:
            psym = ProcSymbol(proc.name, len(proc.params), required_params, owner_file=owner, exported=exported)
            self.procs.define(psym)
        except SemanticError as e:
            # Attach location of PROC header
            info = self.debug.get("proc_src", {}).get(proc.name)
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

    def analyze_call(self, call: CallStmt):
        # Determine caller file if available to support module visibility checks
        caller_file = None
        if getattr(self, 'current_proc', None):
            cur_info = self.debug.get('proc_src', {}).get(self.current_proc.name)
            if cur_info:
                caller_file = cur_info[0]
        try:
            proc_sym = self.procs.lookup(call.name, caller_file=caller_file)
        except SemanticError as e:
            # Re-raise with source location attached
            info = self.debug.get("stmt_src", {}).get(id(call))
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
        # Allow arguments from required_params to param_count
        if len(call.args) < proc_sym.required_params or len(call.args) > proc_sym.param_count:
            msg = (
                f"Procedure '{call.name}' expects {proc_sym.param_count} parameters, "
                f"but {len(call.args)} were provided"
            )
            info = self.debug.get("stmt_src", {}).get(id(call))
            if info:
                if len(info) == 3:
                    fname, line, _text = info
                    col = 1
                else:
                    fname, line, col, _text = info
                err = SemanticError(msg, line=line, col=col)
                err.filename = fname
                raise err
            raise SemanticError(msg)

    def analyze_proc(
        self,
        proc: ProcDecl,
        global_symtab: SymbolTable
        ) -> AnalyzedProc:

        local_symtab = SymbolTable()
        local_symtab._proc_name = proc.name

        # add parameters to local symbol table
        for param in proc.params:
            from symbols import SemType, Symbol
            # Check if parameter type is a struct
            base_name = param.type.base.upper()
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
            local_symtab.define(sym)

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

        decl_an = DeclarationAnalyzer(local_symtab, self.struct_registry, self.func_table, global_symtab=global_symtab)
        for d in proc.locals:
            decl_an.analyze(d)

        # scoped lookup: nejdřív lokály, pak globály
        scoped = ScopedSymbolTable(global_symtab)
        scoped.local = local_symtab

        # Type-check expressions in statements to validate variable references
        if self.func_table is not None:
            from sema_expr import ExprTypeChecker
            tc = ExprTypeChecker(scoped, self.func_table, self.struct_registry)

            def validate_stmt_exprs(statements: list):
                from ast_nodes import AssignStmt, ReturnStmt, IfStmt, WhileStmt, ForStmt
                for st in statements:
                    if isinstance(st, AssignStmt):
                        tc.check(st.lhs)
                        tc.check(st.rhs)
                    elif isinstance(st, ReturnStmt):
                        if st.expr is not None:
                            tc.check(st.expr)
                    elif isinstance(st, IfStmt):
                        tc.check(st.cond)
                        validate_stmt_exprs(st.then_body)
                        if st.else_body:
                            validate_stmt_exprs(st.else_body)
                    elif isinstance(st, WhileStmt):
                        tc.check(st.cond)
                        validate_stmt_exprs(st.body)
                    elif isinstance(st, ForStmt):
                        tc.check(st.start)
                        tc.check(st.end)
                        if st.step is not None:
                            tc.check(st.step)
                        validate_stmt_exprs(st.body)

            validate_stmt_exprs(proc.body)

        # validate procedure calls inside the body (must refer to defined procs)
        # set current_proc so analyze_call can check visibility
        self.current_proc = proc
        def walk(statements: list):
            from ast_nodes import CallStmt, IfStmt, WhileStmt, ForStmt
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
                # other statements (AssignStmt, ReturnStmt, Break/Continue) need no proc validation

        walk(proc.body)
        # clear current_proc after analysis
        self.current_proc = None

        return AnalyzedProc(
            ast=proc,
            locals=list(local_symtab),   # ← TADY vzniká local_symbols
            symtab=scoped
        )




