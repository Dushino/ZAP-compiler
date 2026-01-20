#!/usr/bin/env python3
"""Run test suite"""
import os
import subprocess
import sys

os.chdir(r'c:\Users\dusan.holub\src\ZAP-compiler')

# Find all test files
pass_tests = []
fail_tests = []

for root, dirs, files in os.walk('tests/pass'):
    for f in files:
        if f.endswith('.zap'):
            pass_tests.append(os.path.join(root, f))

pass_tests.sort()

print("=" * 70)
print("TESTING SHOULD-PASS FILES")
print("=" * 70)

passed = 0
failed = 0

for test_file in pass_tests:
    # Extract base name
    base = os.path.basename(test_file).replace('.zap', '')
    test_dir = os.path.dirname(test_file)
    
    try:
        # Try to compile
        from parser import Parser
        from compiler_pipeline import compile_program
        
        code = open(test_file).read()
        parser = Parser(code, test_file)
        ast = parser.parse_program()
        asm = compile_program(ast)
        
        print(f"[PASS] {base}")
        passed += 1
    except Exception as e:
        print(f"[FAIL] {base}: {e}")
        failed += 1

print("\n" + "=" * 70)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 70)
