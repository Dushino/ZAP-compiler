import traceback
import compiler
try:
    compiler.compile_file('tests/pass/110-expressions/110-expressions.zap')
except Exception:
    traceback.print_exc()
    raise
print('compile_file returned successfully')
