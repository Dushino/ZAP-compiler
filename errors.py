import sys

class CompileError(Exception):
    """Base class for compiler errors with optional source context.

    Stores line/column and optional filename/source snippet for diagnostics.
    """
    def __init__(self, message, line=None, col=None, node=None):
        """Initialize an error and normalize source position fields."""
        super().__init__(message)
        self.message = message
        # If a node with position info was provided, prefer that
        if node is not None:
            line = getattr(node, "line", line)
            col = getattr(node, "col", col)
        # Normalize the stored values: only positive ints are meaningful;
        # line=0 from AST nodes means "unknown" — treat as None
        self.line = line if isinstance(line, int) and line >= 1 else None
        self.col = col if isinstance(col, int) and col >= 1 else None
        # Optional extra context — auto-extract filename from node if available
        node_filename = getattr(node, "filename", None) if node is not None else None
        self.filename: str | None = node_filename if node_filename else None
        self.source_text: str | None = None
        self._line_mapped: bool = False


class SyntaxError(CompileError):
    """Raised for parse-time errors in the source program."""
    pass


class SemanticError(CompileError):
    """Raised for semantic/type errors after parsing."""
    pass


class TokenizerError(CompileError):
    """Raised for lexical/tokenization errors in the input."""
    pass

def print_error(src, line, col, msg, filename: str | None = None, severity: str = "error"):
    """Emit a single-line diagnostic formatted for editor parsing."""
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
    """Format and print an exception using the compiler's error style."""
    if isinstance(e, CompileError) and e.line is not None:
        src = getattr(e, "source_text", None) or ""
        fname = getattr(e, "filename", None) or filename or "<input>"
        print_error(src, e.line, e.col, e.message, filename=fname, severity="error")
    else:
        fname = filename or "<internal>"
        if isinstance(e, CompileError):
            # Use the clean message without Python exception class name
            print(f"{fname}:1:1: error: {e.message}", file=sys.stderr)
        else:
            # Non-compiler exceptions: include the class name for debugging
            print(f"{fname}:1:1: error: {e.__class__.__name__}: {e}", file=sys.stderr)
