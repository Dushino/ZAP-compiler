# 

from symbols import SemType, Symbol, SymbolTable
from errors import *
from ast_nodes import IntLiteral, Identifier, DerefExpr, BinaryExpr, BinOp
from ast_nodes import ListInit, StringInit, ExprInit
from ast_nodes import Declaration, Declarator


def eval_const_expr(expr):
    if isinstance(expr, IntLiteral):
        return expr.value
    if isinstance(expr, BinaryExpr):
        left = eval_const_expr(expr.left)
        right = eval_const_expr(expr.right)
        if expr.op == BinOp.ADD:
            return left + right
        elif expr.op == BinOp.SUB:
            return left - right
        elif expr.op == BinOp.MUL:
            return left * right
        elif expr.op == BinOp.DIV:
            return left // right
        elif expr.op == BinOp.MOD:
            return left % right
        else:
            raise SemanticError("Unsupported operation in constant expression")
    raise SemanticError("Constant expression required")


class DeclarationAnalyzer:
    def __init__(self, symtab: SymbolTable):
        self.symtab = symtab

    def analyze(self, decl: Declaration):
        sem_type = SemType(
            base=decl.type.base,
            is_pointer=decl.type.is_pointer
        )

        for d in decl.declarators:
            self._analyze_declarator(decl, d, sem_type)

    def _analyze_declarator(
        self,
        decl: Declaration,
        d: Declarator,
        sem_type: SemType
        ):

        # pole
        is_array = d.array_size is not None
        array_len = None
        address_val = None

        if d.address is not None:
            address_val = eval_const_expr(d.address)

        if is_array:
            try:
                sz_val = eval_const_expr(d.array_size)
            except SemanticError as e:
                raise SemanticError(e.message, line=d.line, col=d.col)
            if sz_val == -1:
                # [] → infer size
                array_len = None
            elif sz_val <= 0:
                raise SemanticError("Array size must be positive", line=d.line, col=d.col)
            else:
                array_len = sz_val

        # const pravidla
        if decl.is_const:
            if d.address is not None:
                raise SemanticError("CONST cannot have address", line=d.line, col=d.col)
            if not isinstance(d.initializer, ExprInit):
                raise SemanticError("CONST must have expression initializer", line=d.line, col=d.col)
            try:
                val = eval_const_expr(d.initializer.expr)
            except SemanticError as e:
                raise SemanticError(e.message, line=d.line, col=d.col)

            sym = Symbol(
                name=d.name,
                type=sem_type,
                is_const=True,
                is_array=False,
                array_len=None,
                init=None,              # CONST nemá runtime init
                const_value=val,
                address=None,
                is_volatile=False,
                proc_name=getattr(self.symtab, '_proc_name', '')
            )
            try:
                self.symtab.define(sym)
            except SemanticError as e:
                # Re-raise with better context for constants
                raise SemanticError(f"Constant '{d.name}': {e.message}", line=d.line, col=d.col)
            return


        # inicializace pole
        if is_array:
            if isinstance(d.initializer, ListInit):
                if array_len is None:
                    array_len = len(d.initializer.values)
                elif array_len != len(d.initializer.values):
                    raise SemanticError("Array initializer size mismatch", line=d.line, col=d.col)

            elif isinstance(d.initializer, StringInit):
                if sem_type.base.lower() != "byte":
                    raise SemanticError("String only allowed for byte array", line=d.line, col=d.col)
                if array_len is None:
                    array_len = len(d.initializer.value) + 1

            elif d.initializer is not None:
                raise SemanticError("Invalid array initializer", line=d.line, col=d.col)

            if array_len is None:
                raise SemanticError("Array size required", line=d.line, col=d.col)

        # skalární proměnná
        else:
            if isinstance(d.initializer, ListInit):
                raise SemanticError("List initializer for scalar", line=d.line, col=d.col)

            if isinstance(d.initializer, StringInit):
                raise SemanticError("String initializer for scalar", line=d.line, col=d.col)

        sym = Symbol(
            name=d.name,
            type=sem_type,
            is_const=False,
            const_value=None,
            is_array=is_array,
            array_len=array_len,
            init=d.initializer,
            address=address_val,
            is_volatile=address_val is not None,
            proc_name=getattr(self.symtab, '_proc_name', '')
        )

        try:
            self.symtab.define(sym)
        except SemanticError as e:
            # Re-raise with better context
            raise SemanticError(f"{e.message}", line=d.line, col=d.col)

