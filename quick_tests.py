#!/usr/bin/env python3
"""Quick test counter"""
import os
from parser import Parser
from compiler_pipeline import compile_program

tests_dir = r'tests\pass'
passed = 0
failed = 0
errors = []

for root, dirs, files in os.walk(tests_dir):
    for f in sorted(files):
        if f.endswith('.zap'):
            test_path = os.path.join(root, f)
            test_name = os.path.dirname(test_path).split(os.sep)[-1]
            
            try:
                code = open(test_path).read()
                parser = Parser(code, test_path)
                ast = parser.parse_program()
                asm = compile_program(ast)
                print(f"[PASS] {test_name}")
                passed += 1
            except Exception as e:
                print(f"[FAIL] {test_name}: {str(e)[:60]}")
                errors.append((test_name, str(e)))
                failed += 1

print(f"\n{'='*60}")
print(f"TOTAL: {passed} passed, {failed} failed")
print(f"{'='*60}")
