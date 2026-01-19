code_bytes = open('tests/pass/026-struct/026-struct.zap', 'rb').read()
print(f'First 10 bytes: {code_bytes[:10]}')
print(f'Is BOM (EF BB BF): {code_bytes[:3] == b"\\xef\\xbb\\xbf"}')

code_str = code_bytes.decode('utf-8')
print(f'First char repr: {repr(code_str[0])}')
print(f'First char ord: {ord(code_str[0])}')
print(f'Is BOM char: {code_str[0] == chr(0xFEFF)}')

# Check without BOM
code_str_no_bom = code_bytes.decode('utf-8-sig')
print(f'\nWith utf-8-sig:')
print(f'First char repr: {repr(code_str_no_bom[0])}')
