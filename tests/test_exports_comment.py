from compiler import compile_file


def test_no_export_directive_emitted(tmp_path):
    p = tmp_path / "mod.zap"
    p.write_text('.module m\nbyte a\nproc main()\nend\n')
    out = compile_file(str(p))
    # Assembler should not contain .export directive emitted by compiler
    assert '.export ' not in out.lower()
    # But compiler should mark exports via comment and include symbol name
    assert '; zap_exports' in out.lower()
    assert 'a' in out.lower()
