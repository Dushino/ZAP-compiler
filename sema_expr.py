from symbols import SemType, SemType, SymbolLookup, FuncTable
from sema import SemanticError
from sema_types import ExprKind, ExprType
from ast_nodes import IntLiteral, Identifier, DerefExpr, CallExpr
from ast_nodes import BinaryExpr, UnaryExpr, BinOp, SubscriptExpr


def promote(a: SemType, b: SemType) -> SemType:
    if a.base == "WORD" or b.base == "WORD":
        return SemType("WORD", False)
    return SemType("BYTE", False)


class ExprTypeChecker:
    def __init__(self, symtab: SymbolLookup, func_table: FuncTable):
        self.symtab = symtab
        self.func_table = func_table

    def check(self, expr) -> ExprType:
        if isinstance(expr, IntLiteral):
            # Small literals (0-255) are BYTE, larger are WORD
            if 0 <= expr.value <= 255:
                return ExprType(SemType("BYTE", False), ExprKind.VALUE)
            else:
                return ExprType(SemType("WORD", False), ExprKind.VALUE)

        if isinstance(expr, Identifier):
            sym = self.symtab.lookup(expr.name)
            if sym.is_array:
                return ExprType(
                    SemType(sym.type.base, False),
                    ExprKind.ADDR
                )

            if sym.type.is_pointer:
                return ExprType(
                    sym.type,        # ← PONECHAT is_pointer = True
                    ExprKind.ADDR
                )

            return ExprType(sym.type, ExprKind.VALUE)

        if isinstance(expr, DerefExpr):
            base = self.check(expr.pointer)
            if base.kind != ExprKind.ADDR or not base.sem_type.is_pointer:
                raise SemanticError("Cannot dereference non-pointer")
            return ExprType(
                SemType(base.sem_type.base, False),
                ExprKind.LVALUE
            )

        if isinstance(expr, SubscriptExpr):
            arr_t = self.check(expr.array)
            if arr_t.kind != ExprKind.ADDR:
                raise SemanticError("Subscript requires array address")
            # array element is LVALUE of base type
            return ExprType(
                SemType(arr_t.sem_type.base, False),
                ExprKind.LVALUE
            )

        if isinstance(expr, BinaryExpr):
            lt = self.check(expr.left)
            rt = self.check(expr.right)
            op = expr.op

            # žádné operace s LVALUE
            if lt.kind == ExprKind.LVALUE or rt.kind == ExprKind.LVALUE:
                raise SemanticError("Invalid use of lvalue in expression")

            # aritmetika
            if op in {
                BinOp.ADD, BinOp.SUB, BinOp.MUL, BinOp.DIV, BinOp.MOD
            }:
                if lt.kind == ExprKind.ADDR or rt.kind == ExprKind.ADDR:
                    if op in (BinOp.ADD, BinOp.SUB):
                        if lt.kind == ExprKind.ADDR and rt.kind == ExprKind.VALUE:
                            return ExprType(lt.sem_type, ExprKind.ADDR)
                        if lt.kind == ExprKind.VALUE and rt.kind == ExprKind.ADDR:
                            return ExprType(rt.sem_type, ExprKind.ADDR)
                    raise SemanticError("Invalid pointer arithmetic")

                return ExprType(promote(lt.sem_type, rt.sem_type), ExprKind.VALUE)

            # relační
            if op in {
                BinOp.EQ, BinOp.NE,
                BinOp.LT, BinOp.GT, BinOp.LE, BinOp.GE
            }:
                if lt.kind != ExprKind.VALUE or rt.kind != ExprKind.VALUE:
                    raise SemanticError("Comparison requires values")
                return ExprType(SemType("BYTE", False), ExprKind.VALUE)

            # logické
            if op in {BinOp.LAND, BinOp.LOR}:
                if lt.kind != ExprKind.VALUE or rt.kind != ExprKind.VALUE:
                    raise SemanticError("Logical operator requires values")
                return ExprType(SemType("BYTE", False), ExprKind.VALUE)

            # bitové
            if op in {BinOp.BAND, BinOp.BOR}:
                if lt.kind != ExprKind.VALUE or rt.kind != ExprKind.VALUE:
                    raise SemanticError("Bitwise operator requires values")
                return ExprType(promote(lt.sem_type, rt.sem_type), ExprKind.VALUE)

        # unární OP
        if isinstance(expr, UnaryExpr):
            t = self.check(expr.expr)
            if t.kind != ExprKind.VALUE:
                raise SemanticError("Logical NOT requires value")
            return ExprType(SemType("BYTE", False), ExprKind.VALUE)

        # funkce
        if isinstance(expr, CallExpr):
            fs = self.func_table.lookup(expr.name)
            if len(expr.args) != fs.param_count:
                raise SemanticError(
                    f"Function '{expr.name}' expects {fs.param_count} parameters, "
                    f"but {len(expr.args)} were provided"
                )
            return ExprType(fs.ret_type, ExprKind.VALUE)

        # chyba
        raise SemanticError(
            f"Unsupported expression type: {type(expr).__name__}"
        )

