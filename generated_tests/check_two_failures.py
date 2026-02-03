#!/usr/bin/env python3
"""Check which tests are failing and why"""
from parser import Parser
from compiler_pipeline import compile_program

tests = [
    ('tests/pass/023-ifdef/023-ifdef.zap', '023-ifdef'),
    ('tests/pass/024-module/024-module.zap', '024-module'),
]

for test_path, name in tests:
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print('='*60)
    
    try:
        code = open(test_path).read()
        print(f"Code preview (first 300 chars):\n{code[:300]}\n")
        
        parser = Parser(code, test_path)
        ast = parser.parse_program()
        asm = compile_program(ast)
        print("SUCCESS")
    except Exception as e:
        from errors import print_exception
        print_exception(e)
