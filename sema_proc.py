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
    def __init__(self, procs: ProcTable):
        self.procs = procs

    def analyze_decl(self, proc: ProcDecl):
        self.procs.define(ProcSymbol(proc.name))

    def analyze_call(self, call: CallStmt):
        self.procs.lookup(call.name)  # musí existovat

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
            sem_type = SemType(param.type.base, param.type.is_pointer)
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
                proc_name=proc.name
            )
            local_symtab.define(sym)

        decl_an = DeclarationAnalyzer(local_symtab)
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




