from ast_nodes import (
    Expr,
    IntLiteral,
    UnaryExpr,
    BinaryExpr,
    UnOp,
    BinOp,
)
from errors import SemanticError


def fold_expr(expr: Expr, node: Expr | None = None) -> Expr:
    """Fold constant subexpressions and apply simple algebraic simplifications."""
    if isinstance(expr, IntLiteral):
        return expr

    if isinstance(expr, UnaryExpr):
        inner: Expr = fold_expr(expr.expr)
        if isinstance(inner, IntLiteral):
            return _eval_unary(expr.op, inner.value, node=expr)
        return UnaryExpr(expr.op, inner)

    if isinstance(expr, BinaryExpr):
        l: Expr = fold_expr(expr.left)
        r: Expr = fold_expr(expr.right)
        
        # Constant folding: const op const
        if isinstance(l, IntLiteral) and isinstance(r, IntLiteral):
            return _eval_binary(expr.op, l.value, r.value, node=expr)
        
        # Neutral element removal and algebraic simplifications
        op: BinOp = expr.op
        
        # Addition: x + 0 = x, 0 + x = x
        if op == BinOp.ADD:
            if isinstance(l, IntLiteral) and l.value == 0:
                return r
            if isinstance(r, IntLiteral) and r.value == 0:
                return l
        
        # Multiplication: x * 1 = x, 1 * x = x
        if op == BinOp.MUL:
            if isinstance(l, IntLiteral) and l.value == 1:
                return r
            if isinstance(r, IntLiteral) and r.value == 1:
                return l
            # Annihilation: x * 0 = 0, 0 * x = 0
            if isinstance(l, IntLiteral) and l.value == 0:
                return IntLiteral(0)
            if isinstance(r, IntLiteral) and r.value == 0:
                return IntLiteral(0)
        
        # Subtraction: x - 0 = x
        if op == BinOp.SUB:
            if isinstance(r, IntLiteral) and r.value == 0:
                return l
        
        # Division: x / 1 = x
        if op == BinOp.DIV:
            if isinstance(r, IntLiteral) and r.value == 1:
                return l
        
        return BinaryExpr(l, expr.op, r)

    return expr


def _eval_unary(op: UnOp, v: int, node: Expr | None = None) -> IntLiteral:
    """Evaluate a unary operator on a constant value."""
    if op == UnOp.NOT:
        return IntLiteral(0 if v else 1)
    if op == UnOp.BNOT:
        # Bitwise NOT - invert all 16 bits
        return IntLiteral((~v) & 0xFFFF)

    raise SemanticError(f"Unsupported unary op in constant fold: {op}", node=node)


def _eval_binary(op: BinOp, a: int, b: int, node: Expr | None = None) -> IntLiteral:
    """Evaluate a binary operator on two constant values."""
    if op == BinOp.ADD:
        return IntLiteral(a + b)
    if op == BinOp.SUB:
        return IntLiteral(a - b)
    if op == BinOp.MUL:
        return IntLiteral(a * b)
    if op == BinOp.DIV:
        if b == 0:
            raise SemanticError("Division by zero in constant expression", node=node)
        return IntLiteral(a // b)
    if op == BinOp.MOD:
        if b == 0:
            raise SemanticError("Modulo by zero in constant expression", node=node)
        return IntLiteral(a % b)

    # relační
    if op == BinOp.EQ:
        return IntLiteral(1 if a == b else 0)
    if op == BinOp.NE:
        return IntLiteral(1 if a != b else 0)
    if op == BinOp.LT:
        return IntLiteral(1 if a < b else 0)
    if op == BinOp.LE:
        return IntLiteral(1 if a <= b else 0)
    if op == BinOp.GT:
        return IntLiteral(1 if a > b else 0)
    if op == BinOp.GE:
        return IntLiteral(1 if a >= b else 0)

    # logické
    if op == BinOp.LAND:
        return IntLiteral(1 if (a and b) else 0)
    if op == BinOp.LOR:
        return IntLiteral(1 if (a or b) else 0)

    # bitové
    if op == BinOp.BAND:
        return IntLiteral(a & b)
    if op == BinOp.BOR:
        return IntLiteral(a | b)
    if op == BinOp.BXOR:
        return IntLiteral(a ^ b)
    if op == BinOp.LSHIFT:
        return IntLiteral(a << b)
    if op == BinOp.RSHIFT:
        return IntLiteral(a >> b)

    raise SemanticError(f"Unsupported binary op in constant fold: {op}", node=node)


