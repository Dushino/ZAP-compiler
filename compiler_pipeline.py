from ast_nodes import Program, AssignStmt, ProcDecl, FuncDecl
from ast_nodes import Program, AssignStmt, ProcDecl, FuncDecl, SegmentDirective
from symbols import SymbolTable, ProcTable, FuncTable
from sema import DeclarationAnalyzer
from sema_expr import ExprTypeChecker
from sema_proc import ProcAnalyzer
from sema_func import FuncAnalyzer
from constsubst import subst_const
from constfold import fold_expr
from codegen_expr import CodeGen
from dce import dce_block
import sys
from jump_threading import jump_threading
from label_cleanup import cleanup_labels
from collections import deque
from typing import Optional, Set

# Global switch to disable all peephole-level optimizations without removing code.
# This is set dynamically by compiler.py based on --peepholes flag
DISABLE_PEEPHOLE_OPTIMIZATIONS = True


def _walk_expr(expr, ctx, global_symtab):
    from ast_nodes import (
        IntLiteral, Identifier, BinaryExpr, UnaryExpr, DerefExpr,
        SubscriptExpr, CallExpr
    )

    if isinstance(expr, IntLiteral):
        return

    if isinstance(expr, Identifier):
        # Mark global usage (locals shadow automatically via scope lookup)
        sym = global_symtab._symbols.get(expr.name)
        if sym is not None and not getattr(sym, "proc_name", ""):
            ctx["used_globals"].add(expr.name)
        return

    if isinstance(expr, CallExpr):
        ctx["func_calls"].add(expr.name)
        for a in expr.args:
            _walk_expr(a, ctx, global_symtab)
        return

    if isinstance(expr, BinaryExpr):
        _walk_expr(expr.left, ctx, global_symtab)
        _walk_expr(expr.right, ctx, global_symtab)
        return

    if isinstance(expr, UnaryExpr):
        _walk_expr(expr.expr, ctx, global_symtab)
        return

    if isinstance(expr, DerefExpr):
        _walk_expr(expr.pointer, ctx, global_symtab)
        return

    if isinstance(expr, SubscriptExpr):
        _walk_expr(expr.array, ctx, global_symtab)
        _walk_expr(expr.index, ctx, global_symtab)
        return


def _walk_stmt(stmt, ctx, global_symtab):
    from ast_nodes import (
        CallStmt, AssignStmt, ReturnStmt, IfStmt, WhileStmt, ForStmt, BreakStmt,
        ContinueStmt
    )

    if isinstance(stmt, CallStmt):
        ctx["proc_calls"].add(stmt.name)
        for a in stmt.args:
            _walk_expr(a, ctx, global_symtab)
        return

    if isinstance(stmt, AssignStmt):
        _walk_expr(stmt.lhs, ctx, global_symtab)
        _walk_expr(stmt.rhs, ctx, global_symtab)
        return

    if isinstance(stmt, ReturnStmt):
        _walk_expr(stmt.expr, ctx, global_symtab)
        return

    if isinstance(stmt, IfStmt):
        _walk_expr(stmt.cond, ctx, global_symtab)
        for s in stmt.then_body:
            _walk_stmt(s, ctx, global_symtab)
        if stmt.else_body:
            for s in stmt.else_body:
                _walk_stmt(s, ctx, global_symtab)
        return

    if isinstance(stmt, WhileStmt):
        _walk_expr(stmt.cond, ctx, global_symtab)
        for s in stmt.body:
            _walk_stmt(s, ctx, global_symtab)
        return

    if isinstance(stmt, ForStmt):
        _walk_expr(stmt.var, ctx, global_symtab)
        _walk_expr(stmt.start, ctx, global_symtab)
        _walk_expr(stmt.end, ctx, global_symtab)
        if stmt.step:
            _walk_expr(stmt.step, ctx, global_symtab)
        for s in stmt.body:
            _walk_stmt(s, ctx, global_symtab)
        return

    # Break/Continue and others carry no identifiers/calls
    if isinstance(stmt, (BreakStmt, ContinueStmt)):
        return


def _walk_initializer(init, ctx, global_symtab):
    from ast_nodes import ExprInit, ListInit, StringInit
    if isinstance(init, ExprInit):
        _walk_expr(init.expr, ctx, global_symtab)
    elif isinstance(init, ListInit):
        for v in init.values:
            _walk_expr(v, ctx, global_symtab)
    elif isinstance(init, StringInit):
        return


def prune_unused(program, analyzed_procs, analyzed_funcs, global_symtab):
    proc_map = {p.ast.name: p for p in analyzed_procs}
    func_map = {f.ast.name: f for f in analyzed_funcs}

    referenced_globals: set[str] = set()
    fixed_globals: set[str] = set(
        name
        for name, sym in list(global_symtab._symbols.items())
        if getattr(sym, "proc_name", "") == "" and sym.address is not None
    )

    ctx = {
        "used_globals": referenced_globals,
        "proc_calls": set(),
        "func_calls": set(),
    }

    # Seed with MAIN
    reachable_procs = set(["MAIN"])
    reachable_funcs = set()

    # Global initializers and declarations may reference globals/funcs
    for decl in program.decls:
        for d in decl.declarators:
            if d.address is not None:
                _walk_expr(d.address, ctx, global_symtab)
            if d.array_size is not None:
                _walk_expr(d.array_size, ctx, global_symtab)
            if d.initializer is not None:
                _walk_initializer(d.initializer, ctx, global_symtab)
            # Declarator's own symbol should be kept if referenced via init above

    proc_queue = deque(["MAIN"])
    func_queue = deque()

    while proc_queue or func_queue:
        if proc_queue:
            pname = proc_queue.popleft()
            proc = proc_map.get(pname)
            if proc is None:
                continue
            # Local declarations can reference globals in initializers/addresses
            for decl in proc.ast.locals:
                for d in decl.declarators:
                    if d.address is not None:
                        _walk_expr(d.address, ctx, global_symtab)
                    if d.array_size is not None:
                        _walk_expr(d.array_size, ctx, global_symtab)
                    if d.initializer is not None:
                        _walk_initializer(d.initializer, ctx, global_symtab)
            for st in proc.ast.body:
                _walk_stmt(st, ctx, global_symtab)
            for called in ctx["proc_calls"]:
                if called not in reachable_procs:
                    reachable_procs.add(called)
                    proc_queue.append(called)
            for fcalled in ctx["func_calls"]:
                if fcalled not in reachable_funcs:
                    reachable_funcs.add(fcalled)
                    func_queue.append(fcalled)
            ctx["proc_calls"].clear()
            ctx["func_calls"].clear()
        else:
            fname = func_queue.popleft()
            func = func_map.get(fname)
            if func is None:
                continue
            # Local declarations can reference globals in initializers/addresses
            for decl in func.ast.locals:
                for d in decl.declarators:
                    if d.address is not None:
                        _walk_expr(d.address, ctx, global_symtab)
                    if d.array_size is not None:
                        _walk_expr(d.array_size, ctx, global_symtab)
                    if d.initializer is not None:
                        _walk_initializer(d.initializer, ctx, global_symtab)
            for st in func.ast.body:
                _walk_stmt(st, ctx, global_symtab)
            for called in ctx["proc_calls"]:
                if called not in reachable_procs:
                    reachable_procs.add(called)
                    proc_queue.append(called)
            for fcalled in ctx["func_calls"]:
                if fcalled not in reachable_funcs:
                    reachable_funcs.add(fcalled)
                    func_queue.append(fcalled)
            ctx["proc_calls"].clear()
            ctx["func_calls"].clear()

    # Filter globals to only used (referenced) or fixed-address
    global_symtab._symbols = {
        name: sym
        for name, sym in global_symtab._symbols.items()
        if getattr(sym, "proc_name", "") != "" or name in referenced_globals or name in fixed_globals
    }

    # Filter procs/funcs
    pruned_procs = [p for p in analyzed_procs if p.ast.name in reachable_procs]
    pruned_funcs = [f for f in analyzed_funcs if f.ast.name in reachable_funcs]

    return pruned_procs, pruned_funcs, referenced_globals


def _walk_expr_locals(expr, used: set[str], local_symtab):
    from ast_nodes import (
        IntLiteral, Identifier, BinaryExpr, UnaryExpr, DerefExpr,
        SubscriptExpr, CallExpr
    )

    if isinstance(expr, IntLiteral):
        return

    if isinstance(expr, Identifier):
        if expr.name in local_symtab._symbols:
            used.add(expr.name)
        return

    if isinstance(expr, CallExpr):
        for a in expr.args:
            _walk_expr_locals(a, used, local_symtab)
        return

    if isinstance(expr, BinaryExpr):
        _walk_expr_locals(expr.left, used, local_symtab)
        _walk_expr_locals(expr.right, used, local_symtab)
        return

    if isinstance(expr, UnaryExpr):
        _walk_expr_locals(expr.expr, used, local_symtab)
        return

    if isinstance(expr, DerefExpr):
        _walk_expr_locals(expr.pointer, used, local_symtab)
        return

    if isinstance(expr, SubscriptExpr):
        _walk_expr_locals(expr.array, used, local_symtab)
        _walk_expr_locals(expr.index, used, local_symtab)
        return


def _walk_stmt_locals(stmt, used: set[str], local_symtab):
    from ast_nodes import (
        CallStmt, AssignStmt, ReturnStmt, IfStmt, WhileStmt, ForStmt, BreakStmt,
        ContinueStmt
    )

    if isinstance(stmt, CallStmt):
        for a in stmt.args:
            _walk_expr_locals(a, used, local_symtab)
        return

    if isinstance(stmt, AssignStmt):
        _walk_expr_locals(stmt.lhs, used, local_symtab)
        _walk_expr_locals(stmt.rhs, used, local_symtab)
        return

    if isinstance(stmt, ReturnStmt):
        _walk_expr_locals(stmt.expr, used, local_symtab)
        return

    if isinstance(stmt, IfStmt):
        _walk_expr_locals(stmt.cond, used, local_symtab)
        for s in stmt.then_body:
            _walk_stmt_locals(s, used, local_symtab)
        if stmt.else_body:
            for s in stmt.else_body:
                _walk_stmt_locals(s, used, local_symtab)
        return

    if isinstance(stmt, WhileStmt):
        _walk_expr_locals(stmt.cond, used, local_symtab)
        for s in stmt.body:
            _walk_stmt_locals(s, used, local_symtab)
        return

    if isinstance(stmt, ForStmt):
        _walk_expr_locals(stmt.var, used, local_symtab)
        _walk_expr_locals(stmt.start, used, local_symtab)
        _walk_expr_locals(stmt.end, used, local_symtab)
        if stmt.step:
            _walk_expr_locals(stmt.step, used, local_symtab)
        for s in stmt.body:
            _walk_stmt_locals(s, used, local_symtab)
        return

    if isinstance(stmt, (BreakStmt, ContinueStmt)):
        return


def _walk_initializer_locals(init, used: set[str], local_symtab):
    from ast_nodes import ExprInit, ListInit, StringInit
    if isinstance(init, ExprInit):
        _walk_expr_locals(init.expr, used, local_symtab)
    elif isinstance(init, ListInit):
        for v in init.values:
            _walk_expr_locals(v, used, local_symtab)
    elif isinstance(init, StringInit):
        return


def prune_unused_locals(analyzed_procs, analyzed_funcs):
    def prune_one(body, locals_list, local_symtab, params):
        used: set[str] = set(p.name for p in params)  # always keep params

        for sym in locals_list:
            if sym.init is not None:
                _walk_initializer_locals(sym.init, used, local_symtab)

        for st in body:
            _walk_stmt_locals(st, used, local_symtab)

        new_symbols = {
            name: sym
            for name, sym in local_symtab._symbols.items()
            if name in used or sym.address is not None  # keep fixed-address locals
        }
        local_symtab._symbols = new_symbols
        return [sym for sym in locals_list if sym.name in used or sym.address is not None]

    for ap in analyzed_procs:
        ap.locals = prune_one(ap.ast.body, ap.locals, ap.symtab.local, ap.ast.params)

    for af in analyzed_funcs:
        af.locals = prune_one(af.ast.body, af.locals, af.symtab.local, af.ast.params)


def compile_program(program: Program, *, target_6502: bool = False, command_line: str | None = None, defined_symbols: Optional[Set[str]] = None, enable_peepholes: bool = False) -> str:
    # --- symbol tables ---
    global_symtab = SymbolTable()
    proc_table = ProcTable()
    func_table = FuncTable()

    # --- declarations ---    
    decl_an = DeclarationAnalyzer(global_symtab)
    for d in program.decls:
        decl_an.analyze(d)
    
    # Check for collisions with .define symbols
    if defined_symbols:
        for name in global_symtab._symbols:
            if name in defined_symbols:
                from errors import SemanticError
                raise SemanticError(f"Variable '{name}' conflicts with .define symbol")

    # --- expression type checker ---
    expr_tc = ExprTypeChecker(global_symtab, func_table)

    # --- procedures and functions ---
    proc_an = ProcAnalyzer(proc_table)
    func_an = FuncAnalyzer(func_table, expr_tc)
    analyzed_procs = []
    analyzed_funcs = []
    
    # first pass: register all proc/func signatures
    for p in program.procs:
        if isinstance(p, ProcDecl):
            proc_an.analyze_decl(p)
            # Check for collision with existing global variables
            if p.name in global_symtab._symbols:
                from errors import SemanticError
                raise SemanticError(f"Procedure '{p.name}' conflicts with existing variable")
            # Check for collision with .define symbols
            if defined_symbols and p.name in defined_symbols:
                from errors import SemanticError
                raise SemanticError(f"Procedure '{p.name}' conflicts with .define symbol")
        elif isinstance(p, FuncDecl):
            func_an.analyze_decl(p)
            # Check for collision with existing global variables
            if p.name in global_symtab._symbols:
                from errors import SemanticError
                raise SemanticError(f"Function '{p.name}' conflicts with existing variable")
            # Check for collision with .define symbols
            if defined_symbols and p.name in defined_symbols:
                from errors import SemanticError
                raise SemanticError(f"Function '{p.name}' conflicts with .define symbol")
    
    # Ensure main() procedure exists (required for initialization code)
    try:
        proc_table.lookup("MAIN")
    except KeyError:
        from errors import SemanticError
        raise SemanticError("Program must have a 'main()' procedure")
    
    # second pass: analyze bodies
    for p in program.procs:
        if isinstance(p, ProcDecl):
            analyzed_procs.append(
                proc_an.analyze_proc(p, global_symtab)
            )
        elif isinstance(p, FuncDecl):
            analyzed_funcs.append(
                func_an.analyze_func(p, global_symtab)
            )

    # --- codegen ---   
    # reuse func_table from analysis (already has all functions registered)
    tc = ExprTypeChecker(global_symtab, func_table)
    pruned_procs, pruned_funcs, used_globals = prune_unused(
        program, analyzed_procs, analyzed_funcs, global_symtab
    )
    analyzed_procs, analyzed_funcs = pruned_procs, pruned_funcs
    # Build parameter specs for procedures and functions (name -> [(param, width)])
    def _build_param_specs_procs(procs):
        specs: dict[str, list[tuple[str, int]]] = {}
        for ap in procs:
            params: list[tuple[str, int]] = []
            for prm in ap.ast.params:
                is_word = prm.type.is_pointer or prm.type.base == "WORD"
                params.append((prm.name, 2 if is_word else 1))
            specs[ap.ast.name] = params
        return specs

    def _build_param_specs_funcs(funcs):
        specs: dict[str, list[tuple[str, int]]] = {}
        for af in funcs:
            params: list[tuple[str, int]] = []
            for prm in af.ast.params:
                is_word = prm.type.is_pointer or prm.type.base == "WORD"
                params.append((prm.name, 2 if is_word else 1))
            specs[af.ast.name] = params
        return specs

    proc_param_specs = _build_param_specs_procs(analyzed_procs)
    func_param_specs = _build_param_specs_funcs(analyzed_funcs)

    cg = CodeGen(
        global_symtab,
        tc,
        is_65c02=not target_6502,
        used_globals=used_globals,
        debug_info=getattr(program, "debug", None),
        command_line=command_line,
        proc_param_specs=proc_param_specs,
        func_param_specs=func_param_specs,
    )

    prune_unused_locals(analyzed_procs, analyzed_funcs)

    cg.gen_file_header()

    # globals init
    cg.gen_globals_header()
    for sym in global_symtab:
        cg.gen_init(sym)
    cg.gen_globals_footer()    

    # Initialize stmt_src tracking for DCE
    from dce import init_stmt_src_tracking, get_updated_stmt_src
    original_debug = getattr(program, "debug", {})
    if original_debug:
        init_stmt_src_tracking(original_debug.get("stmt_src", {}))

    # procedures and functions - First pass: apply DCE to all procs and funcs
    for p in program.procs:
        if isinstance(p, ProcDecl):
            ap = next((ap for ap in analyzed_procs if ap.ast.name == p.name), None)
            if ap:
                ap.ast = ProcDecl(
                    name=ap.ast.name,
                    params=ap.ast.params,
                    locals=ap.ast.locals,
                    body=dce_block(ap.ast.body)
                )
        elif isinstance(p, FuncDecl):
            af = next((af for af in analyzed_funcs if af.ast.name == p.name), None)
            if af:
                af.ast = FuncDecl(
                    name=af.ast.name,
                    ret_type=af.ast.ret_type,
                    params=af.ast.params,
                    locals=af.ast.locals,
                    body=dce_block(af.ast.body)
                )
    
    # Update program.debug and CodeGen's stmt_src with new mappings after all DCE
    # Update in place to preserve references
    if original_debug:
        updated_stmt_src = get_updated_stmt_src()
        original_debug["stmt_src"].clear()
        original_debug["stmt_src"].update(updated_stmt_src)
    
    # Now generate code with updated stmt_src
    for p in program.procs:
        if isinstance(p, SegmentDirective):
            cg.emit(f'.segment "{p.name}"')
            continue
            
        if isinstance(p, ProcDecl):
            ap = next((ap for ap in analyzed_procs if ap.ast.name == p.name), None)
            if ap:
                cg.gen_proc(ap)
        elif isinstance(p, FuncDecl):
            af = next((af for af in analyzed_funcs if af.ast.name == p.name), None)
            if af:
                cg.gen_func(af)

    # Peephole before inserting vars/footer
    if enable_peepholes:
        cg.peephole_optimize()
    else:
        # Keep code legal even with peepholes disabled
        cg.legalize_illegal_ops()

    # Build variable block (now that dynamic temps are known)
    vars_block = cg.gen_vars_block(analyzed_procs, analyzed_funcs)

    # Insert vars in front of the first CODE segment to keep ZP symbols ahead of use
    try:
        code_start = next(i for i, ln in enumerate(cg.code) if ln.strip().startswith('.segment "CODE"'))
    except StopIteration:
        code_start = 0
    cg.code = cg.code[:code_start] + vars_block + cg.code[code_start:]

    cg.gen_file_footer()

    if enable_peepholes:
        cg.peephole_optimize()

        while True:
            new_code1 = jump_threading(cg.code)
            new_code2 = cleanup_labels(new_code1)

            if new_code2 == cg.code:
                break
            cg.code = new_code2
    else:
        # Keep code legal even with peepholes disabled
        cg.legalize_illegal_ops()
    return "\n".join(cg.code)

