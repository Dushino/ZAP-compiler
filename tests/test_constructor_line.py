import pytest
from module_system import ModuleSystem
from errors import SemanticError


def test_constructor_error_points_to_original_line():
    ms = ModuleSystem(base_path='.', include_dirs=['./work/lib/atari'])
    program, _is_module, _module_name, _includes, _defined_symbols, _module_directive_info = ms.parse_file('work/lib/atari/atari_stdio.zap')
    # Find actual line of 'proc CONSTRUCTOR' in the original file and ensure
    # the parser's orig_line_map maps the proc line back to that original line.
    proc_info = None
    for k, v in (program.debug.get('proc_src') or {}).items():
        if 'constructor' in k.lower():
            proc_info = v
            break
    assert proc_info is not None
    orig_map = (program.debug or {}).get('orig_line_map')
    assert orig_map is not None
    line_no = proc_info[1]
    assert 1 <= line_no <= len(orig_map)
    # Find the line where the constructor is declared in the original file
    expected_line = None
    with open('work/lib/atari/atari_stdio.zap', 'r', encoding='utf-8') as f:
        for idx, l in enumerate(f, start=1):
            if l.strip().lower().startswith('proc constructor'):
                expected_line = idx
                break
    assert expected_line is not None
    assert orig_map[line_no - 1] == expected_line
