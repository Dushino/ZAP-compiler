#!/usr/bin/env python3
"""Check originally failing tests"""
from parser import Parser
from compiler_pipeline import compile_program

original_failures = [
    'tests/pass/003-pointers/003-pointers.zap',
    'tests/pass/008-cmp/008-cmp.zap',
    'tests/pass/010-pointer-arith/010-pointer-arith.zap',
    'tests/pass/011-pointer-conv/011-pointer-conv.zap',
    'tests/pass/012-deref-in-expr/012-deref-in-expr.zap',
    'tests/pass/022-array-pointer/022-array-pointer.zap',
]

print("Checking originally failing tests:")
print("="*60)

all_pass = True
for test_path in original_failures:
    name = test_path.split('/')[-2]
    try:
        code = open(test_path).read()
        parser = Parser(code, test_path)
        ast = parser.parse_program()
        asm = compile_program(ast)
        print(f"[PASS] {name}")
    except Exception as e:
        from errors import print_exception
        print_exception(e, filename=name)
        all_pass = False

print("="*60)
if all_pass:
    print("SUCCESS: All originally failing tests now pass!")
else:
    print("FAILURE: Some tests still failing")
