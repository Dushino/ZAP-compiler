

class CompileError(Exception):
    def __init__(self, message, line=None, col=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col


class SyntaxError(CompileError):
    pass


class SemanticError(CompileError):
    pass


class TokenizerError(CompileError):
    pass

def print_error(src, line, col, msg):
    lines = src.splitlines()
    print(f"Error at line {line}, column {col}:")
    print(lines[line-1])
    print(" " * (col-1) + "^")
    print(msg)
