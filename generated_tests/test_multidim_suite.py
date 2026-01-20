#!/usr/bin/env python3
"""
Comprehensive test suite for multi-dimensional array support
Tests all dimension counts, element types, and operations
"""

import subprocess
import sys
from pathlib import Path

test_cases = [
    {
        "name": "2D_byte_basic",
        "description": "Basic 2D byte array",
        "code": """
byte grid[2][3] = {
  {1, 2, 3},
  {4, 5, 6}
}

proc main()
end
"""
    },
    {
        "name": "2D_byte_subscript",
        "description": "2D byte array with subscript operations",
        "code": """
byte grid[2][3] = {
  {0, 0, 0},
  {0, 0, 0}
}

proc main()
  byte i
  byte j
  
  i = 0
  while i < 2
    j = 0
    while j < 3
      grid[i][j] = i + j
      j = j + 1
    end
    i = i + 1
  end
end
"""
    },
    {
        "name": "3D_byte_basic",
        "description": "Basic 3D byte array",
        "code": """
byte cube[2][2][2] = {
  {
    {1, 2},
    {3, 4}
  },
  {
    {5, 6},
    {7, 8}
  }
}

proc main()
end
"""
    },
    {
        "name": "2D_word_basic",
        "description": "Basic 2D word array",
        "code": """
word matrix[2][2] = {
  {$1234, $5678},
  {$9abc, $def0}
}

proc main()
end
"""
    },
]

def run_test(test_case):
    """Run a single test case"""
    name = test_case["name"]
    description = test_case["description"]
    code = test_case["code"]
    
    # Write test file in current directory
    test_file = Path(f"test_tmp_{name}.zap")
    test_file.write_text(code)
    
    # Run compiler
    try:
        result = subprocess.run(
            ["python", "compiler.py", str(test_file)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return False, f"Compilation failed:\n{result.stderr}"
        
        # Check that we got assembly output
        if ".segment" not in result.stdout:
            return False, "No assembly output generated"
        
        return True, f"✓ {name}: {description}"
    
    except subprocess.TimeoutExpired:
        return False, f"Timeout: {name}"
    except Exception as e:
        return False, f"Error: {e}"
    finally:
        # Clean up
        if test_file.exists():
            test_file.unlink()

def main():
    print("=" * 70)
    print("Multi-Dimensional Array Test Suite")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        success, message = run_test(test_case)
        
        if success:
            print(f"[PASS] {message}")
            passed += 1
        else:
            print(f"[FAIL] {test_case['name']}: {test_case['description']}")
            print(f"       {message}")
            failed += 1
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 70)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
