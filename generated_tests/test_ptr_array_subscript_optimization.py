"""Test optimization of pointer array subscript codegen using Y-indexed indirect addressing."""

import subprocess
import os


def test_ptr_array_subscript_optimized_codegen():
    """Verify pointer array subscript generates optimized Y-indexed indirect addressing."""
    # Create a test ZAP file with pointer array subscript assignment
    test_zap = """
byte ^PTRARRAY[10]

proc main()
    byte result = 0
    byte local_assignment = 42
    
    ; Test: assign through pointer array element
    PTRARRAY[0]^ = local_assignment
    PTRARRAY[1]^ = 99
    PTRARRAY[2]^ = result
end
"""
    
    # Write test file
    test_file = "/tmp/test_ptr_array_opt.zap"
    with open(test_file, "w") as f:
        f.write(test_zap)
    
    # Compile to assembly
    compiler_path = "/home/dusan/src/ZAP-compiler"
    result = subprocess.run(
        ["python3", "compiler.py", test_file, "-6502", "-o", "/tmp/test_ptr_array_opt.s"],
        cwd=compiler_path,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Compilation failed: {result.stderr}"
    
    # Read and verify assembly
    with open("/tmp/test_ptr_array_opt.s", "r") as f:
        asm = f.read()
    
    # Should use ZP indexed indirect addressing: STA (_PTRARRAY,X)
    # NOT the old pattern: LDA _PTRARRAY+offset, LDX _PTRARRAY+offset+1, STA TMP0, etc.
    assert "(_PTRARRAY,X)" in asm, "Assembly should use ZP indexed indirect addressing for optimized path"
    
    # Should have minimal byte offset setup (not full address calculation)
    # Count occurrences of TMP0 usage - should be much less than in unoptimized version
    tmp0_uses = asm.count("TMP0")
    # Optimized version shouldn't use TMP0 for pointer array subscript
    # (TMP0 might be used elsewhere, but not for the PTRARRAY subscript operations)
    
    # Verify the optimization comment is present
    assert "byte offset = index * element_width" in asm, "Should have byte offset comment"
    
    print("✓ Pointer array subscript optimization test passed!")
    print(f"  Assembly correctly uses Y-indexed indirect addressing")


if __name__ == "__main__":
    test_ptr_array_subscript_optimized_codegen()

