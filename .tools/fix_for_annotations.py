import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
py_files = list(root.glob('*.py')) + list(root.glob('**/*.py'))
pattern = re.compile(r"for\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_\[\]\.|\s,<>\|]+)\s+in\s")

fixed = []
for p in py_files:
    if 'venv' in p.parts or '.git' in p.parts:
        continue
    text = p.read_text(encoding='utf-8')
    new_text, n = pattern.subn(lambda m: f"for {m.group(1)} in ", text)
    if n > 0:
        p.write_text(new_text, encoding='utf-8')
        fixed.append((p, n))

print('Fixed files:')
for p, n in fixed:
    print(p, n)
print('Done')
