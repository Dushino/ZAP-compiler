

class CompileError(Exception):
    def __init__(self, message, line=None, col=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        # Optional extra context
        self.filename: str | None = None
        self.source_text: str | None = None


class SyntaxError(CompileError):
    pass


class SemanticError(CompileError):
    pass


class TokenizerError(CompileError):
    pass

def print_error(src, line, col, msg, filename: str | None = None):
    lines = src.splitlines()
    where = f"{filename}:{line}:{col}" if filename else f"line {line}, column {col}"
    # Print message and location
    print(f"Error: {msg}")
    print(f" at {where}")
    # Show offending line with caret
    if 1 <= line <= len(lines):
        print(lines[line-1])
        if col is not None and col >= 1:
            print(" " * (col-1) + "^")
