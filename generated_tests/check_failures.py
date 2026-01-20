#!/usr/bin/env python3
"""Check failing test"""
from parser import Parser
from compiler_pipeline import compile_program
import sys

tests = [
    'tests/pass/003-pointers/003-pointers.zap',
    'tests/pass/008-cmp/008-cmp.zap',
    'tests/pass/010-pointer-arith/010-pointer-arith.zap',
]

for test_file in tests:
    print(f"\n{'='*60}")
    print(f"Testing: {test_file}")
    print('='*60)
    
    try:
        code = open(test_file).read()
        parser = Parser(code, test_file)
        ast = parser.parse_program()
        asm = compile_program(ast)
        print('[OK] Compiled successfully')
    except Exception as e:
        print(f'[ERROR] {e}')
        import traceback
        traceback.print_exc()
