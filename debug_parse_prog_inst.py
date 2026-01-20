#!/usr/bin/env python3
"""Debug parse_program with instrumentation"""

from parser import Parser
from token_types import *
import sys

code = """
func byte add_one(byte x)
    return x + 1
end

proc main()
    byte result = add_one(5)
end
"""

class DebugParser(Parser):
    def parse_program(self):
        decls = []
        procs = []

        # FIRST PASS: Collect struct names
        temp_pos = self.pos
        temp_cur = self.cur
        iteration = 0
        while self.cur.type != TOK_EOF:
            if self.cur.type == TOK_KEYWORD and self.cur.value == "STRUCT":
                self.advance()
                if self.cur.type == TOK_IDENT:
                    self.struct_names.add(self.cur.value.upper())
                while self.cur.type != TOK_EOF and not (self.cur.type == TOK_KEYWORD and self.cur.value == "END"):
                    self.advance()
                if self.cur.type == TOK_KEYWORD:
                    self.advance()
            else:
                self.advance()
            iteration += 1

        print(f"First pass completed: {iteration} iterations, advanced from {temp_pos} to {self.pos}")

        # RESET to beginning
        self.pos = temp_pos
        if self.pos < len(self.tokens):
            self.cur = self.tokens[self.pos]

        print(f"After reset: pos={self.pos}, cur.type={self.cur.type}, cur.value={self.cur.value}")

        # SECOND PASS: Parse everything
        iteration = 0
        while self.cur.type != TOK_EOF:
            iteration += 1
            print(f"\n  Iteration {iteration}: pos={self.pos}, type={self.cur.type}, value={self.cur.value}")
            
            if self.cur.type == TOK_PREPROC and self.cur.value.upper() == ".SEGMENT":
                print("    -> .SEGMENT directive")
                self.advance()
                if self.cur.type != TOK_STRING:
                    self.error("Expected string after .segment")
                segment_name = self.cur.value
                self.advance()
                from ast_nodes import SegmentDirective
                procs.append(SegmentDirective(segment_name))
            elif self.cur.type == TOK_OP and self.cur.value == ".":
                print("    -> . operator")
                self.advance()
                if self.cur.type == TOK_IDENT:
                    directive = self.cur.value.upper()
                    self.advance()
                    if directive == "INCLUDE":
                        if self.cur.type != TOK_STRING:
                            self.error("Expected string after .include")
                        self.advance()
                    elif directive == "SEGMENT":
                        if self.cur.type != TOK_STRING:
                            self.error("Expected string after .segment")
                        segment_name = self.cur.value
                        self.advance()
                        from ast_nodes import SegmentDirective
                        procs.append(SegmentDirective(segment_name))
                    else:
                        pass
                else:
                    self.error("Expected identifier after '.'")
            elif self.cur.type == TOK_KEYWORD and self.cur.value == "STRUCT":
                print("    -> STRUCT")
                procs.append(self.parse_struct_def())
            elif self.cur.type in (TOK_TYPE, TOK_TYPEMOD):
                print("    -> Declaration")
                decls.append(self.parse_declaration())
            elif self.cur.type == TOK_IDENT and self.cur.value.upper() in self.struct_names:
                print("    -> Struct type declaration")
                decls.append(self.parse_declaration())
            elif self.cur.type == TOK_KEYWORD and self.cur.value == "PROC":
                print("    -> PROC")
                procs.append(self.parse_proc())
            elif self.cur.type == TOK_KEYWORD and self.cur.value == "FUNC":
                print("    -> FUNC - calling parse_func()")
                try:
                    result = self.parse_func()
                    print(f"    <- parse_func() returned, name={result.name}, pos now={self.pos}")
                    procs.append(result)
                except Exception as e:
                    print(f"    <- parse_func() EXCEPTION: {e}")
                    raise
            elif self.cur.type == TOK_IDENT:
                print("    -> Stray ident, skipping")
                self.advance()
            else:
                print(f"    -> ERROR: no condition matched! type={self.cur.type}, value={self.cur.value}")
                self.error("Expected declaration, PROC, FUNC, or STRUCT")

        print(f"\nSecond pass completed: {iteration} iterations")
        from ast_nodes import Program
        program = Program(decls, procs)
        program.debug = {
            "stmt_src": self.stmt_src,
            "local_decl_src": self.local_decl_src,
            "global_decl_src": self.global_decl_src,
            "proc_src": self.proc_src,
            "source_lines": self.source_lines,
            "filename": self.filename,
        }
        return program

parser = DebugParser(code, "test.zap")
try:
    program = parser.parse_program()
    print(f"\n✓ Success!")
except Exception as e:
    print(f"\n✗ Error: {e}")
