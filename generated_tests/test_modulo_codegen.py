from compiler import compile_file


def test_mod8_codegen_preserves_divisor():
    asm = compile_file('tests/pass/023-modulo/023-modulo.zap')
    # Ensure we save divisor into math operands before calling MOD8
    assert '\tSTA MATH_OP2' in asm
    assert '\tJSR MOD8' in asm
