#!/usr/bin/env python3
"""
Comprehensive test suite for const struct feature
Tests all aspects of const struct declarations to verify full implementation
"""

import sys
from parser import Parser
from compiler_pipeline import compile_program

def test_case(name, code, should_fail=False):
    """Run a single test case"""
    print(f"\n{'='*70}")
    print(f"Test: {name}")
    print(f"{'='*70}")
    print("Code:")
    print("-----")
    for line in code.strip().split('\n'):
        print(f"  {line}")
    print()
    
    try:
        parser = Parser(code, "test.zap")
        ast = parser.parse_program()
        asm = compile_program(ast)
        
        if should_fail:
            print("❌ [FAIL] Should have raised an error but succeeded")
            return False
        else:
            print("✓ [PASS] Compilation succeeded")
            return True
            
    except Exception as e:
        if should_fail:
            print(f"✓ [PASS] Correctly failed with: {e}")
            return True
        else:
            from errors import print_exception
            print_exception(e, filename="<test>")
            return False

# Test cases
tests = [
    (
        "1. Simple const struct (local)",
        """
struct Point
    byte x
    byte y
end

proc main()
    const Point p = { 10, 20 }
    byte temp
    temp = p.x
end
        """,
        False
    ),
    
    (
        "2. Multiple const structs (local)",
        """
struct Point
    byte x
    byte y
end

proc main()
    const Point p1 = { 10, 20 }
    const Point p2 = { 30, 40 }
    byte temp
    temp = p1.x + p2.x
end
        """,
        False
    ),
    
    (
        "3. Complex struct const (local)",
        """
struct Rect
    byte x
    byte y
    byte w
    byte h
end

proc main()
    const Rect r = { 5, 10, 100, 50 }
    byte temp
    temp = r.w
end
        """,
        False
    ),
    
    (
        "4. Global const struct",
        """
struct Point
    byte x
    byte y
end

const Point gp = { 15, 25 }

proc main()
    byte temp
    temp = gp.x
end
        """,
        False
    ),
    
    (
        "5. Multiple global const structs",
        """
struct Point
    byte x
    byte y
end

const Point gp1 = { 10, 20 }
const Point gp2 = { 30, 40 }

proc main()
    byte temp
    temp = gp1.x + gp2.y
end
        """,
        False
    ),
    
    (
        "6. Global const struct - complex",
        """
struct Rect
    byte x
    byte y
    byte w
    byte h
end

const Rect gr = { 1, 2, 3, 4 }

proc main()
    byte temp
    temp = gr.w
end
        """,
        False
    ),
    
    (
        "7. Const enforcement - direct assignment",
        """
struct Point
    byte x
    byte y
end

proc main()
    const Point p = { 10, 20 }
    p = { 99, 99 }
end
        """,
        True
    ),
    
    (
        "8. Const enforcement - field modification",
        """
struct Point
    byte x
    byte y
end

proc main()
    const Point p = { 10, 20 }
    p.x = 50
end
        """,
        True
    ),
    
    (
        "9. Const enforcement - word struct",
        """
struct Pos
    word x
    word y
end

proc main()
    const Pos pos = { 100, 200 }
    pos.x = 999
end
        """,
        True
    ),
    
    (
        "10. Non-const struct - allows modification",
        """
struct Point
    byte x
    byte y
end

proc main()
    Point p = { 10, 20 }
    p.x = 50
end
        """,
        False
    ),
    
    (
        "11. Mixed const and non-const",
        """
struct Point
    byte x
    byte y
end

proc main()
    const Point cp = { 10, 20 }
    Point mp = { 30, 40 }
    byte temp
    temp = cp.x
    mp.x = 99
end
        """,
        False
    ),
    
    (
        "12. Const struct in nested context",
        """
struct Point
    byte x
    byte y
end

proc helper()
    const Point p = { 50, 60 }
    byte temp
    temp = p.x
end

proc main()
    helper()
end
        """,
        False
    ),
]

# Run all tests
print("\n" + "="*70)
print("CONST STRUCT FEATURE - COMPREHENSIVE TEST SUITE")
print("="*70)

passed = 0
failed = 0

for name, code, should_fail in tests:
    if test_case(name, code, should_fail):
        passed += 1
    else:
        failed += 1

# Summary
print(f"\n" + "="*70)
print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
print("="*70)

if failed > 0:
    sys.exit(1)
