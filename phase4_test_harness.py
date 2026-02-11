#!/usr/bin/env python3
"""
Phase 4 RPN Testing Harness
Tests RPN code generation and measures byte savings

Usage:
    python phase4_test_harness.py
"""

import os
import sys
import subprocess
import difflib
from pathlib import Path

# Test cases to measure
TEST_CASES = [
    "tests/pass/096-arithmetic-16bit/096-arithmetic-16bit.zap",
    "tests/pass/099-mul-div-mod-variants/099-mul-div-mod-variants.zap",
    "tests/pass/100-basic/100-basic.zap",
]

def run_compiler(zap_file: str, rpn_enabled: bool = False) -> tuple[bool, str, int]:
    """Run compiler and return (success, output, size)"""
    env = os.environ.copy()
    if rpn_enabled:
        env["RPN_ENABLED"] = "1"
    
    cmd = [sys.executable, "compiler.py", zap_file]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        success = result.returncode == 0
        size = len(result.stdout) if success else 0
        return success, output, size
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT", 0
    except Exception as e:
        return False, str(e), 0

def extract_code_size(output: str) -> int:
    """Extract the size of generated assembly code"""
    lines = output.strip().split('\n')
    # Count non-comment, non-empty lines as a rough metric
    code_lines = [l for l in lines if l.strip() and not l.strip().startswith(';')]
    return len('\n'.join(code_lines).encode())

def test_case(zap_file: str) -> None:
    """Test a single ZAP file with and without RPN"""
    print(f"\n{'='*70}")
    print(f"Testing: {zap_file}")
    print(f"{'='*70}")
    
    if not os.path.exists(zap_file):
        print(f"❌ File not found: {zap_file}")
        return
    
    # Baseline (RPN disabled)
    print("\n[Baseline - RPN Disabled]")
    success_baseline, output_baseline, size_baseline = run_compiler(zap_file, rpn_enabled=False)
    if not success_baseline:
        print(f"❌ Compilation failed (baseline)")
        print(output_baseline[:500])
        return
    
    code_size_baseline = extract_code_size(output_baseline)
    print(f"✓ Compilation successful")
    print(f"  Output size: {size_baseline} bytes")
    print(f"  Code size:   {code_size_baseline} bytes")
    
    # Modify codegen_expr.py to enable RPN
    print("\n[Enabling RPN]")
    codegen_file = "codegen_expr.py"
    with open(codegen_file, 'r') as f:
        content = f.read()
    
    modified = content.replace(
        "self.rpn_enabled: bool = False",
        "self.rpn_enabled: bool = True"
    )
    
    if modified == content:
        print("⚠ Warning: Could not find rpn_enabled line to modify")
        return
    
    try:
        with open(codegen_file, 'w') as f:
            f.write(modified)
        
        # RPN enabled
        print("\n[RPN Enabled]")
        success_rpn, output_rpn, size_rpn = run_compiler(zap_file, rpn_enabled=False)  # Still False, but rpn_enabled is True in code
        
        if not success_rpn:
            print(f"❌ Compilation failed (RPN enabled)")
            print(output_rpn[:500])
            return
        
        code_size_rpn = extract_code_size(output_rpn)
        print(f"✓ Compilation successful")
        print(f"  Output size: {size_rpn} bytes")
        print(f"  Code size:   {code_size_rpn} bytes")
        
        # Comparison
        print("\n[Comparison]")
        delta = code_size_baseline - code_size_rpn
        percent = (delta / code_size_baseline * 100) if code_size_baseline > 0 else 0
        
        if delta > 0:
            print(f"✓ RPN is smaller by {delta} bytes ({percent:.1f}%)")
        elif delta < 0:
            print(f"⚠ RPN is larger by {-delta} bytes ({-percent:.1f}%)")
        else:
            print(f"= No size difference")
        
        # Check if outputs are similar (should be same or very close)
        baseline_lines = output_baseline.split('\n')[:50]  # First 50 lines for comparison
        rpn_lines = output_rpn.split('\n')[:50]
        
        if baseline_lines[0] == rpn_lines[0]:
            print("✓ Generated code structure matches (first lines identical)")
        else:
            print("⚠ Generated code structure differs (expected for RPN optimization)")
        
    finally:
        # Restore original file
        print("\n[Restoring codegen_expr.py]")
        with open(codegen_file, 'w') as f:
            f.write(content)
        print("✓ Restored")

def main():
    print("\n" + "="*70)
    print("RPN CODE GENERATION - PHASE 4 TESTING")
    print("="*70)
    print(f"\nTesting {len(TEST_CASES)} cases for RPN optimization impact")
    
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    results = []
    for test_file in TEST_CASES:
        test_case(test_file)
    
    print("\n" + "="*70)
    print("PHASE 4 TESTING COMPLETE")
    print("="*70)

if __name__ == "__main__":
    main()
