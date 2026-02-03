import os
from module_system import ModuleSystem


def test_include_chain():
    ms = ModuleSystem(base_path=os.getcwd())
    program, defs = ms.build_program('work/tmp_test.zap')
    proc_names = set(p.name.upper() for p in program.procs if hasattr(p, 'name'))
    assert 'CLS' in proc_names
    assert 'MAIN2' in proc_names
