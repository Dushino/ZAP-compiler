import os
import subprocess

root = os.path.join(os.path.dirname(__file__), '..')
root = os.path.abspath(root)
pass_root = os.path.join(root, 'tests', 'pass')
errors = []
count = 0
for dirpath, dirs, files in os.walk(pass_root):
    for f in sorted(files):
        if not f.endswith('.zap'):
            continue
        path = os.path.join(dirpath, f)
        out = os.path.join(dirpath, os.path.splitext(f)[0] + '_default.s')
        cmd = ['python', os.path.join(root, 'compiler.py'), path, '-o', out]
        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            count += 1
        except subprocess.CalledProcessError as e:
            errors.append((path, e.output.decode('utf-8', errors='replace')))

print(f"Compiled {count} tests; {len(errors)} errors")
for p, msg in errors[:20]:
    print('--- ERROR compiling:', p)
    print(msg)
