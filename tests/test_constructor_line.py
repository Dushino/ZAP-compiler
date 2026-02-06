import pytest
from module_system import ModuleSystem
from errors import SemanticError


def test_constructor_error_points_to_original_line():
    ms = ModuleSystem(base_path='.', include_dirs=['./work/lib/atari'])
    with pytest.raises(SemanticError) as excinfo:
        ms.parse_file('work/lib/atari/atari_stdio.zap')
    # The 'proc CONSTRUCTOR()' is at line 67 in the original file
    assert excinfo.value.line == 67
