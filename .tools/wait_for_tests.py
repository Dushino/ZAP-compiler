import time
import os
report = os.path.join(os.path.dirname(__file__), '..', 'tests', 'tests_report.txt')
report = os.path.abspath(report)
print('Waiting for', report)
for _ in range(300):
    if os.path.exists(report):
        text = open(report, 'r', encoding='utf-8', errors='replace').read()
        if 'Test Results Summary' in text:
            print('Found summary')
            print('\n'.join(text.strip().splitlines()[-20:]))
            break
    time.sleep(1)
else:
    print('Timeout waiting for test report')
