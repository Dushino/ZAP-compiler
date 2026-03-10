"""ast_walker.py — Generic AST traversal for the ZAP compiler.

Provides three recursive walker functions that visit every node in an
expression, statement, or initializer tree.  Callers supply callbacks for
the semantically-interesting nodes; this module handles all structural
recursion.

    walk_expr(expr, *, on_identifier=None, on_call_expr=None)
    walk_stmt(stmt, *, on_call_stmt=None, on_identifier=None, on_call_expr=None)
    walk_initializer(init, *, on_identifier=None, on_call_expr=None)

Callback signatures
-------------------
on_identifier(node: Identifier) -> None
    Called for every Identifier leaf.  No further recursion from this node.

on_call_expr(node: CallExpr) -> None
    Called for every CallExpr before its argument list is walked.

on_call_stmt(node: CallStmt) -> None
    Called for every CallStmt before its argument list is walked.

All callbacks default to None (no-op).  The walker always recurses fully
regardless of which callbacks are provided.

Adding new AST node types
-------------------------
When a new expression node type is added to the language, add a branch to
walk_expr().  When a new statement node type is added, add a branch to
walk_stmt().  No other file needs to change to pick up the new traversal in
all consumers (prune_unused, prune_unused_locals, liveness analysis, etc.).
"""

from typing import Callable, Optional


def walk_expr(
    expr,
    *,
    on_identifier: Optional[Callable] = None,
    on_call_expr: Optional[Callable] = None,
) -> None:
    """Recursively visit every node in an expression tree.

    Handled node types (in dispatch order):
        IntLiteral, StringLiteral  — base cases, no recursion
        Identifier                 — calls on_identifier if provided
        FieldAccess                — recurses into .object
        CallExpr                   — calls on_call_expr if provided, then recurses into .args
        BinaryExpr                 — recurses into .left and .right
        UnaryExpr                  — recurses into .expr
        DerefExpr                  — recurses into .pointer
        SubscriptExpr              — recurses into .array and .index
    """
    from ast_nodes import (
        IntLiteral, StringLiteral, Identifier, BinaryExpr, UnaryExpr,
        DerefExpr, SubscriptExpr, CallExpr, FieldAccess,
    )

    if expr is None:
        return

    if isinstance(expr, (IntLiteral, StringLiteral)):
        return

    if isinstance(expr, Identifier):
        if on_identifier is not None:
            on_identifier(expr)
        return

    if isinstance(expr, FieldAccess):
        # Recurse into the object (e.g. the struct variable in global.field).
        walk_expr(expr.object, on_identifier=on_identifier, on_call_expr=on_call_expr)
        return

    if isinstance(expr, CallExpr):
        if on_call_expr is not None:
            on_call_expr(expr)
        for a in expr.args:
            walk_expr(a, on_identifier=on_identifier, on_call_expr=on_call_expr)
        return

    if isinstance(expr, BinaryExpr):
        walk_expr(expr.left, on_identifier=on_identifier, on_call_expr=on_call_expr)
        walk_expr(expr.right, on_identifier=on_identifier, on_call_expr=on_call_expr)
        return

    if isinstance(expr, UnaryExpr):
        walk_expr(expr.expr, on_identifier=on_identifier, on_call_expr=on_call_expr)
        return

    if isinstance(expr, DerefExpr):
        walk_expr(expr.pointer, on_identifier=on_identifier, on_call_expr=on_call_expr)
        return

    if isinstance(expr, SubscriptExpr):
        walk_expr(expr.array, on_identifier=on_identifier, on_call_expr=on_call_expr)
        walk_expr(expr.index, on_identifier=on_identifier, on_call_expr=on_call_expr)
        return


def walk_stmt(
    stmt,
    *,
    on_call_stmt: Optional[Callable] = None,
    on_identifier: Optional[Callable] = None,
    on_call_expr: Optional[Callable] = None,
) -> None:
    """Recursively visit every node in a statement tree.

    on_call_stmt and on_call_expr/on_identifier are forwarded to nested
    walk_stmt and walk_expr calls respectively throughout the full tree.

    Handled statement types:
        BreakStmt, ContinueStmt    — no sub-expressions, no-op
        CallStmt                   — calls on_call_stmt if provided, recurses into .args
        AssignStmt                 — recurses into .lhs and .rhs
        ReturnStmt                 — recurses into .expr
        IfStmt                     — recurses into .cond, .then_body, .else_body
        WhileStmt                  — recurses into .cond, .body
        RepeatUntilStmt            — recurses into .body, .cond
        ForStmt                    — recurses into .var, .start, .end, .step, .body
        SwitchStmt                 — recurses into .expr, case .labels, case .body
    """
    from ast_nodes import (
        CallStmt, AssignStmt, ReturnStmt, IfStmt, WhileStmt, RepeatUntilStmt,
        ForStmt, SwitchStmt, BreakStmt, ContinueStmt,
    )

    # Keyword arguments forwarded to every recursive call.
    kw_expr = dict(on_identifier=on_identifier, on_call_expr=on_call_expr)
    kw_stmt = dict(on_call_stmt=on_call_stmt, **kw_expr)

    if isinstance(stmt, (BreakStmt, ContinueStmt)):
        return

    if isinstance(stmt, CallStmt):
        # Parser emits CallStmt for both proc calls and func calls used as
        # statements (return value discarded).
        if on_call_stmt is not None:
            on_call_stmt(stmt)
        for a in stmt.args:
            walk_expr(a, **kw_expr)
        return

    if isinstance(stmt, AssignStmt):
        walk_expr(stmt.lhs, **kw_expr)
        walk_expr(stmt.rhs, **kw_expr)
        return

    if isinstance(stmt, ReturnStmt):
        walk_expr(stmt.expr, **kw_expr)
        return

    if isinstance(stmt, IfStmt):
        walk_expr(stmt.cond, **kw_expr)
        for s in stmt.then_body:
            walk_stmt(s, **kw_stmt)
        if stmt.else_body:
            for s in stmt.else_body:
                walk_stmt(s, **kw_stmt)
        return

    if isinstance(stmt, WhileStmt):
        walk_expr(stmt.cond, **kw_expr)
        for s in stmt.body:
            walk_stmt(s, **kw_stmt)
        return

    if isinstance(stmt, RepeatUntilStmt):
        for s in stmt.body:
            walk_stmt(s, **kw_stmt)
        walk_expr(stmt.cond, **kw_expr)
        return

    if isinstance(stmt, ForStmt):
        walk_expr(stmt.var, **kw_expr)
        walk_expr(stmt.start, **kw_expr)
        walk_expr(stmt.end, **kw_expr)
        if stmt.step is not None:
            walk_expr(stmt.step, **kw_expr)
        for s in stmt.body:
            walk_stmt(s, **kw_stmt)
        return

    if isinstance(stmt, SwitchStmt):
        walk_expr(stmt.expr, **kw_expr)
        for case in stmt.cases:
            for label in case.labels:
                walk_expr(label, **kw_expr)
            for s in case.body:
                walk_stmt(s, **kw_stmt)
        return


def walk_initializer(
    init,
    *,
    on_identifier: Optional[Callable] = None,
    on_call_expr: Optional[Callable] = None,
) -> None:
    """Recursively visit every expression node reachable from an initializer.

    ListInit.values may contain ExprInit, ListInit, StringInit wrappers, or
    plain expression nodes — all cases are handled.

    Handled initializer types:
        ExprInit     — recurses into .expr
        ListInit     — recurses into each value (unwrapping InitValue wrappers)
        StringInit   — no sub-expressions, no-op
    """
    from ast_nodes import ExprInit, ListInit, StringInit

    if init is None:
        return

    kw = dict(on_identifier=on_identifier, on_call_expr=on_call_expr)

    if isinstance(init, ExprInit):
        walk_expr(init.expr, **kw)
        return

    if isinstance(init, ListInit):
        for v in init.values:
            if isinstance(v, ExprInit):
                walk_expr(v.expr, **kw)
            elif isinstance(v, ListInit):
                walk_initializer(v, **kw)
            elif isinstance(v, StringInit):
                pass  # no sub-expressions
            else:
                # Plain expression value (array literal shorthand).
                walk_expr(v, **kw)
        return

    # StringInit has no sub-expressions to visit.
