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
    def __init__(self, procs: ProcTable, debug_info: dict | None = None, struct_registry=None):
        self.procs = procs
        self.debug = debug_info or {}
        self.struct_registry = struct_registry

    def analyze_decl(self, proc: ProcDecl):
        try:
            self.procs.define(ProcSymbol(proc.name, len(proc.params)))
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
        proc_sym = self.procs.lookup(call.name)  # musí existovat
        if len(call.args) != proc_sym.param_count:
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

        decl_an = DeclarationAnalyzer(local_symtab, self.struct_registry)
        for d in proc.locals:
            decl_an.analyze(d)

        # scoped lookup: nejdřív lokály, pak globály
        scoped = ScopedSymbolTable(global_symtab)
        scoped.local = local_symtab

        # validate procedure calls inside the body (must refer to defined procs)
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

        return AnalyzedProc(
            ast=proc,
            locals=list(local_symtab),   # ← TADY vzniká local_symbols
            symtab=scoped
        )




