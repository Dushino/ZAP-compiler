from compiler import compile_file


def test_mod8_codegen_preserves_divisor():
    asm = compile_file('tests/pass/023-modulo/023-modulo.zap')
    # Ensure we save divisor then restore it before calling MOD8
    assert '\tSTA TMP2' in asm or '\tSTX TMP3' in asm  # initial save should exist
    # After moving dividend to TMP0,TMP0+1 we must restore divisor into A/X
    assert '\tLDA TMP2' in asm
    assert '\tLDX TMP3' in asm
    # And we must call MOD8
    assert '\tJSR MOD8' in asm
