code_default = open('tests/pass/026-struct/026-struct.zap').read()
print(f'Default encoding first char: {repr(code_default[0])}')
print(f'Default encoding first 10 chars: {repr(code_default[:10])}')

code_utf8 = open('tests/pass/026-struct/026-struct.zap', encoding='utf-8').read()
print(f'\nUTF-8 encoding first char: {repr(code_utf8[0])}')
print(f'UTF-8 encoding first 10 chars: {repr(code_utf8[:10])}')

code_sig = open('tests/pass/026-struct/026-struct.zap', encoding='utf-8-sig').read()
print(f'\nUTF-8-sig encoding first char: {repr(code_sig[0])}')
print(f'UTF-8-sig encoding first 10 chars: {repr(code_sig[:10])}')
