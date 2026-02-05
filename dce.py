from ast_nodes import (
    Expr, Expr, IfStmt, WhileStmt, BreakStmt, ContinueStmt,
    ReturnStmt
)
from ast_nodes import IntLiteral


# Global dict to preserve source line mappings during DCE
_stmt_src_copy: dict = {}


def init_stmt_src_tracking(original_stmt_src: dict) -> None:
    """Initialize the stmt_src copy dict with original mappings."""
    global _stmt_src_copy
    _stmt_src_copy = original_stmt_src.copy()


def get_updated_stmt_src() -> dict:
    """Get the updated stmt_src dict after DCE."""
    return _stmt_src_copy.copy()


def dce_block(stmts: list) -> list:
    out = []
    for stmt in stmts:
        out_stmt = dce_stmt(stmt)
        if out_stmt is None:
            continue

        if isinstance(out_stmt, list):
            out.extend(out_stmt)
        else:
            out.append(out_stmt)

        if isinstance(stmt, (BreakStmt, ContinueStmt, ReturnStmt)):
            break   # vše za tím je mrtvé

    return out

def dce_stmt(stmt):
    # IF
    if isinstance(stmt, IfStmt):
        cond: Expr = stmt.cond

        if isinstance(cond, IntLiteral):
            if cond.value == 0:
                return None
            else:
                return dce_block(stmt.then_body)

        then_body = dce_block(stmt.then_body)
        else_body = dce_block(stmt.else_body) if stmt.else_body else None

        new_stmt = IfStmt(cond, then_body, else_body)
        # Preserve source mapping
        if id(stmt) in _stmt_src_copy:
            _stmt_src_copy[id(new_stmt)] = _stmt_src_copy[id(stmt)]
        return new_stmt

    # WHILE
    if isinstance(stmt, WhileStmt):
        cond: Expr = stmt.cond

        if isinstance(cond, IntLiteral) and cond.value == 0:
            return None

        body = dce_block(stmt.body)
        new_stmt = WhileStmt(cond, body)
        # Preserve source mapping
        if id(stmt) in _stmt_src_copy:
            _stmt_src_copy[id(new_stmt)] = _stmt_src_copy[id(stmt)]
        return new_stmt

    # ostatní – ponech
    return stmt

