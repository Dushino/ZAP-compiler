import os
from parser import Parser
from module_system import ModuleSystem


def test_proc_modifiers_parsed():
    with open('work/lib/atari/atari_stdio.zap', encoding='utf-8') as f:
        src = f.read()
    p = Parser(src, filename='work/lib/atari/atari_stdio.zap')
    prog = p.parse_program()
    # Find proc named atari_file_data_area (tokenizer uppercases identifiers)
    found = None
    for item in prog.procs:
        if hasattr(item, 'name') and item.name.upper() == 'ATARI_FILE_DATA_AREA':
            found = item
            break
    assert found is not None, 'Expected to find atari_file_data_area proc'
    assert getattr(found, 'keep', False) is True
    assert getattr(found, 'noexport', False) is True


def test_module_exports_respect_noexport():
    ms = ModuleSystem(base_path=os.getcwd())
    program, defs = ms.build_program('work/lib/atari/atari_stdio.zap')
    exports = getattr(program, 'exports', set())
    # The proc marked #NOEXPORT should not be in exports
    assert 'ATARI_FILE_DATA_AREA' not in exports


def test_export_modifier_parsed():
    with open('work/tmp_nonmodule.zap', encoding='utf-8') as f:
        src = f.read()
    p = Parser(src, filename='work/tmp_nonmodule.zap')
    prog = p.parse_program()
    found = None
    for item in prog.procs:
        if hasattr(item, 'name') and item.name.upper() == 'EXPORTED_PROC':
            found = item
            break
    assert found is not None
    assert getattr(found, 'export', False) is True
