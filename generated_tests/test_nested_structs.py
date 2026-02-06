#!/usr/bin/env python3
"""Test nested struct support in ZAP compiler."""

import subprocess
import sys
import os

def run_compiler(zap_code, target="6502"):
    """Compile ZAP code and return True if successful."""
    # Write to temp file
    with open("/tmp/test_nested.zap", "w") as f:
        f.write(zap_code)
    
    # Run compiler
    try:
        result = subprocess.run(
            ["python3", "compiler.py", f"-{target}", "/tmp/test_nested.zap", "-o", "/tmp/test_nested.s"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Compilation timeout"

def test_nested_struct_definition():
    """Test that nested struct definitions are recognized."""
    code = """
struct Point
    byte X
    byte Y
    byte Z
end

struct Container
    Point pt
    byte flag
end

Container c1 @40000

proc main()
    c1.pt.x = 1
    c1.pt.y = 2
    c1.pt.z = 3
    c1.flag = 4
end
    """
    
    success, output = run_compiler(code)
    assert success, f"Compilation failed: {output}"
    # Check that nested field access code was generated
    with open("/tmp/test_nested.s", "r") as f:
        asm = f.read()
        assert ("_C1" in asm and ("c1.pt.x" in asm or "c1.pt" in asm)), "Generated assembly missing nested field access"

def test_nested_struct_array():
    """Test nested struct inside an array."""
    code = """
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
end
    """
    
    success, output = run_compiler(code)
    assert success, f"Compilation failed: {output}"

def test_multiple_levels_nested():
    """Test multiple levels of nesting (if supported)."""
    code = """
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

Outer o1 @40000

proc main()
    o1.md.in.a = 1
end
    """
    
    success, output = run_compiler(code)
    assert success, f"Multiple level nesting not supported: {output[:200]}"

def test_nested_with_word_fields():
    """Test nested structs with word-sized fields."""
    code = """
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
    
    success, output = run_compiler(code)
    assert success, f"Compilation failed: {output}"

def test_026_struct_example():
    """Test the actual 026-struct.zap example."""
    code_file = "tests/pass/026-struct/026-struct.zap"
    if os.path.exists(code_file):
        try:
            result = subprocess.run(
                ["python3", "compiler.py", "-6502", code_file, "-o", "/tmp/026-test.s"],
                capture_output=True,
                text=True,
                timeout=5
            )
            assert result.returncode == 0, f"026-struct.zap compilation failed: {result.stderr[:200]}"
        except Exception as e:
            raise AssertionError(f"Error running 026-struct test: {str(e)}")
    else:
        import pytest
        pytest.skip("026-struct.zap not found (skipped)")

# Run all tests
def main():
    print("=" * 70)
    print("NESTED STRUCT SUPPORT TEST SUITE")
    print("=" * 70)
    print()
    
    tests = [
        ("Nested Struct Definition", test_nested_struct_definition),
        ("Nested Struct Array", test_nested_struct_array),
        ("Multiple Nesting Levels", test_multiple_levels_nested),
        ("Nested with WORD Fields", test_nested_with_word_fields),
        ("026-struct.zap Example", test_026_struct_example),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            res = test_func()  # type: ignore
            # Some test functions use pytest-style assertions and don't return a tuple.
            if res is None:
                print(f"- {test_name}: skipped")
                continue
            res_any = res  # type: ignore
            try:
                success, message = res_any  # type: ignore
            except Exception:
                print(f"- {test_name}: skipped or unexpected result")
                continue
        except AssertionError as ae:
            print(f"✗ {test_name}: Assertion failed: {ae}")
            failed += 1
            continue
        except Exception as ex:
            print(f"✗ {test_name}: Exception: {ex}")
            failed += 1
            continue

        if success:
            print(f"✓ {test_name}: {message}")
            passed += 1
        else:
            print(f"✗ {test_name}: {message}")
            failed += 1
    
    print()
    print("=" * 70)
    print(f"RESULTS: {passed}/{len(tests)} tests passed")
    if failed > 0:
        print(f"✗ {failed} test(s) failed")
    else:
        print("✓ All tests passed!")
    print("=" * 70)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
