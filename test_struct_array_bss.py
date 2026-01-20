#!/usr/bin/env python3

from parser import Parser
from compiler_pipeline import compile_program

code = """
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
"""

parser = Parser(code, "test.zap")
ast = parser.parse_program()
asm = compile_program(ast)

print("Generated Assembly:")
print("=" * 70)
for line in asm.splitlines():
    print(line)

# Check for correct BSS allocation
import re
bss_section = re.search(r'\.segment "BSS"(.*?)\.segment', asm, re.DOTALL)
if bss_section:
    print("\n" + "=" * 70)
    print("BSS SECTION:")
    print(bss_section.group(1))
    
    # Check if array is allocated correctly
    # Point arr[3] with size 2 bytes = 6 bytes total
    if "_MAIN_ARR:" in bss_section.group(1):
        res_match = re.search(r'_MAIN_ARR:\s+\.res\s+(\d+)', bss_section.group(1))
        if res_match:
            allocated = int(res_match.group(1))
            print(f"\nArray allocation: {allocated} bytes")
            print(f"Expected: 6 bytes (3 elements × 2 bytes/element)")
            print(f"Result: {'PASS' if allocated == 6 else 'FAIL'}")
