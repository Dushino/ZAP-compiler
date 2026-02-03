#!/usr/bin/env python3

import sys
import re
from parser import Parser
from compiler_pipeline import compile_program

def test_cases():
    tests = []
    
    # Test 1: Global struct simple
    tests.append(("Global struct simple", """
struct Point
    byte x
    byte y
end

Point global_pt

proc main()
    global_pt.x = 1
    global_pt.y = 2
end
""", "_GLOBAL_PT:"))
    
    # Test 2: Local struct simple
    tests.append(("Local struct simple", """
struct Point
    byte x
    byte y
end

proc main()
    Point local_pt
    local_pt.x = 1
    local_pt.y = 2
end
""", "_MAIN_LOCAL_PT:"))
    
    # Test 3: Struct array
    tests.append(("Struct array (3x2=6 bytes)", """
struct Point
    byte x
    byte y
end

proc main()
    Point arr[3]
    arr[0].x = 1
    arr[1].y = 2
    arr[2].x = 3
end
""", "_MAIN_ARR:"))
    
    # Test 4: Larger struct (4 fields)
    tests.append(("Larger struct (4 bytes)", """
struct Rect
    byte x
    byte y
    byte w
    byte h
end

proc main()
    Rect r
    r.x = 1
    r.y = 2
    r.w = 10
    r.h = 20
end
""", "_MAIN_R:"))
    
    # Test 5: Global array
    tests.append(("Global struct array (2x2=4 bytes)", """
struct Point
    byte x
    byte y
end

Point arr[2]

proc main()
    arr[0].x = 1
    arr[1].x = 2
end
""", "_ARR:"))
    
    return tests

def run_tests():
    tests = test_cases()
    results = []
    
    print("=" * 70)
    print("STRUCT COMPILATION TESTS")
    print("=" * 70)
    
    for test_name, code, expected_symbol in tests:
        try:
            parser = Parser(code, "test.zap")
            ast = parser.parse_program()
            asm = compile_program(ast)
            
            if expected_symbol in asm:
                print(f"[PASS] {test_name}")
                results.append(True)
            else:
                print(f"[FAIL] {test_name} - symbol not found: {expected_symbol}")
                results.append(False)
        except Exception as e:
            from errors import print_exception
            print_exception(e, filename=f"<test {test_name}>")
            results.append(False)
    
    print("\n" + "=" * 70)
    print(f"Results: {sum(results)}/{len(results)} passed")
    print("=" * 70)
    
    return all(results)

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
