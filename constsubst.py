"""Constant substitution pass.

Replaces references to named constants (const identifiers, enum members)
with their literal values so that later constant folding can evaluate
the full expression at compile time.
"""

from ast_nodes import (
    Identifier,
    Expr,
    IntLiteral,
    UnaryExpr,
    BinaryExpr,
    DerefExpr,
)

from symbols import Symbol, SymbolTable
from errors import SemanticError

def subst_const(expr: Expr, symtab: SymbolTable) -> Expr:
    """Replace const identifiers in an expression with literal values."""
    # IDENTIFIER
    if isinstance(expr, Identifier):
        try:
            sym: Symbol = symtab.lookup(expr.name, node=expr)
        except SemanticError:
            return expr  # Unknown identifier — not a const; leave for codegen
        if sym.is_const:
            # Only substitute scalar consts; const arrays/structs keep their address semantics
            if sym.is_array or sym.type.is_struct:
                return expr
            assert sym.const_value is not None
            return IntLiteral(sym.const_value)
        return expr

    # ENUM MEMBER (FieldAccess with Identifier object)
    from ast_nodes import FieldAccess
    if isinstance(expr, FieldAccess) and isinstance(expr.object, Identifier):
        enum_name = expr.object.name.upper()
        # Lookup enum definitions starting from current scope
        enums = getattr(symtab, '_enums', None)
        if enums is None:
            parent = getattr(symtab, 'parent', None)
            if parent is not None:
                enums = getattr(parent, '_enums', None)
        if enums and enum_name in enums:
            members = enums[enum_name]['members']
            mname = expr.field.upper()
            if mname in members:
                return IntLiteral(members[mname])

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

    # DEREF — constants never have an address
    if isinstance(expr, DerefExpr):
        return DerefExpr(
            subst_const(expr.pointer, symtab)
        )

    # literal or other node — return as-is
    return expr

