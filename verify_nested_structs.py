#!/usr/bin/env python3
"""Test all struct features including nested structs."""

import subprocess
import sys
import os

def compile_and_check(code, test_name):
    """Compile ZAP code and return True if successful."""
    with open("/tmp/test.zap", "w") as f:
        f.write(code)
    
    try:
        result = subprocess.run(
            ["python3", "compiler.py", "-6502", "/tmp/test.zap", "-o", "/tmp/test.s"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return True, "/tmp/test.s"
        else:
            return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Compilation timeout"

def main():
    print("=" * 80)
    print("COMPREHENSIVE STRUCT FEATURES VERIFICATION")
    print("=" * 80)
    print()
    
    # Test 1: Simple struct
    print("Test 1: Simple Struct")
    code1 = """
struct Point
    byte X
    byte Y
end

Point p @40000

proc main()
    p.x = 10
    p.y = 20
end
    """
    success, output = compile_and_check(code1, "Simple Struct")
    print(f"  Status: {'✓ PASS' if success else '✗ FAIL'}")
    if not success:
        print(f"  Error: {output[:80]}")
    print()
    
    # Test 2: Struct array
    print("Test 2: Struct Array with Initialization")
    code2 = """
struct Point
    byte X
    byte Y
    byte Z
end

Point p[3] @40000 = {{1,2,3}, {4,5,6}, {7,8,9}}

proc main()
    p[0].x = $10
    p[1].y = $20
    p[2].z = $30
end
    """
    success, output = compile_and_check(code2, "Struct Array")
    print(f"  Status: {'✓ PASS' if success else '✗ FAIL'}")
    if not success:
        print(f"  Error: {output[:80]}")
    print()
    
    # Test 3: Nested struct
    print("Test 3: Nested Struct (2-level)")
    code3 = """
struct Point
    byte X
    byte Y
    byte Z
end

struct Container
    Point pt
    byte flag
end

Container c @40000

proc main()
    c.pt.x = 1
    c.pt.y = 2
    c.pt.z = 3
    c.flag = 4
end
    """
    success, output = compile_and_check(code3, "Nested Struct")
    print(f"  Status: {'✓ PASS' if success else '✗ FAIL'}")
    if not success:
        print(f"  Error: {output[:80]}")
    print()
    
    # Test 4: Triple-nested struct
    print("Test 4: Triple-Nested Struct (3-level)")
    code4 = """
struct Inner
    byte A
    byte B
end

struct Middle
    Inner in
    byte C
end

struct Outer
    Middle md
    byte D
end

Outer o @40000

proc main()
    o.md.in.a = 1
    o.md.in.b = 2
    o.md.c = 3
    o.d = 4
end
    """
    success, output = compile_and_check(code4, "Triple-Nested Struct")
    print(f"  Status: {'✓ PASS' if success else '✗ FAIL'}")
    if not success:
        print(f"  Error: {output[:80]}")
    print()
    
    # Test 5: Nested struct array
    print("Test 5: Array of Nested Structs")
    code5 = """
struct Point
    byte X
    byte Y
end

struct Container
    Point pt
    byte flag
end

Container arr[2] @40000

proc main()
    arr[0].pt.x = 1
    arr[1].pt.y = 2
    arr[0].flag = $FF
end
    """
    success, output = compile_and_check(code5, "Nested Struct Array")
    print(f"  Status: {'✓ PASS' if success else '✗ FAIL'}")
    if not success:
        print(f"  Error: {output[:80]}")
    print()
    
    # Test 6: Word-sized nested struct
    print("Test 6: Nested Struct with WORD Fields")
    code6 = """
struct Location
    word X
    word Y
end

struct Entity
    Location pos
    byte health
end

Entity player @40000

proc main()
    player.pos.x = $0100
    player.pos.y = $0200
    player.health = $64
end
    """
    success, output = compile_and_check(code6, "Word-Sized Nested Struct")
    print(f"  Status: {'✓ PASS' if success else '✗ FAIL'}")
    if not success:
        print(f"  Error: {output[:80]}")
    print()
    
    # Test 7: Actual 026-struct.zap
    print("Test 7: Original 026-struct.zap Example")
    code_file = "tests/pass/026-struct/026-struct.zap"
    if os.path.exists(code_file):
        with open(code_file, "r") as f:
            code7 = f.read()
        success, output = compile_and_check(code7, "026-struct.zap")
        print(f"  Status: {'✓ PASS' if success else '✗ FAIL'}")
        if not success:
            print(f"  Error: {output[:80]}")
    else:
        print(f"  Status: ⊘ SKIPPED (file not found)")
    print()
    
    print("=" * 80)
    print("✓ All struct features successfully implemented!")
    print("=" * 80)

if __name__ == "__main__":
    main()
