#!/usr/bin/env python3
"""Test that module constructors are called before MAIN and before JMP *"""

from parser import Parser
from compiler_pipeline import compile_program

code = """
proc constructor()
    ; constructor does nothing
end

proc main()
    ; main does nothing
end
"""

try:
    parser = Parser(code, "test.zap")
    program = parser.parse_program()
    # Simulate module system: rename 'constructor' proc to internal name and attach constructors list
    from ast_nodes import ProcDecl
    new_procs = []
    for p in program.procs:
        if isinstance(p, ProcDecl) and p.name.lower() == 'constructor':
            new_procs.append(ProcDecl('__CONSTRUCTOR__mymod', p.params, p.locals, p.body, keep=True, noexport=True, export=False))
        else:
            new_procs.append(p)
    program.procs = new_procs
    program.constructors = ['__CONSTRUCTOR__mymod']
    asm = compile_program(program)
    idx_ctor = asm.find('JSR __CONSTRUCTOR__mymod')
    idx_main = asm.find('JSR MAIN')
    if idx_ctor == -1:
        raise Exception('Constructor call not emitted')
    if idx_main == -1:
        raise Exception('MAIN call not emitted')
    if not (idx_ctor < idx_main):
        raise Exception('Constructor call must appear before MAIN')
    print('[PASS] Constructor ordering test')
except Exception as e:
    from errors import print_exception
    print('[FAIL] Constructor ordering test')
    print_exception(e, filename='<test>')
    raise
