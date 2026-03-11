#!/usr/bin/env python3
"""Preprocessor for handling conditional compilation directives."""

from typing import Optional, Set
from errors import CompileError


class PreprocessorError(CompileError):
    def __init__(self, message: str, line: int = 0, col: int = 1):
        """Create a preprocessor-specific error with line/column info."""
        super().__init__(message, line=line, col=col)


class Preprocessor:
    def __init__(self, predefined_symbols: Optional[Set[str]] = None):
        """Initialize the preprocessor with optional predefined symbols."""
        self.defined_symbols: Set[str] = predefined_symbols.copy() if predefined_symbols else set()
    
    def process(self, source: str) -> tuple[str, Set[str]]:
        """Process conditional directives and return filtered source and symbols.

        Preserves a mapping of kept line numbers for later diagnostics.
        """
        lines = source.split('\n')
        output_lines = []
        kept_line_numbers: list[int] = []
        
        # Stack to track nested conditionals: (is_active, has_matched, start_line)
        # is_active: whether we're currently including code
        # has_matched: whether any branch in this if/elif/else chain has matched
        # start_line: 1-based line number of the opening .ifdef/.ifndef
        cond_stack = [(True, False, 0)]
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip().lower()
            

            
            # Check for directives
            if stripped.startswith('.define '):
                if cond_stack[-1][0]:  # only process if active
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        symbol = parts[1].strip().upper()
                        if symbol in self.defined_symbols:
                            col = line.upper().find(symbol)
                            raise PreprocessorError(f"Symbol '{symbol}' already defined", line=i + 1, col=(col + 1) if col != -1 else 1)
                        self.defined_symbols.add(symbol)
                i += 1
                continue
            
            if stripped.startswith('.undef '):
                if cond_stack[-1][0]:  # only process if active
                    parts = line.strip().split(None, 1)
                    if len(parts) >= 2:
                        symbol = parts[1].strip().upper()
                        self.defined_symbols.discard(symbol)
                i += 1
                continue
            
            if stripped.startswith('.ifdef '):
                parts = line.strip().split()
                if len(parts) < 2:
                    raise PreprocessorError("Missing symbol in .ifdef", i + 1)
                symbol = parts[1].strip().upper()
                
                # Only check condition if parent is active
                parent_active = cond_stack[-1][0]
                is_defined = symbol in self.defined_symbols
                is_active = parent_active and is_defined
                cond_stack.append((is_active, is_active, i + 1))
                i += 1
                continue

            if stripped.startswith('.ifndef '):
                parts = line.strip().split()
                if len(parts) < 2:
                    raise PreprocessorError("Missing symbol in .ifndef", i + 1)
                symbol = parts[1].strip().upper()

                # Only check condition if parent is active
                parent_active = cond_stack[-1][0]
                is_defined = symbol in self.defined_symbols
                is_active = parent_active and not is_defined
                cond_stack.append((is_active, is_active, i + 1))
                i += 1
                continue
            
            if stripped == '.else':
                if len(cond_stack) <= 1:
                    raise PreprocessorError("Unexpected .else without .ifdef/.ifndef", i + 1)
                
                current_active, has_matched, start_line = cond_stack.pop()
                parent_active = cond_stack[-1][0] if cond_stack else True

                # .else activates only if parent is active and no branch has matched yet
                new_active = parent_active and not has_matched
                cond_stack.append((new_active, has_matched or new_active, start_line))
                i += 1
                continue
            
            if stripped == '.endif':
                if len(cond_stack) <= 1:
                    raise PreprocessorError("Unexpected .endif without .ifdef/.ifndef", i + 1)
                cond_stack.pop()
                i += 1
                continue
            
            # Regular line - include if active
            if cond_stack[-1][0]:
                output_lines.append(line)
                kept_line_numbers.append(i+1)
            
            i += 1
        
        # Check for unclosed conditionals
        if len(cond_stack) > 1:
            open_line = cond_stack[-1][2]
            raise PreprocessorError("Unclosed .ifdef/.ifndef (missing .endif)", line=open_line, col=1)
        
        # Store last kept line mapping so callers can relate processed lines back to
        # the original file line numbers.
        self.last_kept_line_numbers = kept_line_numbers
        return '\n'.join(output_lines), self.defined_symbols
