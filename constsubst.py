from ast_nodes import (
    Identifier,
    Expr,
    IntLiteral,
    UnaryExpr,
    BinaryExpr,
    DerefExpr,
)

from symbols import Symbol, SymbolTable

def subst_const(expr: Expr, symtab: SymbolTable) -> Expr:
    """Replace const identifiers in an expression with literal values."""
    # IDENTIFIER
    if isinstance(expr, Identifier):
        sym: Symbol = symtab.lookup(expr.name)
        if sym.is_const:
            # Only substitute scalar consts; const arrays/structs keep their address semantics
            if sym.is_array or sym.type.is_struct:
                return expr
            assert sym.const_value is not None
            return IntLiteral(sym.const_value)
        return expr

    # UNARY
    if isinstance(expr, UnaryExpr):
        return UnaryExpr(
            expr.op,
            subst_const(expr.expr, symtab)
        )

    # BINARY
    if isinstance(expr, BinaryExpr):
        return BinaryExpr(
            subst_const(expr.left, symtab),
            expr.op,
            subst_const(expr.right, symtab)
        )

    # DEREF – konstanta nikdy nemá adresu
    if isinstance(expr, DerefExpr):
        return DerefExpr(
            subst_const(expr.pointer, symtab)
        )

    # LITERAL nebo něco jiného
    return expr

