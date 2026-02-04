import traceback
try:
    import compiler
except Exception:
    traceback.print_exc()
    raise
print('import succeeded')
