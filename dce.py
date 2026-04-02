
# The author of this software stands in solidarity with 🇺🇦 Ukraine. 
# We believe in a world where international borders are respected and human rights are upheld. 
# We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


"""Dead code elimination for ZAP AST.

Removes unreachable code: dead branches in if/while/repeat-until,
and statements after break/continue/return.  Preserves source-line
mappings in the stmt_src dict so error reporting stays correct.
"""

from ast_nodes import (
    Expr, IfStmt, WhileStmt, RepeatUntilStmt, SwitchStmt, SwitchCase, BreakStmt, ContinueStmt,
    ReturnStmt
)
from ast_nodes import IntLiteral


def dce_block(stmts: list, stmt_src: dict[int, tuple] | None = None) -> list:
    """Apply dead-code elimination to a list of statements.

    stmt_src: optional id(stmt) → source-info dict; updated in-place
    when statements are rewritten so that error locations survive DCE.
    """
    out = []
    for stmt in stmts:
        out_stmt = _dce_stmt(stmt, stmt_src)
        if out_stmt is None:
            continue

        if isinstance(out_stmt, list):
            out.extend(out_stmt)
        else:
            out.append(out_stmt)

        if isinstance(stmt, (BreakStmt, ContinueStmt, ReturnStmt)):
            break   # everything after this is dead code

    return out


def _dce_stmt(stmt, stmt_src: dict[int, tuple] | None = None):
    """Rewrite a single statement, dropping code proven unreachable."""
    # IF
    if isinstance(stmt, IfStmt):
        cond: Expr = stmt.cond

        if isinstance(cond, IntLiteral):
            if cond.value == 0:
                return None
            else:
                return dce_block(stmt.then_body, stmt_src)

        then_body = dce_block(stmt.then_body, stmt_src)
        else_body = dce_block(stmt.else_body, stmt_src) if stmt.else_body else None

        new_stmt = IfStmt(cond, then_body, else_body)
        _copy_src_mapping(stmt, new_stmt, stmt_src)
        return new_stmt

    # WHILE
    if isinstance(stmt, WhileStmt):
        cond: Expr = stmt.cond

        if isinstance(cond, IntLiteral) and cond.value == 0:
            return None

        body = dce_block(stmt.body, stmt_src)
        new_stmt = WhileStmt(cond, body)
        _copy_src_mapping(stmt, new_stmt, stmt_src)
        return new_stmt

    # REPEAT-UNTIL
    if isinstance(stmt, RepeatUntilStmt):
        cond: Expr = stmt.cond

        body = dce_block(stmt.body, stmt_src)
        if isinstance(cond, IntLiteral) and (cond.value & 0xFFFF) != 0:
            return body

        new_stmt = RepeatUntilStmt(body, cond)
        _copy_src_mapping(stmt, new_stmt, stmt_src)
        return new_stmt

    # SWITCH
    if isinstance(stmt, SwitchStmt):
        new_cases = []
        for case in stmt.cases:
            body = dce_block(case.body, stmt_src)
            new_cases.append(SwitchCase(case.labels, body, case.is_default))
        new_stmt = SwitchStmt(stmt.expr, new_cases)
        _copy_src_mapping(stmt, new_stmt, stmt_src)
        return new_stmt

    # all other statements — keep as-is
    return stmt


def _copy_src_mapping(old_stmt, new_stmt, stmt_src: dict[int, tuple] | None) -> None:
    """Preserve source mapping when a statement is rewritten by DCE."""
    if stmt_src is not None and id(old_stmt) in stmt_src:
        stmt_src[id(new_stmt)] = stmt_src[id(old_stmt)]
