
from typing import NoReturn, Optional, Callable, Union, cast
from ast_nodes import Program
from ast_nodes import StructDef
from ast_nodes import EnumDecl
from ast_nodes import ProcDecl
from ast_nodes import Parameter
from ast_nodes import Parameter
from ast_nodes import Declaration
from ast_nodes import Declarator
from ast_nodes import FuncDecl
from ast_nodes import Parameter
from ast_nodes import Parameter
from ast_nodes import Declaration
from ast_nodes import Declarator
from ast_nodes import Parameter
from ast_nodes import Declaration
from ast_nodes import Declarator
from ast_nodes import Declarator
from ast_nodes import DerefExpr, FieldAccess, Identifier, SubscriptExpr
from ast_nodes import AssignStmt, CallStmt
from ast_nodes import DerefExpr, FieldAccess, Identifier, SubscriptExpr
from ast_nodes import BinOp
from ast_nodes import BinOp
from ast_nodes import BinOp
from ast_nodes import BinOp
from ast_nodes import BinOp
from ast_nodes import IfStmt
from ast_nodes import IfStmt
from ast_nodes import IfStmt
from ast_nodes import IfStmt
from ast_nodes import WhileStmt
from ast_nodes import ForStmt
from ast_nodes import AsmBlock, AssignStmt, BreakStmt, CallStmt, ContinueStmt, ForStmt, IfStmt, IncbinDirective, ReturnStmt, SegmentDirective, ErrorDirective, WarningDirective, InfoDirective, WhileStmt, SwitchStmt, SwitchCase
from tokenizer import Tokenizer, Token
from token_types import *
from ast_nodes import *
from errors import SyntaxError

class Parser:
    def __init__(self, source: str, filename: str | None = None) -> None:
        self.filename: str = filename or "<input.act>"
        # Remove BOM if present (can be \ufeff or UTF-8 BOM misinterpreted as 'ï»¿')
        if source.startswith('\ufeff'):
            source = source[1:]
        elif source.startswith('ï»¿'):
            # UTF-8 BOM misinterpreted by non-UTF-8-aware decoder
            source = source[3:]
        self.source: str = source
        self.source_lines: list[str] = source.splitlines()
        self.tok = Tokenizer(source)
        self.tok.tokenize()
        self.tokens: list[Token] = self.tok._getTokens()        
        # Current token - always maintain a Token (use EOF token when empty)
        self.cur: Token = self.tokens[0] if self.tokens else Token(TOK_EOF, "", 1, 1)
        self.pos = 0
        # Debug maps
        self.current_proc_name: str | None = None
        # Statement source: id(node) -> (filename, line, col, line_text)
        self.stmt_src: dict[int, tuple[str, int, int, str]] = {}
        # Declaration source: (filename, line, col, line_text)
        self.local_decl_src: dict[tuple[str, str], tuple[str, int, int, str]] = {}
        self.global_decl_src: dict[str, tuple[str, int, int, str]] = {}
        # Proc/Func source: name -> (filename, line, col, line_text)
        self.proc_src: dict[str, tuple[str, int, int, str]] = {}
        self.param_src: dict[tuple[str, str], tuple[str, int, str]] = {}
        # Struct names for type checking in parse_declaration
        self.struct_names: set[str] = set()

    def _readable_token(self, ttype: str, tvalue: Optional[str] = None) -> str:
        """Return a human-readable description for a token type/value.

        The mapping contains either a string or a callable that accepts an optional
        token value and returns a string. Type annotations are explicit to avoid
        Pylance errors where the inferred type could be "object".
        """
        mapping: dict[str, Union[str, Callable[[Optional[str]], str]]] = {
            TOK_IDENT: "identifier",
            TOK_NUMBER: "number",
            TOK_STRING: "string",
            TOK_KEYWORD: (lambda v: f"keyword '{v}'" if v else "keyword"),
            TOK_TYPE: (lambda v: f"type '{v}'" if v else "type"),
            TOK_TYPEMOD: "type modifier",
            TOK_PTR: "pointer '^'",
            TOK_DELIM: "delimiter",
            TOK_EQU: "'='",
            TOK_OP: (lambda v: f"'{v}'" if v else "operator"),
            TOK_AT: "'@'",
            TOK_EOF: "end of file",
            TOK_SQB: "square brackets '[]'",
            TOK_PREPROC: "preprocessor directive",
            TOK_ASM_BLOCK: "assembly block",
            TOK_DECLMOD: "declaration modifier",
            TOK_LBRACE: "'('",
            TOK_RBRACE: "')'",
            TOK_LCURLY: "'{'",
            TOK_RCURLY: "'}'",
        }
        val: Optional[Union[str, Callable[[Optional[str]], str]]] = mapping.get(ttype)
        if val is None:
            return ttype
        if isinstance(val, str):
            return val
        # At this point val must be a callable; cast it for the type checker
        return cast(Callable[[Optional[str]], str], val)(tvalue)

    def advance(self) -> None:
        self.pos += 1
        if self.pos < len(self.tokens):
            self.cur: Token = self.tokens[self.pos]
        else:
            self.cur = Token(TOK_EOF, "", self.cur.line, self.cur.col)

    def _peek_next(self) -> Token | None:
        """Peek at the token after the current one without advancing"""
        next_pos: int = self.pos + 1
        if next_pos < len(self.tokens):
            return self.tokens[next_pos]
        return None

    def expect(self, kind, value=None) -> None:
        if self.cur.type != kind:
            expected = self._readable_token(kind, value)
            got = self._readable_token(self.cur.type, self.cur.value)
            raise SyntaxError(
                f'Expected {expected}, got {got}',
                line=self.cur.line,
                col=self.cur.col,
            )
        if value is not None and self.cur.value != value:
            raise SyntaxError(
                f"Expected '{value}', got '{self.cur.value}'",
                line=self.cur.line,
                col=self.cur.col,
            )
        self.advance()

    def error(self, msg) -> NoReturn:
        raise SyntaxError(
            msg,
            line=self.cur.line,
            col=self.cur.col
        )


    def parse_program(self) -> Program:
        decls = []
        procs = []

        # FIRST PASS: Collect struct names
        # This allows us to recognize struct names as types in declarations
        temp_pos: int = self.pos
        temp_cur: Token = self.cur
        while self.cur.type != TOK_EOF:
            if self.cur.type == TOK_KEYWORD and self.cur.value == "STRUCT":
                self.advance()  # skip "struct"
                if self.cur.type == TOK_IDENT:
                    self.struct_names.add(self.cur.value.upper())
                # Skip to end of struct
                while self.cur.type != TOK_EOF and not (self.cur.type == TOK_KEYWORD and self.cur.value == "END"):
                    self.advance()
                if self.cur.type == TOK_KEYWORD:
                    self.advance()  # skip "end"
            elif self.cur.type == TOK_KEYWORD and self.cur.value == "ENUM":
                # Collect enum name for first-pass recognition (END-style enums)
                self.advance()  # skip "enum"
                # Optional base type (byte/word)
                if self.cur.type == TOK_TYPE:
                    self.advance()
                if self.cur.type == TOK_IDENT:
                    self.struct_names.add(self.cur.value.upper())
                # Skip to closing 'END'
                while self.cur.type != TOK_EOF and not (self.cur.type == TOK_KEYWORD and self.cur.value == "END"):
                    self.advance()
                if self.cur.type == TOK_KEYWORD and self.cur.value == "END":
                    self.advance()
            else:
                self.advance()
        
        # RESET to beginning
        self.pos: int = temp_pos
        if self.pos < len(self.tokens):
            self.cur: Token = self.tokens[self.pos]

        # SECOND PASS: Parse everything
        while self.cur.type != TOK_EOF:
            if self.cur.type == TOK_PREPROC and self.cur.value.upper() == ".ERROR":
                # Parse .error directive at top level
                self.advance()
                if self.cur.type != TOK_STRING:
                    self.error("Expected string after .error")
                msg: str = self.cur.value
                self.advance()
                procs.append(ErrorDirective(msg, self.cur.line, self.cur.col))
            elif self.cur.type == TOK_PREPROC and self.cur.value.upper() == ".WARNING":
                # Parse .warning directive at top level
                self.advance()
                if self.cur.type != TOK_STRING:
                    self.error("Expected string after .warning")
                msg: str = self.cur.value
                self.advance()
                procs.append(WarningDirective(msg, self.cur.line, self.cur.col))
            elif self.cur.type == TOK_PREPROC and self.cur.value.upper() == ".INFO":
                # Parse .info directive at top level
                self.advance()
                if self.cur.type != TOK_STRING:
                    self.error("Expected string after .info")
                msg: str = self.cur.value
                self.advance()
                procs.append(InfoDirective(msg, self.cur.line, self.cur.col))
            elif self.cur.type == TOK_OP and self.cur.value == ".":
                # Handle . followed by IDENT (preprocessor directive like .include)
                self.advance()
                if self.cur.type == TOK_IDENT:
                    directive: str = self.cur.value.upper()
                    self.advance()
                    if directive == "INCLUDE":
                        if self.cur.type != TOK_STRING:
                            self.error("Expected string after .include")
                        # Skip .include directives for now
                        self.advance()
                    elif directive == "ERROR":
                        if self.cur.type != TOK_STRING:
                            self.error("Expected string after .error")
                        msg: str = self.cur.value
                        self.advance()
                        procs.append(ErrorDirective(msg, self.cur.line, self.cur.col))
                    elif directive == "WARNING":
                        if self.cur.type != TOK_STRING:
                            self.error("Expected string after .warning")
                        msg: str = self.cur.value
                        self.advance()
                        procs.append(WarningDirective(msg, self.cur.line, self.cur.col))
                    elif directive == "INFO":
                        if self.cur.type != TOK_STRING:
                            self.error("Expected string after .info")
                        msg: str = self.cur.value
                        self.advance()
                        procs.append(InfoDirective(msg, self.cur.line, self.cur.col))
                    else:
                        # Unknown directive: try to skip optional argument (string or identifier)
                        if self.cur.type == TOK_STRING:
                            # skip module/include style string argument
                            self.advance()
                        # otherwise ignore and continue
                        pass
                else:
                    self.error("Expected identifier after '.'")
            elif self.cur.type == TOK_KEYWORD and self.cur.value == "STRUCT":
                procs.append(self.parse_struct_def())
            elif self.cur.type == TOK_KEYWORD and self.cur.value == "ENUM":
                decls.append(self.parse_enum())
            elif self.cur.type in (TOK_TYPE, TOK_TYPEMOD):
                decls.append(self.parse_declaration())
            elif self.cur.type == TOK_IDENT and self.cur.value.upper() in self.struct_names:
                # Struct type declaration at top level
                decls.append(self.parse_declaration())
            elif self.cur.type == TOK_KEYWORD and self.cur.value == "PROC":
                procs.append(self.parse_proc())
            elif self.cur.type == TOK_KEYWORD and self.cur.value == "FUNC":
                procs.append(self.parse_func())
            elif self.cur.type == TOK_IDENT:
                # Skip stray identifiers (like BOM misinterpreted as 'Ï')
                self.advance()
            else:
                self.error("Expected declaration, PROC, FUNC, or STRUCT")
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


    def parse_struct_def(self) -> StructDef:
        """Parse struct definition: struct Name field_list end"""
        start_line: int = self.cur.line
        start_col: int = self.cur.col
        self.expect(TOK_KEYWORD, "STRUCT")
        
        struct_name: str = self.cur.value
        self.expect(TOK_IDENT)

        # Optional struct-level declaration modifiers: #PORT #RD #WR
        struct_is_port: bool = False
        struct_port_rd: Optional[bool] = None
        struct_port_wr: Optional[bool] = None
        while self.cur.type == TOK_DECLMOD:
            val: str = self.cur.value.upper()
            if val == 'PORT':
                struct_is_port = True
            elif val == 'RD':
                struct_port_rd = True
            elif val == 'WR':
                struct_port_wr = True
            else:
                self.error(f"Unsupported struct modifier '{val}'")
            self.advance()

        fields = []
        seen_names: set[str] = set()
        
        # Parse field list until END
        while not (self.cur.type == TOK_KEYWORD and self.cur.value == "END"):
            # Parse: [^] type IDENT [dimensions] [ address_spec ] [decl_modifiers]
            # Check for pointer prefix first
            is_pointer = False
            if self.cur.type == TOK_PTR or (self.cur.type == TOK_OP and self.cur.value == "^"):
                is_pointer = True
                self.advance()
            
            # type (either built-in like byte/word, or a struct name)
            if self.cur.type == TOK_TYPE:
                type_name: str = self.cur.value
                type_tok: Token = self.cur
                self.advance()
            elif self.cur.type == TOK_IDENT and self.cur.value.upper() in self.struct_names:
                type_name: str = self.cur.value
                type_tok: Token = self.cur
                self.advance()
            else:
                self.error(f"Expected type in struct field, got {self._readable_token(self.cur.type, self.cur.value)}")
            
            field_type = TypeNode(type_name, is_pointer)
            
            # field name
            field_name: str = self.cur.value
            if field_name.startswith('_'):
                self.error("Field names cannot start with underscore")
            self.expect(TOK_IDENT)
            
            if field_name in seen_names:
                raise SyntaxError(f"Duplicate field '{field_name}' in struct '{struct_name}'", 
                                line=self.cur.line, col=self.cur.col)
            seen_names.add(field_name)
            
            # Parse optional array dimensions
            array_sizes = None
            if self.cur.type == TOK_OP and self.cur.value == "[":
                array_sizes = []
                while self.cur.type == TOK_OP and self.cur.value == "[":
                    self.advance()
                    # Parse array size expression
                    size_expr = self.parse_expr()
                    array_sizes.append(size_expr)
                    self.expect(TOK_OP, "]")
            
            # Parse optional address spec
            field_addr = None
            if self.cur.type == TOK_AT:
                self.advance()
                field_addr = self.parse_expr()

            # Optional trailing modifiers on field: #PORT, #RD, #WR
            field_is_port = False
            field_port_rd: Optional[bool] = None
            field_port_wr: Optional[bool] = None
            while self.cur.type == TOK_DECLMOD:
                val: str = self.cur.value.upper()
                if val == 'PORT':
                    field_is_port = True
                elif val == 'RD':
                    field_port_rd = True
                elif val == 'WR':
                    field_port_wr = True
                else:
                    self.error(f"Unsupported field modifier '{val}'")
                self.advance()

            fields.append(StructField(field_type, field_name, field_addr, array_sizes,
                                      is_port=field_is_port, port_rd=field_port_rd, port_wr=field_port_wr))
        
        self.expect(TOK_KEYWORD, "END")
        return StructDef(struct_name, fields, is_port=struct_is_port, port_rd=struct_port_rd, port_wr=struct_port_wr, line=start_line, col=start_col)

    def parse_enum(self) -> EnumDecl:
        """Parse enum declaration (END-style only):
           enum [type] Name
               item [= value]
               [,...]
           END
        """
        start_line: int = self.cur.line
        start_col: int = self.cur.col
        self.expect(TOK_KEYWORD, "ENUM")
        # optional base type
        base = 'byte'
        if self.cur.type == TOK_TYPE:
            base: str = self.cur.value
            self.advance()
        name: str = self.cur.value
        self.expect(TOK_IDENT)
        items = []
        # END-style enum, parse until END
        while not (self.cur.type == TOK_KEYWORD and self.cur.value == "END"):
            item_line: int = self.cur.line
            item_col: int = self.cur.col
            if self.cur.type != TOK_IDENT:
                self.error("Expected enum member name or END")
            item_name: str = self.cur.value
            if item_name.startswith('_'):
                self.error("Enum member names cannot start with underscore")
            self.expect(TOK_IDENT)
            item_value = None
            if self.cur.type == TOK_EQU:
                self.advance()
                item_value = self.parse_expr()
            items.append(EnumItem(item_name, item_value, line=item_line, col=item_col))
            # optional trailing comma
            if self.cur.type == TOK_DELIM and self.cur.value == ',':
                self.advance()
                continue
        self.expect(TOK_KEYWORD, "END")
        return EnumDecl(name, base, items, line=start_line, col=start_col)


    def parse_proc(self) -> ProcDecl:
        start_line: int = self.cur.line
        start_col: int = self.cur.col
        self.expect(TOK_KEYWORD, "PROC")
        name: str = self.cur.value
        self.expect(TOK_IDENT)

        # record proc source info
        line_text: str = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.proc_src[name] = (self.filename, start_line, start_col, line_text)
        self.current_proc_name = name

        locals = []
        body = []
        params = []
        seen_names: set[str] = set()

        self.expect(TOK_LBRACE)
        # parse parameter list
        if self.cur.type != TOK_RBRACE:
            p: Parameter = self.parse_parameter()
            if p.name in seen_names:
                raise SyntaxError(f"Duplicate parameter '{p.name}' in procedure", line=p.line, col=p.col)
            seen_names.add(p.name)
            params.append(p)
            while self.cur.type == TOK_DELIM and self.cur.value == ',':
                self.advance()
                p: Parameter = self.parse_parameter()
                if p.name in seen_names:
                    raise SyntaxError(f"Duplicate parameter '{p.name}' in procedure", line=p.line, col=p.col)
                seen_names.add(p.name)
                params.append(p)
        self.expect(TOK_RBRACE)

        # Optional declaration modifiers: #KEEP, #NOEXPORT, #EXPORT
        keep = False
        noexport = False
        export = False
        while self.cur.type == TOK_DECLMOD:
            val: str = self.cur.value.upper()
            if val == 'KEEP':
                keep = True
            elif val == 'NOEXPORT':
                noexport = True
            elif val == 'EXPORT':
                export = True
            else:
                self.error(f"Unsupported declaration modifier '{val}'")
            self.advance()

        def _is_declaration_start() -> bool:
            """Check if current position starts a declaration"""
            if self.cur.type in (TOK_TYPE, TOK_TYPEMOD):
                return True
            if self.cur.type == TOK_PTR or (self.cur.type == TOK_OP and self.cur.value == "^"):
                return True
            # For struct types, check if next token is an identifier (variable name)
            # NOT a dot (which would indicate field access like node.data)
            if self.cur.type == TOK_IDENT and self.cur.value.upper() in self.struct_names:
                # Look ahead to see if next token is an identifier or [ or @ or = or ^ (pointer)
                # If it's a dot, this is a statement, not a declaration
                next_tok: Token | None = self.tokens[self.pos+1] if self.pos+1 < len(self.tokens) else None
                if next_tok and (next_tok.type == TOK_IDENT or 
                                next_tok.type == TOK_PTR or
                                next_tok.type in (TOK_SQB, TOK_AT) or
                                (next_tok.type == TOK_OP and next_tok.value in ("[", "@", "^")) or
                                next_tok.type == TOK_EQU):
                    return True
                # If next token is dot or anything else, it's not a declaration
                return False
            return False

        while _is_declaration_start():
            decl: Declaration = self.parse_declaration()
            for d in decl.declarators:
                if d.name in seen_names:
                    raise SyntaxError(f"Duplicate local '{d.name}' in procedure", line=d.line, col=d.col)
                seen_names.add(d.name)
            locals.append(decl)

        while not (self.cur.type == TOK_KEYWORD and self.cur.value == "END"):
            body.append(self.parse_stmt())

        # consume END keyword
        self.expect(TOK_KEYWORD, "END")

        self.current_proc_name = None
        return ProcDecl(name, params, locals, body, keep=keep, noexport=noexport, export=export)

    def parse_func(self) -> FuncDecl:
        start_line: int = self.cur.line
        start_col: int = self.cur.col
        self.expect(TOK_KEYWORD, "FUNC")
        
        # return type: can be TYPE (byte/word) or STRUCT_NAME
        ret_type_tok: Token = self.cur
        if self.cur.type == TOK_TYPE:
            self.advance()
            ret_type_base: str = ret_type_tok.value
        elif self.cur.type == TOK_IDENT and self.cur.value.upper() in self.struct_names:
            # Struct return type
            ret_type_base: str = self.cur.value
            self.advance()
        else:
            self.error(f"Expected type for function return, got {self._readable_token(self.cur.type, self.cur.value)}")
        
        ret_is_pointer = False
        if self.cur.type == TOK_PTR or (self.cur.type == TOK_OP and self.cur.value == "^"):
            ret_is_pointer = True
            self.advance()
        
        name: str = self.cur.value
        self.expect(TOK_IDENT)
        
        locals = []
        body = []
        params = []
        seen_names: set[str] = set()
        
        self.expect(TOK_LBRACE)
        # parse parameter list
        if self.cur.type != TOK_RBRACE:
            p: Parameter = self.parse_parameter()
            if p.name in seen_names:
                raise SyntaxError(f"Duplicate parameter '{p.name}' in function", line=p.line, col=p.col)
            seen_names.add(p.name)
            params.append(p)
            while self.cur.type == TOK_DELIM and self.cur.value == ',':
                self.advance()
                p: Parameter = self.parse_parameter()
                if p.name in seen_names:
                    raise SyntaxError(f"Duplicate parameter '{p.name}' in function", line=p.line, col=p.col)
                seen_names.add(p.name)
                params.append(p)
        self.expect(TOK_RBRACE)
        
        # Optional declaration modifiers: #KEEP, #NOEXPORT, #EXPORT
        keep = False
        noexport = False
        export = False
        while self.cur.type == TOK_DECLMOD:
            val: str = self.cur.value.upper()
            if val == 'KEEP':
                keep = True
            elif val == 'NOEXPORT':
                noexport = True
            elif val == 'EXPORT':
                export = True
            else:
                self.error(f"Unsupported declaration modifier '{val}'")
            self.advance()
        
        while self.cur.type in (TOK_TYPE, TOK_TYPEMOD) or (self.cur.type == TOK_IDENT and self.cur.value.upper() in self.struct_names):
            decl: Declaration = self.parse_declaration()
            for d in decl.declarators:
                if d.name in seen_names:
                    raise SyntaxError(f"Duplicate local '{d.name}' in function", line=d.line, col=d.col)
                seen_names.add(d.name)
            locals.append(decl)
        
        while not (self.cur.type == TOK_KEYWORD and self.cur.value == "END"):
            body.append(self.parse_stmt())
        
        # consume END keyword
        self.expect(TOK_KEYWORD, "END")

        line_text: str = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.proc_src[name] = (self.filename, start_line, start_col, line_text)

        return FuncDecl(name, TypeNode(ret_type_base, ret_is_pointer), params, locals, body, keep=keep, noexport=noexport, export=export)

    def parse_parameter(self) -> Parameter:
        # Note: the 'type' token can be TOK_TYPE (byte/word) or a STRUCT_NAME, optionally const
        is_const = False
        if self.cur.type == TOK_TYPEMOD and self.cur.value.upper() == "CONST":
            is_const = True
            self.advance()
        
        type_tok: Token = self.cur
        if self.cur.type == TOK_TYPE:
            self.advance()
            type_base: str = type_tok.value
        elif self.cur.type == TOK_IDENT and self.cur.value.upper() in self.struct_names:
            # Struct parameter type
            type_base: str = self.cur.value
            self.advance()
        else:
            self.error(f"Expected type for parameter, got {self._readable_token(self.cur.type, self.cur.value)}")
        
        is_pointer = False
        if self.cur.type == TOK_PTR or (self.cur.type == TOK_OP and self.cur.value == "^"):
            is_pointer = True
            self.advance()
        
        name: str = self.cur.value
        name_line: int = self.cur.line
        name_col: int = self.cur.col
        self.expect(TOK_IDENT)
        
        is_array = False
        if self.cur.type == TOK_OP and self.cur.value == '[':
            self.advance()
            self.expect(TOK_OP, ']')
            is_array = True
        
        # Parse optional default value: = expression
        default_value = None
        if self.cur.type == TOK_EQU:
            self.advance()
            default_value = self.parse_expr()
        
        return Parameter(TypeNode(type_base, is_pointer), name, is_array, default_value, name_line, name_col)

    def parse_init_value(self):
        """Parse an initializer value: either a nested list { ... } or an expression."""
        if self.cur.type == TOK_LCURLY:
            # Nested list initializer
            self.advance()
            values = []
            if self.cur.type != TOK_RCURLY:
                values.append(self.parse_init_value())
                while self.cur.type == TOK_DELIM and self.cur.value == ',':
                    self.advance()
                    # Allow trailing comma
                    if self.cur.type == TOK_RCURLY:
                        break
                    values.append(self.parse_init_value())
            self.expect(TOK_RCURLY)
            return ListInit(values)
        else:
            # Regular expression
            return self.parse_expr()

    def parse_declaration(self) -> Declaration:
        is_const = False
        is_static = False
        is_port = False
        port_rd = False
        port_wr = False

        # CONST or STATIC prefix (PORT is now a declaration modifier #PORT)
        while self.cur.type == TOK_TYPEMOD:
            if self.cur.value.upper() == "CONST":
                is_const = True
            elif self.cur.value.upper() == "STATIC":
                is_static = True
            else:
                self.error("Unsupported type modifier")
            self.advance()

        # Check for pointer prefix - two possible orders:
        # 1. ^type name (pointer prefix first - used in structs and procs)
        # 2. type ^name (pointer suffix after type - global declarations)
        is_pointer = False

        # Try order 1: ^type name
        if self.cur.type == TOK_PTR or (self.cur.type == TOK_OP and self.cur.value == "^"):
            is_pointer = True
            self.advance()

        # type (built-in or struct name)
        type_tok: Token = self.cur
        if self.cur.type == TOK_TYPE:
            # Built-in type (byte, word)
            self.expect(TOK_TYPE)
        elif self.cur.type == TOK_IDENT and self.cur.value.upper() in self.struct_names:
            # Struct type
            self.advance()
        else:
            self.expect(TOK_TYPE)

        # Check for order 2: type ^name (pointer suffix after type)
        if not is_pointer and (self.cur.type == TOK_PTR or (self.cur.type == TOK_OP and self.cur.value == "^")):
            is_pointer = True
            self.advance()

        def _is_sqb(val=None):
            # Accept either dedicated square-bracket tokens or OP tokens carrying '[' or ']'
            if self.cur.type == TOK_SQB:
                return val is None or self.cur.value == val
            if self.cur.type == TOK_OP and self.cur.value in ("[", "]"):
                return val is None or self.cur.value == val
            return False

        def _expect_sqb(val) -> None:
            if not _is_sqb(val):
                self.error(f"Expected '{val}'")
            self.advance()

        def parse_declarator() -> Declarator:
            # ident
            name: str = self.cur.value
            if name.startswith('_'):
                self.error("Variable names cannot start with underscore")
            decl_line: int = self.cur.line
            decl_col: int = self.cur.col
            self.expect(TOK_IDENT)

            # Parse array dimensions (may have multiple [size] clauses)
            array_sizes = []
            while _is_sqb("["):
                # [expr] or []
                self.advance()
                if not _is_sqb("]"):
                    array_sizes.append(self.parse_expr())
                else:
                    # [] → infer size from initializer
                    array_sizes.append(IntLiteral(-1))
                _expect_sqb("]")  # closing ]

            # For backward compatibility, keep array_size for single dimension
            array_size = array_sizes[0] if len(array_sizes) == 1 else None

            init = None
            address = None

            # init / address (any order, at most once each)
            while True:
                if self.cur.type == TOK_EQU and init is None:
                    self.advance()

                    # list initializer { ... }
                    if self.cur.type == TOK_LCURLY:
                        self.advance()
                        values = []
                        if self.cur.type != TOK_RCURLY:
                            values.append(self.parse_init_value())
                            while self.cur.type == TOK_DELIM and self.cur.value == ',':
                                self.advance()
                                # Allow trailing comma
                                if self.cur.type == TOK_RCURLY:
                                    break
                                values.append(self.parse_init_value())
                        self.expect(TOK_RCURLY)
                        init = ListInit(values)
                        continue

                    # string initializer
                    if self.cur.type == TOK_STRING:
                        val: str = self.cur.value
                        self.advance()
                        init = StringInit(val)
                        continue

                    init = ExprInit(self.parse_expr())
                    continue

                if self.cur.type == TOK_AT and address is None:
                    self.advance()
                    address = self.parse_expr()
                    continue
                break

            # record declaration source
            line_text: str = self.source_lines[decl_line-1] if 1 <= decl_line <= len(self.source_lines) else ""
            if self.current_proc_name:
                self.local_decl_src[(self.current_proc_name, name)] = (self.filename, decl_line, decl_col, line_text)
            else:
                self.global_decl_src[name] = (self.filename, decl_line, decl_col, line_text)

            # Create Declarator with multi-dimensional support
            return Declarator(
                name=name,
                array_size=array_size,
                address=address,
                initializer=init,
                array_sizes=array_sizes if array_sizes else None,
                line=decl_line,
                col=decl_col,
                is_static=is_static
            )

        declarators: list[Declarator] = [parse_declarator()]

        while self.cur.type == TOK_DELIM and self.cur.value == ',':
            self.advance()
            declarators.append(parse_declarator())

        # Optional trailing declaration modifiers: #KEEP, #NOEXPORT, #EXPORT
        keep = False
        noexport = False
        export = False
        while self.cur.type == TOK_DECLMOD:
            val: str = self.cur.value.upper()
            if val == 'KEEP':
                keep = True
            elif val == 'NOEXPORT':
                noexport = True
            elif val == 'EXPORT':
                export = True
            elif val == 'PORT':
                is_port = True
            elif val == 'RD':
                port_rd = True
            elif val == 'WR':
                port_wr = True
            else:
                self.error(f"Unsupported declaration modifier '{val}'")
            self.advance()

        return Declaration(
            is_const=is_const,
            type=TypeNode(type_tok.value, is_pointer),
            declarators=declarators,
            is_static=is_static,
            is_port=is_port,
            port_rd=port_rd,
            port_wr=port_wr,
            keep=keep,
            noexport=noexport,
            export=export,
        )

        # Check for pointer prefix - two possible orders:
        # 1. ^type name (pointer prefix first - used in structs and procs)
        # 2. type ^name (pointer suffix after type - global declarations)
        is_pointer = False
        
        # Try order 1: ^type name
        if self.cur.type == TOK_PTR or (self.cur.type == TOK_OP and self.cur.value == "^"):
            is_pointer = True
            self.advance()

        # type (built-in or struct name)
        type_tok = self.cur
        if self.cur.type == TOK_TYPE:
            # Built-in type (byte, word)
            self.expect(TOK_TYPE)
        elif self.cur.type == TOK_IDENT and self.cur.value.upper() in self.struct_names:
            # Struct type
            self.advance()
        else:
            self.expect(TOK_TYPE)
        
        # Check for order 2: type ^name (pointer suffix after type)
        if not is_pointer and (self.cur.type == TOK_PTR or (self.cur.type == TOK_OP and self.cur.value == "^")):
            is_pointer = True
            self.advance()

        def _is_sqb(val=None):
            # Accept either dedicated square-bracket tokens or OP tokens carrying '[' or ']'
            if self.cur.type == TOK_SQB:
                return val is None or self.cur.value == val
            if self.cur.type == TOK_OP and self.cur.value in ("[", "]"):
                return val is None or self.cur.value == val
            return False

        def _expect_sqb(val):
            if not _is_sqb(val):
                self.error(f"Expected '{val}'")
            self.advance()

        def parse_declarator():
            # ident
            name = self.cur.value
            if name.startswith('_'):
                self.error("Variable names cannot start with underscore")
            decl_line = self.cur.line
            decl_col = self.cur.col
            self.expect(TOK_IDENT)

            # Parse array dimensions (may have multiple [size] clauses)
            array_sizes = []
            while _is_sqb("["):
                # [expr] or []
                self.advance()
                if not _is_sqb("]"):
                    array_sizes.append(self.parse_expr())
                else:
                    # [] → infer size from initializer
                    array_sizes.append(IntLiteral(-1))
                _expect_sqb("]")  # closing ]

            # For backward compatibility, keep array_size for single dimension
            array_size = array_sizes[0] if len(array_sizes) == 1 else None

            init = None
            address = None

            # init / address (any order, at most once each)
            while True:
                if self.cur.type == TOK_EQU and init is None:
                    self.advance()

                    # list initializer { ... }
                    if self.cur.type == TOK_LCURLY:
                        self.advance()
                        values = []
                        if self.cur.type != TOK_RCURLY:
                            values.append(self.parse_init_value())
                            while self.cur.type == TOK_DELIM and self.cur.value == ',':
                                self.advance()
                                # Allow trailing comma
                                if self.cur.type == TOK_RCURLY:
                                    break
                                values.append(self.parse_init_value())
                        self.expect(TOK_RCURLY)
                        init = ListInit(values)
                        continue

                    # string initializer
                    if self.cur.type == TOK_STRING:
                        val = self.cur.value
                        self.advance()
                        init = StringInit(val)
                        continue

                    init = ExprInit(self.parse_expr())
                    continue

                if self.cur.type == TOK_AT and address is None:
                    self.advance()
                    address = self.parse_expr()
                    continue
                break

            # record declaration source
            line_text = self.source_lines[decl_line-1] if 1 <= decl_line <= len(self.source_lines) else ""
            if self.current_proc_name:
                self.local_decl_src[(self.current_proc_name, name)] = (self.filename, decl_line, decl_col, line_text)
            else:
                self.global_decl_src[name] = (self.filename, decl_line, decl_col, line_text)
            
            # Create Declarator with multi-dimensional support
            return Declarator(
                name=name,
                array_size=array_size,
                address=address,
                initializer=init,
                array_sizes=array_sizes if array_sizes else None,
                line=decl_line,
                col=decl_col,
                is_static=is_static
            )

        declarators = [parse_declarator()]

        while self.cur.type == TOK_DELIM and self.cur.value == ',':
            self.advance()
            declarators.append(parse_declarator())

        # Optional trailing declaration modifiers: #KEEP, #NOEXPORT, #EXPORT
        keep = False
        noexport = False
        export = False
        while self.cur.type == TOK_DECLMOD:
            val = self.cur.value.upper()
            if val == 'KEEP':
                keep = True
            elif val == 'NOEXPORT':
                noexport = True
            elif val == 'EXPORT':
                export = True
            else:
                self.error(f"Unsupported declaration modifier '{val}'")
            self.advance()

        return Declaration(
            is_const=is_const,
            type=TypeNode(type_tok.value, is_pointer),
            declarators=declarators,
            is_static=is_static,
            is_port=is_port,
            keep=keep,
            noexport=noexport,
            export=export,
        )


    def parse_lvalue(self) -> Identifier | SubscriptExpr | FieldAccess | DerefExpr:
        if self.cur.type != TOK_IDENT:
            self.error("Expected identifier")

        name_line: int = self.cur.line
        name_col: int = self.cur.col
        node = Identifier(self.cur.value, line=name_line, col=name_col)
        self.advance()

        while True:
            if self.cur.type in (TOK_SQB, TOK_OP) and self.cur.value == "[":
                br_line: int = self.cur.line
                br_col: int = self.cur.col
                self.advance()
                idx = self.parse_expr()
                if self.cur.type in (TOK_SQB, TOK_OP) and self.cur.value == "]":
                    self.advance()
                else:
                    self.error("Expected ']' after subscript")
                node = SubscriptExpr(node, idx, line=br_line, col=br_col)
                continue
            if (self.cur.type == TOK_PTR) or (self.cur.type == TOK_OP and self.cur.value == "^"):
                # Check for ptr^.field pattern BEFORE treating ^ as postfix deref
                # This MUST be checked first because ^ can also be binary XOR operator
                next_tok: Token | None = self._peek_next()
                if next_tok and next_tok.type == TOK_OP and next_tok.value == ".":
                    # This is ptr^.field - consume ^ and '.', then field name
                    ptr_line: int = self.cur.line
                    ptr_col: int = self.cur.col
                    self.advance()  # consume ^
                    dot_line: int = self.cur.line
                    dot_col: int = self.cur.col
                    self.advance()  # consume .
                    if self.cur.type != TOK_IDENT:
                        self.error("Expected field name after '.'")
                    field_line: int = self.cur.line
                    field_col: int = self.cur.col
                    field_name: str = self.cur.value
                    self.advance()
                    node = FieldAccess(DerefExpr(node, line=ptr_line, col=ptr_col), field_name, is_deref=True, line=field_line, col=field_col)
                    continue
                # Also check if this might be binary XOR (a ^ b) rather than postfix deref
                # If next token could start an expression operand on the same line, it's probably XOR
                if next_tok and (next_tok.type in (TOK_IDENT, TOK_NUMBER, TOK_AT) or
                                (next_tok.type == TOK_OP and next_tok.value in ("~", "@", "("))) and \
                   next_tok.line == self.cur.line:
                    # This looks like binary XOR (a ^ b), don't consume the ^
                    break
                # Otherwise, treat as postfix dereference
                deref_line: int = self.cur.line
                deref_col: int = self.cur.col
                self.advance()
                node = DerefExpr(node, line=deref_line, col=deref_col)
                continue
            # Handle field access: obj.field
            if self.cur.type == TOK_OP and self.cur.value == ".":
                dot_line: int = self.cur.line
                dot_col: int = self.cur.col
                self.advance()
                if self.cur.type != TOK_IDENT:
                    self.error("Expected field name after '.'")
                field_line: int = self.cur.line
                field_col: int = self.cur.col
                field_name: str = self.cur.value
                self.advance()
                node = FieldAccess(node, field_name, is_deref=False, line=field_line, col=field_col)
                continue
            # Handle pointer field access: ptr^.field (handled as ptr^ then field)
            break

        return node

    def parse_assign(self) -> CallStmt | AssignStmt:
        start_line: int = self.cur.line
        start_col: int = self.cur.col
        lhs: Identifier | SubscriptExpr | FieldAccess | DerefExpr = self.parse_lvalue()

        # defensive: if after lvalue we see '(', treat as a call statement
        if self.cur.type == TOK_LBRACE:
            if not isinstance(lhs, Identifier):
                self.error("Call target must be identifier")
            # parse args
            self.advance()
            args = []
            if self.cur.type != TOK_RBRACE:
                # Allow empty first argument (skipped)
                if self.cur.type == TOK_DELIM and self.cur.value == ',':
                    args.append(None)
                else:
                    args.append(self.parse_expr())
                while self.cur.type == TOK_DELIM and self.cur.value == ',':
                    self.advance()
                    # Check for empty argument (skipped parameter)
                    if self.cur.type == TOK_RBRACE or (self.cur.type == TOK_DELIM and self.cur.value == ','):
                        args.append(None)
                    else:
                        args.append(self.parse_expr())
            self.expect(TOK_RBRACE)
            return CallStmt(lhs.name, args)

        self.expect(TOK_EQU)

        rhs = self.parse_expr()
        node = AssignStmt(lhs, rhs)
        line_text: str = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.stmt_src[id(node)] = (self.filename, start_line, start_col, line_text)
        return node

    def parse_term(self):
        node = self.parse_factor()
        while self.cur.type == TOK_OP and self.cur.value in ("*", "/", "%"):
            op = BinOp(self.cur.value)
            op_line: int = self.cur.line
            op_col: int = self.cur.col
            self.advance()
            rhs = self.parse_factor()
            node = BinaryExpr(node, op, rhs, line=op_line, col=op_col)
        return node


    def parse_shift(self):
        node = self.parse_add()
        while self.cur.type == TOK_OP and self.cur.value in ("<<", ">>"):
            op = BinOp(self.cur.value)
            op_line: int = self.cur.line
            op_col: int = self.cur.col
            self.advance()
            rhs = self.parse_add()
            node = BinaryExpr(node, op, rhs, line=op_line, col=op_col)
        return node


    def parse_add(self):
        node = self.parse_term()
        while self.cur.type == TOK_OP and self.cur.value in ("+", "-"):
            op = BinOp(self.cur.value)
            op_line: int = self.cur.line
            op_col: int = self.cur.col
            self.advance()
            rhs = self.parse_term()
            node = BinaryExpr(node, op, rhs, line=op_line, col=op_col)
        return node


    def parse_rel(self):
        node = self.parse_shift()
        while self.cur.type == TOK_OP and self.cur.value in (
            "==", "!=", "<", "<=", ">", ">="
        ):
            op = BinOp(self.cur.value)
            op_line: int = self.cur.line
            op_col: int = self.cur.col
            self.advance()
            rhs = self.parse_shift()
            node = BinaryExpr(node, op, rhs, line=op_line, col=op_col)
        return node


    def parse_bitwise_and(self):
        node = self.parse_rel()
        while self.cur.type == TOK_OP and self.cur.value == "&":
            op: BinOp = BinOp.BAND
            op_line: int = self.cur.line
            op_col: int = self.cur.col
            self.advance()
            rhs = self.parse_rel()
            node = BinaryExpr(node, op, rhs, line=op_line, col=op_col)
        return node


    def parse_bitwise_xor(self):
        node = self.parse_bitwise_and()
        while self.cur.type == TOK_OP and self.cur.value == "^":
            op: BinOp = BinOp.BXOR
            op_line: int = self.cur.line
            op_col: int = self.cur.col
            self.advance()
            rhs = self.parse_bitwise_and()
            node = BinaryExpr(node, op, rhs, line=op_line, col=op_col)
        return node


    def parse_bitwise_or(self):
        node = self.parse_bitwise_xor()
        while self.cur.type == TOK_OP and self.cur.value == "|":
            op: BinOp = BinOp.BOR
            op_line: int = self.cur.line
            op_col: int = self.cur.col
            self.advance()
            rhs = self.parse_bitwise_xor()
            node = BinaryExpr(node, op, rhs, line=op_line, col=op_col)
        return node


    def parse_logic_and(self):
        node = self.parse_bitwise_or()
        while self.cur.type == TOK_OP and self.cur.value == "&&":
            op: BinOp = BinOp.LAND
            op_line: int = self.cur.line
            op_col: int = self.cur.col
            self.advance()
            rhs = self.parse_bitwise_or()
            node = BinaryExpr(node, op, rhs, line=op_line, col=op_col)
        return node


    def parse_logic_or(self):
        node = self.parse_logic_and()
        while self.cur.type == TOK_OP and self.cur.value == "||":
            op: BinOp = BinOp.LOR
            op_line: int = self.cur.line
            op_col: int = self.cur.col
            self.advance()
            rhs = self.parse_logic_and()
            node = BinaryExpr(node, op, rhs, line=op_line, col=op_col)
        return node

    def parse_expr(self):
        return self.parse_logic_or()

    def parse_factor(self):
        # Handle unary operators (prefix)
        if self.cur.type == TOK_AT:
            # Address-of operator @expr
            op_line: int = self.cur.line
            op_col: int = self.cur.col
            self.advance()
            operand = self.parse_factor()  # Parse the expression to take address of
            return UnaryExpr(UnOp.ADDROF, operand, line=op_line, col=op_col)
        
        if self.cur.type == TOK_OP and self.cur.value == "~":
            op_line: int = self.cur.line
            op_col: int = self.cur.col
            self.advance()
            operand = self.parse_factor()  # Recursive call for nested unary operators
            return UnaryExpr(UnOp.BNOT, operand, line=op_line, col=op_col)
        
        if self.cur.type == TOK_OP and self.cur.value == "!":
            # Logical NOT operator
            op_line: int = self.cur.line
            op_col: int = self.cur.col
            self.advance()
            operand = self.parse_factor()  # Recursive call for nested unary operators
            return UnaryExpr(UnOp.NOT, operand, line=op_line, col=op_col)
        
        if self.cur.type == TOK_NUMBER:
            val: str = self.cur.value
            num_line: int = self.cur.line
            num_col: int = self.cur.col
            self.advance()
            
            # Check for consecutive character literals: 'a''b' for word values
            # When parsing 'a', check if next token is also 'b' (TOK_NUMBER with value < 256)
            first_val = int(val, 0)
            if (self.cur.type == TOK_NUMBER and 
                0 <= first_val <= 255 and 
                self.pos < len(self.tokens) - 1):
                # Peek at the next number to see if it's also a character literal range
                next_val = int(self.cur.value, 0)
                if 0 <= next_val <= 255:
                    # This looks like 'a''b' - combine into word value
                    # Format: low byte in 'a', high byte in 'b'
                    self.advance()
                    combined_val: int = first_val | (next_val << 8)
                    return IntLiteral(combined_val, line=num_line, col=num_col)
            
            return IntLiteral(first_val, line=num_line, col=num_col)

        if self.cur.type == TOK_IDENT:
            name: str = self.cur.value
            name_line: int = self.cur.line
            name_col: int = self.cur.col
            node = Identifier(name, line=name_line, col=name_col)
            self.advance()

            while True:
                # function call as expression: ident(...)
                if self.cur.type == TOK_LBRACE:
                    # parse argument list
                    self.advance()
                    args = []
                    if self.cur.type != TOK_RBRACE:
                        # Allow empty first argument (skipped)
                        if self.cur.type == TOK_DELIM and self.cur.value == ',':
                            args.append(None)
                        else:
                            args.append(self.parse_expr())
                        while self.cur.type == TOK_DELIM and self.cur.value == ',':
                            self.advance()
                            # Check for empty argument (skipped parameter)
                            if self.cur.type == TOK_RBRACE or (self.cur.type == TOK_DELIM and self.cur.value == ','):
                                args.append(None)
                            else:
                                args.append(self.parse_expr())
                    self.expect(TOK_RBRACE)
                    return CallExpr(name, args, line=name_line, col=name_col)
                if self.cur.type in (TOK_SQB, TOK_OP) and self.cur.value == "[":
                    br_line: int = self.cur.line
                    br_col: int = self.cur.col
                    self.advance()
                    idx = self.parse_expr()
                    if self.cur.type in (TOK_SQB, TOK_OP) and self.cur.value == "]":
                        self.advance()
                    else:
                        self.error("Expected ']' after subscript")
                    node = SubscriptExpr(node, idx, line=br_line, col=br_col)
                    continue
                # IMPORTANT: Check for ptr^.field BEFORE checking for standalone ^
                # This must be checked first because ^ can be consumed as postfix deref
                if self.cur.type == TOK_PTR:
                    next_tok: Token | None = self._peek_next()
                    if next_tok and ((next_tok.type == TOK_OP and next_tok.value in (".", ":")) or (next_tok.type == TOK_DELIM and next_tok.value == ":")):
                        ptr_line: int = self.cur.line
                        ptr_col: int = self.cur.col
                        self.advance()  # consume ^
                        dot_line: int = self.cur.line
                        dot_col: int = self.cur.col
                        self.advance()  # consume '.' or ':'
                        field_line: int = self.cur.line
                        field_col: int = self.cur.col
                        field_name: str = self.cur.value
                        self.expect(TOK_IDENT)
                        node = FieldAccess(DerefExpr(node, line=ptr_line, col=ptr_col), field_name, is_deref=True, line=field_line, col=field_col)
                        continue
                # For caret: only treat as postfix dereference if next token cannot start an expression
                # If it could be an expression (IDENT, NUMBER, LBRACE, etc.), then it's likely binary XOR
                if self.cur.type == TOK_PTR:
                    deref_line: int = self.cur.line
                    deref_col: int = self.cur.col
                    self.advance()
                    node = DerefExpr(node, line=deref_line, col=deref_col)
                    continue
                # Check for caret as postfix dereference
                # Only consume it if the next token is NOT an identifier or number (which would indicate binary XOR)
                if self.cur.type == TOK_OP and self.cur.value == "^":
                    # Look ahead to see if this might be binary XOR
                    next_tok: Token | None = self._peek_next()
                    # If next token is IDENT or NUMBER on the SAME line, it's likely binary XOR
                    # If it's on a different line, it's the start of a new statement, so ^ is postfix deref
                    if next_tok and next_tok.type in (TOK_IDENT, TOK_NUMBER) and next_tok.line == self.cur.line:
                        # This is likely binary XOR (a ^ b), don't consume the ^
                        break
                    # Otherwise treat as postfix dereference
                    deref2_line: int = self.cur.line
                    deref2_col: int = self.cur.col
                    self.advance()
                    node = DerefExpr(node, line=deref2_line, col=deref2_col)
                    continue
                # Field access: obj.field
                if self.cur.type == TOK_OP and self.cur.value == ".":
                    dotline: int = self.cur.line
                    dotcol: int = self.cur.col
                    self.advance()
                    field_line: int = self.cur.line
                    field_col: int = self.cur.col
                    field_name: str = self.cur.value
                    self.expect(TOK_IDENT)
                    node = FieldAccess(node, field_name, is_deref=False, line=field_line, col=field_col)
                    continue
                break
            return node

        if self.cur.type == TOK_LBRACE:
            self.advance()
            node = self.parse_expr()
            self.expect(TOK_RBRACE)
            return node

        self.error(f"Expected expression, got {self._readable_token(self.cur.type, self.cur.value)}")

            
    def parse_if(self) -> IfStmt:
        start_line: int = self.cur.line
        start_col: int = self.cur.col
        self.expect(TOK_KEYWORD, "IF")
        cond = self.parse_expr()
        self.expect(TOK_KEYWORD, "THEN")        
        then_body = []

        while not (
            self.cur.type == TOK_KEYWORD and
            self.cur.value in ("ELSE", "ELSEIF", "ENDIF")
        ):
            then_body.append(self.parse_stmt())

        root_if = IfStmt(cond, then_body, None)
        cur_if: IfStmt = root_if

        # ELSEIF*
        while self.cur.type == TOK_KEYWORD and self.cur.value == "ELSEIF":
            self.advance()
            cond = self.parse_expr()
            self.expect(TOK_KEYWORD, "THEN")

            body = []
            while not (
                self.cur.type == TOK_KEYWORD and
                self.cur.value in ("ELSE", "ELSEIF", "ENDIF")
            ):
                body.append(self.parse_stmt())

            next_if = IfStmt(cond, body, None)
            cur_if.else_body = [next_if]
            cur_if: IfStmt = next_if

        # ELSE
        if self.cur.type == TOK_KEYWORD and self.cur.value == "ELSE":
            self.advance()
            else_body = []
            while not (
                self.cur.type == TOK_KEYWORD and
                self.cur.value == "ENDIF"
            ):
                else_body.append(self.parse_stmt())
            cur_if.else_body = else_body

        self.expect(TOK_KEYWORD, "ENDIF")
        node: IfStmt = root_if
        line_text: str = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.stmt_src[id(node)] = (self.filename, start_line, start_col, line_text)
        return node

    def parse_switch(self) -> SwitchStmt:
        start_line: int = self.cur.line
        start_col: int = self.cur.col
        self.expect(TOK_KEYWORD, "SWITCH")
        expr = self.parse_expr()

        cases: list[SwitchCase] = []
        current_labels: list[Expr] = []
        current_body: list = []
        current_is_default: bool = False
        seen_label: bool = False

        def flush_case() -> None:
            nonlocal current_labels, current_body, current_is_default
            if current_labels or current_body or current_is_default:
                cases.append(SwitchCase(current_labels, current_body, current_is_default))
            current_labels = []
            current_body = []
            current_is_default = False

        while not (self.cur.type == TOK_KEYWORD and self.cur.value == "END"):
            if self.cur.type == TOK_KEYWORD and self.cur.value == "CASE":
                # Start a new case label; flush only if we already started a body
                if current_body:
                    flush_case()
                self.advance()
                current_labels.append(self.parse_expr())
                seen_label = True
                continue

            if self.cur.type == TOK_KEYWORD and self.cur.value == "DEFAULT":
                if current_body:
                    flush_case()
                self.advance()
                current_is_default = True
                seen_label = True
                continue

            if not seen_label:
                self.error("SWITCH requires CASE or DEFAULT before statements")

            current_body.append(self.parse_stmt())

        flush_case()

        if not cases:
            self.error("SWITCH requires at least one CASE or DEFAULT")

        self.expect(TOK_KEYWORD, "END")
        node = SwitchStmt(expr, cases)
        line_text: str = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.stmt_src[id(node)] = (self.filename, start_line, start_col, line_text)
        return node


    def parse_while(self) -> WhileStmt:
        start_line: int = self.cur.line
        start_col: int = self.cur.col
        self.expect(TOK_KEYWORD, "WHILE")
        cond = self.parse_expr()

        body = []
        while not (self.cur.type == TOK_KEYWORD and self.cur.value == "END"):
            body.append(self.parse_stmt())

        self.expect(TOK_KEYWORD, "END")
        node = WhileStmt(cond, body)
        line_text: str = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.stmt_src[id(node)] = (self.filename, start_line, start_col, line_text)
        return node

    def parse_for(self) -> ForStmt:
        start_line: int = self.cur.line
        start_col: int = self.cur.col
        self.expect(TOK_KEYWORD, "FOR")

        # i
        var = Identifier(self.cur.value)
        self.expect(TOK_IDENT)

        self.expect(TOK_EQU)
        start = self.parse_expr()

        self.expect(TOK_KEYWORD, "TO")
        end = self.parse_expr()

        step = None
        if self.cur.type == TOK_KEYWORD and self.cur.value == "STEP":
            self.advance()
            step = self.parse_expr()

        body = []
        while not (self.cur.type == TOK_KEYWORD and self.cur.value == "END"):
            body.append(self.parse_stmt())

        self.expect(TOK_KEYWORD, "END")
        node = ForStmt(var, start, end, step, body)
        line_text: str = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.stmt_src[id(node)] = (self.filename, start_line, start_col, line_text)
        return node


    def parse_stmt(self) -> SegmentDirective | IncbinDirective | AsmBlock | ErrorDirective | WarningDirective | InfoDirective | IfStmt | WhileStmt | ForStmt | SwitchStmt | BreakStmt | ContinueStmt | ReturnStmt | CallStmt | AssignStmt:
        if self.cur.type in (TOK_TYPE, TOK_TYPEMOD):
            self.error("Local variable declarations must be placed before the first statement in a procedure")

        # blokové terminátory NESMÍ být parsovány jako statement
        if self.cur.type == TOK_KEYWORD and self.cur.value in ("END", "ENDIF", "ELSE"):
            self.error(f"Unexpected block terminator {self.cur.value}")

        if self.cur.type == TOK_PREPROC and self.cur.value.upper() == ".ERROR":
            # Parse .error directive in statement context
            self.advance()
            if self.cur.type != TOK_STRING:
                self.error("Expected string after .error")
            msg: str = self.cur.value
            self.advance()
            return ErrorDirective(msg, self.cur.line, self.cur.col)

        if self.cur.type == TOK_PREPROC and self.cur.value.upper() == ".WARNING":
            # Parse .warning directive in statement context
            self.advance()
            if self.cur.type != TOK_STRING:
                self.error("Expected string after .warning")
            msg: str = self.cur.value
            self.advance()
            return WarningDirective(msg, self.cur.line, self.cur.col)

        if self.cur.type == TOK_PREPROC and self.cur.value.upper() == ".INFO":
            # Parse .info directive in statement context
            self.advance()
            if self.cur.type != TOK_STRING:
                self.error("Expected string after .info")
            msg: str = self.cur.value
            self.advance()
            return InfoDirective(msg, self.cur.line, self.cur.col)

        # Handle . followed by IDENT (preprocessor directive like .include)
        if self.cur.type == TOK_OP and self.cur.value == ".":
            self.advance()
            if self.cur.type == TOK_IDENT:
                directive: str = self.cur.value.upper()
                self.advance()
                if directive == "INCLUDE":
                    if self.cur.type != TOK_STRING:
                        self.error("Expected string after .include")
                    # Skip .include directives for now
                    self.advance()
                elif directive == "ERROR":
                    if self.cur.type != TOK_STRING:
                        self.error("Expected string after .error")
                    msg: str = self.cur.value
                    self.advance()
                    return ErrorDirective(msg, self.cur.line, self.cur.col)
                elif directive == "WARNING":
                    if self.cur.type != TOK_STRING:
                        self.error("Expected string after .warning")
                    msg: str = self.cur.value
                    self.advance()
                    return WarningDirective(msg, self.cur.line, self.cur.col)
                elif directive == "INFO":
                    if self.cur.type != TOK_STRING:
                        self.error("Expected string after .info")
                    msg: str = self.cur.value
                    self.advance()
                    return InfoDirective(msg, self.cur.line, self.cur.col)
                else:
                    self.error(f"Unknown directive '.{directive}'")
            else:
                self.error("Expected identifier after '.'")

        if self.cur.type == TOK_KEYWORD:
            if self.cur.value == "ASM":
                self.advance()
                if self.cur.type != TOK_ASM_BLOCK:
                    self.error("Expected ASM block after ASM")
                block_text: str = self.cur.value
                self.advance()
                return AsmBlock(block_text)
            if self.cur.value == "IF":
                return self.parse_if()
            if self.cur.value == "WHILE":
                return self.parse_while()
            if self.cur.value == "FOR":
                return self.parse_for()
            if self.cur.value == "SWITCH":
                return self.parse_switch()
            if self.cur.value == "BREAK":
                self.advance()
                return BreakStmt()
            if self.cur.value == "CONTINUE":
                self.advance()
                return ContinueStmt()
            if self.cur.value == "RETURN":
                self.advance()
                # Expression is optional for PROCs
                expr = None
                if self.cur.type not in (TOK_EOF, TOK_KEYWORD) or (
                    self.cur.type == TOK_KEYWORD and self.cur.value not in ("END", "ELSE", "ELSEIF", "ENDIF")
                ):
                    # There's something after RETURN that looks like an expression
                    if self.cur.type not in (TOK_KEYWORD,):
                        expr = self.parse_expr()
                node = ReturnStmt(expr)
                ret_line: int = self.cur.line
                ret_col: int = self.cur.col
                line_text: str = self.source_lines[ret_line-1] if 1 <= ret_line <= len(self.source_lines) else ""
                self.stmt_src[id(node)] = (self.filename, ret_line, ret_col, line_text)
                return node

        # Call statement: IDENT(...)
        if self.cur.type == TOK_IDENT:
            # peek next token
            nxt: Token | None = self.tokens[self.pos+1] if self.pos+1 < len(self.tokens) else None
            if nxt is not None and nxt.type == TOK_LBRACE:
                start_line: int = self.cur.line
                start_col: int = self.cur.col
                name: str = self.cur.value
                self.advance()
                # parse arg list
                self.expect(TOK_LBRACE)
                args = []
                if self.cur.type != TOK_RBRACE:
                    args.append(self.parse_expr())
                    while self.cur.type == TOK_DELIM and self.cur.value == ',':
                        self.advance()
                        args.append(self.parse_expr())
                self.expect(TOK_RBRACE)
                node = CallStmt(name, args)
                line_text: str = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
                self.stmt_src[id(node)] = (self.filename, start_line, start_col, line_text)
                return node

        return self.parse_assign()
