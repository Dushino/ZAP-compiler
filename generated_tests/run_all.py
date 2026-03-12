"""Quick test runner that checks pass/fail test results."""
import subprocess, os, glob, re, sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pass_ok = pass_fail = fail_ok = fail_wrong = 0

for d in sorted(glob.glob('tests/pass/*/')):
    base = os.path.basename(d.rstrip('/\\'))
    zap = os.path.join(d, base + '.zap')
    if not os.path.exists(zap):
        continue
    r = subprocess.run([sys.executable, 'compiler.py', zap],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode == 0:
        pass_ok += 1
    else:
        pass_fail += 1
        print(f'FAIL PASS: {base}: {r.stderr.strip()[:100]}')

for d in sorted(glob.glob('tests/fail/*/')):
    base = os.path.basename(d.rstrip('/\\'))
    zap = os.path.join(d, base + '.zap')
    err_file = os.path.join(d, base + '.err')
    if not os.path.exists(zap):
        continue
    r = subprocess.run([sys.executable, 'compiler.py', zap],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        if os.path.exists(err_file):
            with open(err_file) as f:
                expected = f.read().strip()
            actual = r.stderr.strip()
            actual_norm = re.sub(r'^[^:]+:', '', actual, count=1).strip()
            if actual_norm.startswith(expected) or expected in actual:
                fail_ok += 1
            else:
                fail_wrong += 1
                print(f'WRONG FAIL: {base}')
                print(f'  expected: {expected}')
                print(f'  got:      {actual_norm[:120]}')
        else:
            fail_ok += 1
    else:
        fail_wrong += 1
        print(f'WRONG FAIL (no error): {base}')

print(f'\nPass tests: {pass_ok} OK, {pass_fail} FAILED')
print(f'Fail tests: {fail_ok} OK, {fail_wrong} WRONG')
