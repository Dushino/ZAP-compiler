from compiler import compile_file


def test_playf2_visible():
    # Should compile without semantic errors and produce output
    out = compile_file('work/test_stdio.zap', target_6502=True, predefined_symbols={'ATARI'}, include_dirs=['lib'])
    assert out is not None and len(out) > 0
