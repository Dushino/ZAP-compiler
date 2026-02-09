from parser import Parser
s = 'FUNC 42 MAIN { END }'
try:
    p = Parser(s)
    p.parse_program()
except Exception as e:
    print('Exception:', type(e).__name__)
    print('Message:', e)
