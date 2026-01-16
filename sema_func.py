from dataclasses import dataclass
from ast_nodes import FuncDecl, ReturnStmt
from symbols import Symbol, SymbolTable, ScopedSymbolTable, SymbolLookup, SemType, FuncTable, FuncSymbol
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
    def __init__(self, func_table: FuncTable, expr_tc: ExprTypeChecker):
        self.func_table = func_table
        self.expr_tc = expr_tc

    def analyze_decl(self, func: FuncDecl):
        ret_sem = SemType(func.ret_type.base, func.ret_type.is_pointer)
        self.func_table.define(
            FuncSymbol(func.name, ret_sem, len(func.params))
        )

    def analyze_func(self, func: FuncDecl, global_symtab: SymbolTable) -> AnalyzedFunc:
        # lokály (stejně jako u PROC)
        local_symtab = SymbolTable()
        local_symtab._proc_name = func.name
        
        # add parameters to local symbol table
        for param in func.params:
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
                proc_name=func.name
            )
            local_symtab.define(sym)
        
        decl_an = DeclarationAnalyzer(local_symtab)
        for d in func.locals:
            decl_an.analyze(d)

        scoped = ScopedSymbolTable(global_symtab)
        scoped.local = local_symtab

        # návratový typ
        ret_sem = SemType(func.ret_type.base, func.ret_type.is_pointer)

        # update expr_tc to use scoped symbol table
        prev_symtab = self.expr_tc.symtab
        self.expr_tc.symtab = scoped

        has_return = False
        for stmt in func.body:
            if isinstance(stmt, ReturnStmt):
                has_return = True
                et = self.expr_tc.check(stmt.expr)
                if et.sem_type.base != ret_sem.base:
                    raise SemanticError("RETURN type mismatch")

        # restore previous symbol table
        self.expr_tc.symtab = prev_symtab

        if not has_return:
            raise SemanticError("FUNC must have RETURN")

        return AnalyzedFunc(
            ast=func,
            locals=list(local_symtab),
            symtab=scoped,
            ret_type=ret_sem
        )
