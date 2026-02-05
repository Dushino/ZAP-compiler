#!/usr/bin/env python3
"""
Regression test: shifting a WORD then masking and assigning to BYTE must use
16-bit right-shift (RSHIFT_LOOP) and not the 8-bit path (RSHIFT8_LOOP).
"""

import subprocess
import sys
from pathlib import Path

code = """
func word getw()
    return $1234
end

proc main()
    word v = getw()
    byte hi = (v >> 8) & 0xFF
end
"""

def main():
    print("Testing 16-bit right shift used when shifting WORD assigned to BYTE")
    test_file = Path("test_shift_tmp.zap")
    test_file.write_text(code)
    try:
        result = subprocess.run(["python", "compiler.py", str(test_file)], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("Compilation failed")
            print(result.stderr)
            return 1
        asm = result.stdout
        used_rshift_loop = "RSHIFT_LOOP" in asm
        used_rshift8_loop = "RSHIFT8_LOOP" in asm
        if used_rshift_loop and not used_rshift8_loop:
            print("PASS: 16-bit RSHIFT used as expected")
            return 0
        print("FAIL: wrong RSHIFT variant used")
        # For debugging, print snippets
        for line in asm.splitlines():
            if "RSHIFT" in line:
                print(line)
        return 1
    finally:
        if test_file.exists():
            test_file.unlink()

if __name__ == '__main__':
    sys.exit(main())
