import sys

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

def print_error(src, line, col, msg, filename: str | None = None, severity: str = "error"):
    """Print a single-line error suitable for editor parsing:

    Format: filename:line:column: severity: message
    """
    # Ensure filename and numeric line/col for one-line format
    fname = filename or "<input>"
    line_num = line if isinstance(line, int) and line >= 1 else 1
    col_num = col if isinstance(col, int) and col >= 1 else 1
    # Print a single-line message suitable for editors/linters
    try:
        print(f"{fname}:{line_num}:{col_num}: {severity}: {msg}", file=sys.stderr)
    except Exception:
        # Fallback to a very simple print if something unusual happens
        print(f"{fname}:{line_num}:{col_num}: {severity}: {msg}")


def print_exception(e: Exception, filename: str | None = None):
    """Print an exception using the unified single-line format.

    Handles CompileError (with line/col) specially; falls back to a generic
    one-line message for other exceptions.
    """
    if isinstance(e, CompileError) and e.line is not None:
        src = getattr(e, "source_text", None) or ""
        fname = getattr(e, "filename", None) or filename or "<input>"
        print_error(src, e.line, e.col, e.message, filename=fname, severity="error")
    else:
        fname = filename or "<internal>"
        print(f"{fname}:1:1: error: {e.__class__.__name__}: {e}", file=sys.stderr)
