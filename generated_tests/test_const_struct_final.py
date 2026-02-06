#!/usr/bin/env python3
"""
Comprehensive test suite for const struct feature
Tests all aspects of const struct declarations to verify full implementation
"""

import sys
from parser import Parser
from compiler_pipeline import compile_program

def _run_case(name, code, should_fail=False):
    """Run a single test case"""
    try:
        parser = Parser(code, "test.zap")
        ast = parser.parse_program()
        asm = compile_program(ast)
        
        if should_fail:
            return False, "Should have raised an error but succeeded"
        else:
            return True, "OK"
            
    except Exception as e:
        if should_fail:
            return True, str(e)
        else:
            return False, str(e)

# Test cases
tests = [
    ("Simple const struct (local)", 
     "struct Point\n    byte x\n    byte y\nend\n\nproc main()\n    const Point p = { 10, 20 }\n    byte temp\n    temp = p.x\nend", False),
    
    ("Multiple const structs (local)",
     "struct Point\n    byte x\n    byte y\nend\n\nproc main()\n    const Point p1 = { 10, 20 }\n    const Point p2 = { 30, 40 }\n    byte temp\n    temp = p1.x + p2.x\nend", False),
    
    ("Complex struct const (local)",
     "struct Rect\n    byte x\n    byte y\n    byte w\n    byte h\nend\n\nproc main()\n    const Rect r = { 5, 10, 100, 50 }\n    byte temp\n    temp = r.w\nend", False),
    
    ("Global const struct",
     "struct Point\n    byte x\n    byte y\nend\n\nconst Point gp = { 15, 25 }\n\nproc main()\n    byte temp\n    temp = gp.x\nend", False),
    
    ("Multiple global const structs",
     "struct Point\n    byte x\n    byte y\nend\n\nconst Point gp1 = { 10, 20 }\nconst Point gp2 = { 30, 40 }\n\nproc main()\n    byte temp\n    temp = gp1.x + gp2.y\nend", False),
    
    ("Global const struct - complex",
     "struct Rect\n    byte x\n    byte y\n    byte w\n    byte h\nend\n\nconst Rect gr = { 1, 2, 3, 4 }\n\nproc main()\n    byte temp\n    temp = gr.w\nend", False),
    
    ("Const enforcement - field modification",
     "struct Point\n    byte x\n    byte y\nend\n\nproc main()\n    const Point p = { 10, 20 }\n    p.x = 50\nend", True),
    
    ("Const enforcement - word struct",
     "struct Pos\n    word x\n    word y\nend\n\nproc main()\n    const Pos pos = { 100, 200 }\n    pos.x = 999\nend", True),
    
    ("Non-const struct - allows modification",
     "struct Point\n    byte x\n    byte y\nend\n\nproc main()\n    Point p = { 10, 20 }\n    p.x = 50\nend", False),
    
    ("Mixed const and non-const",
     "struct Point\n    byte x\n    byte y\nend\n\nproc main()\n    const Point cp = { 10, 20 }\n    Point mp = { 30, 40 }\n    byte temp\n    temp = cp.x\n    mp.x = 99\nend", False),
    
    ("Const struct in nested context",
     "struct Point\n    byte x\n    byte y\nend\n\nproc helper()\n    const Point p = { 50, 60 }\n    byte temp\n    temp = p.x\nend\n\nproc main()\n    helper()\nend", False),
]

# Run all tests
print("="*70)
print("CONST STRUCT FEATURE - COMPREHENSIVE TEST SUITE")
print("="*70)

passed = 0
failed = 0
failed_tests = []

for name, code, should_fail in tests:
    success, msg = _run_case(name, code, should_fail)
    status = "[PASS]" if success else "[FAIL]"
    print(f"{status} {name}")
    if not success:
        print(f"<test {name}>:1:1: error: {msg}", file=sys.stderr)
        failed_tests.append((name, msg))
        failed += 1
    else:
        passed += 1

# Summary
print("\n" + "="*70)
print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
print("="*70)

if failed > 0:
    print("\nFailed tests:")
    for name, msg in failed_tests:
        print(f"  - {name}: {msg}")
    sys.exit(1)
else:
    print("\nAll tests PASSED!")
