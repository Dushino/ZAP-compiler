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
    def __init__(self, func_table: FuncTable, expr_tc: ExprTypeChecker, debug_info: dict | None = None, struct_registry=None):
        self.func_table = func_table
        self.expr_tc = expr_tc
        self.debug = debug_info or {}
        self.struct_registry = struct_registry

    def analyze_decl(self, func: FuncDecl):
        ret_sem = SemType(func.ret_type.base, func.ret_type.is_pointer)
        try:
            self.func_table.define(
                FuncSymbol(func.name, ret_sem, len(func.params))
            )
        except SemanticError as e:
            info = self.debug.get("proc_src", {}).get(func.name)
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
        local_symtab._proc_name = func.name
        
        # add parameters to local symbol table
        for param in func.params:
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
                proc_name=func.name,
                array_dims=None
            )
            local_symtab.define(sym)
        
        decl_an = DeclarationAnalyzer(local_symtab, self.struct_registry)
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
                # Type-check return expression; attach location if error occurs
                try:
                    et = self.expr_tc.check(stmt.expr)
                except SemanticError as e:
                    info = self.debug.get("stmt_src", {}).get(id(stmt))
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
                if et.sem_type.base != ret_sem.base:
                    # Allow implicit narrowing from WORD to BYTE (use lower byte)
                    # Allow implicit widening from BYTE to WORD (zero-extend)
                    if (ret_sem.base == "BYTE" and et.sem_type.base == "WORD") or \
                       (ret_sem.base == "WORD" and et.sem_type.base == "BYTE"):
                        # This is allowed - implicit conversion
                        pass
                    else:
                        # Type mismatch - report error with context
                        info = self.debug.get("stmt_src", {}).get(id(stmt))
                        if info:
                            if len(info) == 3:
                                fname, line, _text = info
                                col = 1
                            else:
                                fname, line, col, _text = info
                            msg = f"RETURN type mismatch: expected {ret_sem.base}, got {et.sem_type.base}"
                            err = SemanticError(msg, line=line, col=col)
                            err.filename = fname
                            raise err
                        raise SemanticError(f"RETURN type mismatch: expected {ret_sem.base}, got {et.sem_type.base}")

        # restore previous symbol table
        self.expr_tc.symtab = prev_symtab

        if not has_return:
            info = self.debug.get("proc_src", {}).get(func.name)
            if info:
                if len(info) == 3:
                    fname, line, _text = info
                    col = 1
                else:
                    fname, line, col, _text = info
                err = SemanticError("FUNC must have RETURN", line=line, col=col)
                err.filename = fname
                raise err
            raise SemanticError("FUNC must have RETURN")

        return AnalyzedFunc(
            ast=func,
            locals=list(local_symtab),
            symtab=scoped,
            ret_type=ret_sem
        )
