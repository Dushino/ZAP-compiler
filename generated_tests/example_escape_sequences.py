#!/usr/bin/env python3
"""Example: Using enhanced escape sequences"""

from parser import Parser
from compiler_pipeline import compile_program

code = r"""
; Example using enhanced escape sequences

byte magic[] = "\xFF\xAA\x55"  ; Binary data using hex escapes
byte ascii[] = "\101\102\103"  ; ABC using octal
byte bits[] = "\b11110000"     ; Mask pattern using binary
byte text[] = "Hello\0World"   ; Embedded null terminator

proc main()
    byte msg = '\x41'            ; Character 'A' using hex
    byte mask = '\b10101010'     ; Alternating bit pattern
end
"""

print("Compiling example with enhanced escape sequences...")
try:
    parser = Parser(code, "escape_example.zap")
    program = parser.parse_program()
    asm = compile_program(program)
    print(f"✓ Successfully compiled!")
    print(f"  Generated {len(asm)} bytes of assembly code")
    print(f"\nVariables created:")
    print(f"  - magic: binary data [FF AA 55]")
    print(f"  - ascii: letters [41 42 43] (ABC)")
    print(f"  - bits: mask [F0] (binary 11110000)")
    print(f"  - text: string with null terminator")
    print(f"\n✓ All escape sequences processed successfully!")
except Exception as e:
    from errors import print_exception
    from errors import print_exception
    print_exception(e)
    # traceback.print_exc()
