import os
from parser import Parser
from module_system import ModuleSystem
from compiler import compile_file


def test_declaration_modifiers_parsed():
    src = """
    byte g = 5 #KEEP #NOEXPORT
    const byte c = 10 #KEEP
    """
    p = Parser(src, filename='<test>')
    prog = p.parse_program()
    # top-level declarations
    decls = prog.decls
    assert any(getattr(d, 'keep', False) for d in decls)
    assert any(getattr(d, 'noexport', False) for d in decls)


def test_module_exports_respect_decl_modifiers(tmp_path):
    # create a module file
    p = tmp_path / "m1.zap"
    p.write_text('.module "m1"\nbyte a #NOEXPORT\nbyte b\nproc modentry()\nend\n')
    ms = ModuleSystem(base_path=os.getcwd())
    program, defs = ms.build_program(str(p))
    exports = getattr(program, 'exports', set())
    assert 'A' not in exports
    assert 'B' in exports


def test_prune_respects_keep_global(tmp_path):
    p = tmp_path / "keepvar.zap"
    p.write_text('.module "kmod"\nbyte KEEPVAR #KEEP\nproc modproc()\nend\n')
    # Create a small main program that includes the module so program has a main()
    main = tmp_path / "main.zap"
    main.write_text('.include "keepvar.zap"\nproc main()\nend\n')
    out = compile_file(str(main))
    # KEEPVAR should appear in exports or in generated output
    assert 'KEEPVAR' in out.upper()


def test_parse_error_filename_set_on_module_parse(tmp_path):
    # create a broken included file
    bad = tmp_path / "bad.zap"
    bad.write_text('byte\n')
    main = tmp_path / "main.zap"
    main.write_text('.include "bad.zap"\nproc main()\nend\n')

    ms = ModuleSystem(base_path=os.getcwd())
    try:
        ms.build_program(str(main))
        assert False, "Expected exception"
    except Exception as e:
        # The parser exception should have filename set to the bad file path
        fname = getattr(e, 'filename', None)
        assert fname is not None
        assert os.path.abspath(str(bad)) == os.path.abspath(fname)
