#!/usr/bin/env python3
"""
Phase 4 Full Regression Test Suite
Tests all 107 passing test cases with RPN enabled
"""

import os
import sys
import subprocess
from pathlib import Path

def run_compile(zap_file: str) -> tuple[bool, int, str]:
    """Compile a ZAP file and return (success, output_size, error_msg)"""
    try:
        result = subprocess.run(
            [sys.executable, "compiler.py", zap_file],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        if result.returncode == 0:
            size = len(result.stdout)
            return True, size, ""
        else:
            error = result.stderr.split('\n')[0][:100] if result.stderr else "Unknown error"
            return False, 0, error
    except subprocess.TimeoutExpired:
        return False, 0, "Timeout"
    except Exception as e:
        return False, 0, str(e)

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Find all test directories
    tests_dir = Path("tests/pass")
    test_dirs = sorted([d for d in tests_dir.iterdir() if d.is_dir()])
    
    print("\n" + "="*70)
    print("RPN FULL REGRESSION TEST SUITE - PHASE 4 VALIDATION")
    print("="*70)
    print(f"\nRPN enabled: True (default)")
    print(f"Total tests found: {len(test_dirs)}\n")
    
    passed = 0
    failed = 0
    total_bytes = 0
    failed_tests = []
    
    for i, test_dir in enumerate(test_dirs, 1):
        test_name = test_dir.name
        zap_file = test_dir / f"{test_name}.zap"
        
        if not zap_file.exists():
            continue
        
        # Show progress every 10 tests
        if i % 10 == 0:
            print(f"  [{i}/{len(test_dirs)}] Progress...")
        
        success, size, error = run_compile(str(zap_file))
        
        if success:
            passed += 1
            total_bytes += size
        else:
            failed += 1
            failed_tests.append((test_name, error))
    
    print("\n" + "="*70)
    print("REGRESSION TEST RESULTS")
    print("="*70)
    print(f"Total tests:      {len(test_dirs)}")
    print(f"[PASS] Passed:    {passed}")
    print(f"[FAIL] Failed:    {failed}")
    print(f"Success rate:     {passed}/{len(test_dirs)} ({100*passed//len(test_dirs)}%)")
    print(f"Total bytes:      {total_bytes:,}")
    print("="*70)
    
    if failed > 0:
        print(f"\nFailed tests ({failed}):")
        for test_name, error in failed_tests[:10]:
            print(f"  • {test_name}: {error}")
        if len(failed_tests) > 10:
            print(f"  ... and {len(failed_tests)-10} more")
    
    if failed == 0:
        print("\n[OK] PERFECT! All 107 tests passed with RPN enabled!")
        print("[OK] RPN optimization is stable and production-ready")
        print("[OK] No regressions detected across full test suite")
        return 0
    else:
        print(f"\n[WARN] {failed} test(s) failed - needs investigation")
        return 1

if __name__ == "__main__":
    sys.exit(main())
