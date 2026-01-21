
from tokenizer import Tokenizer, Token
from token_types import *
from ast_nodes import *
from errors import SyntaxError

class Parser:
    def __init__(self, source: str, filename: str | None = None):
        self.filename = filename or "<input.act>"
        # Remove BOM if present (can be \ufeff or UTF-8 BOM misinterpreted as 'ï»¿')
        if source.startswith('\ufeff'):
            source = source[1:]
        elif source.startswith('ï»¿'):
            # UTF-8 BOM misinterpreted by non-UTF-8-aware decoder
            source = source[3:]
        self.source = source
        self.source_lines = source.splitlines()
        self.tok = Tokenizer(source)
        self.tok.tokenize()
        self.tokens = self.tok._getTokens()        
        self.cur = self.tokens[0] if self.tokens else None
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

    def advance(self):
        self.pos += 1
        if self.pos < len(self.tokens):
            self.cur = self.tokens[self.pos]
        else:
            self.cur = Token(TOK_EOF, "", self.cur.line, self.cur.col)

    def _peek_next(self):
        """Peek at the token after the current one without advancing"""
        next_pos = self.pos + 1
        if next_pos < len(self.tokens):
            return self.tokens[next_pos]
        return None

    def expect(self, kind, value=None):
        if self.cur.type != kind:
            raise SyntaxError(
                f'Expected token {kind}, got {self.cur.type} ({self.cur.value})',
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

    def error(self, msg):
        raise SyntaxError(
            msg,
            line=self.cur.line,
            col=self.cur.col
        )


    def parse_program(self):
        decls = []
        procs = []

        # FIRST PASS: Collect struct names
        # This allows us to recognize struct names as types in declarations
        temp_pos = self.pos
        temp_cur = self.cur
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
            else:
                self.advance()
        
        # RESET to beginning
        self.pos = temp_pos
        if self.pos < len(self.tokens):
            self.cur = self.tokens[self.pos]

        # SECOND PASS: Parse everything
        while self.cur.type != TOK_EOF:
            if self.cur.type == TOK_PREPROC and self.cur.value.upper() == ".SEGMENT":
                # Parse .segment directive at top level
                self.advance()
                if self.cur.type != TOK_STRING:
                    self.error("Expected string after .segment")
                segment_name = self.cur.value
                self.advance()
                procs.append(SegmentDirective(segment_name))
            elif self.cur.type == TOK_OP and self.cur.value == ".":
                # Handle . followed by IDENT (preprocessor directive like .include)
                self.advance()
                if self.cur.type == TOK_IDENT:
                    directive = self.cur.value.upper()
                    self.advance()
                    if directive == "INCLUDE":
                        if self.cur.type != TOK_STRING:
                            self.error("Expected string after .include")
                        # Skip .include directives for now
                        self.advance()
                    elif directive == "SEGMENT":
                        if self.cur.type != TOK_STRING:
                            self.error("Expected string after .segment")
                        segment_name = self.cur.value
                        self.advance()
                        procs.append(SegmentDirective(segment_name))
                    else:
                        # Unknown directive, skip it
                        pass
                else:
                    self.error("Expected identifier after '.'")
            elif self.cur.type == TOK_KEYWORD and self.cur.value == "STRUCT":
                procs.append(self.parse_struct_def())
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


    def parse_struct_def(self):
        """Parse struct definition: struct Name field_list end"""
        start_line = self.cur.line
        start_col = self.cur.col
        self.expect(TOK_KEYWORD, "STRUCT")
        
        struct_name = self.cur.value
        self.expect(TOK_IDENT)
        
        fields = []
        seen_names: set[str] = set()
        
        # Parse field list until END
        while not (self.cur.type == TOK_KEYWORD and self.cur.value == "END"):
            # Parse: [^] type IDENT [dimensions] [ address_spec ]
            # Check for pointer prefix first
            is_pointer = False
            if self.cur.type == TOK_PTR or (self.cur.type == TOK_OP and self.cur.value == "^"):
                is_pointer = True
                self.advance()
            
            # type (either built-in like byte/word, or a struct name)
            if self.cur.type == TOK_TYPE:
                # Built-in type (byte, word)
                type_name = self.cur.value
                type_tok = self.cur
                self.advance()
            elif self.cur.type == TOK_IDENT and self.cur.value.upper() in self.struct_names:
                # Struct type (nested struct)
                type_name = self.cur.value
                type_tok = self.cur
                self.advance()
            else:
                self.error(f"Expected type in struct field, got {self.cur.type} {self.cur.value}")
            
            field_type = TypeNode(type_name, is_pointer)
            
            # field name
            field_name = self.cur.value
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
            
            fields.append(StructField(field_type, field_name, field_addr, array_sizes))
        
        self.expect(TOK_KEYWORD, "END")
        return StructDef(struct_name, fields)


    def parse_proc(self):
        start_line = self.cur.line
        start_col = self.cur.col
        self.expect(TOK_KEYWORD, "PROC")
        name = self.cur.value
        self.expect(TOK_IDENT)

        # record proc source info
        line_text = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.proc_src[name] = (self.filename, start_line, start_col, line_text)
        self.current_proc_name = name

        locals = []
        body = []
        params = []
        seen_names: set[str] = set()

        self.expect(TOK_LBRACE)
        # parse parameter list
        if self.cur.type != TOK_RBRACE:
            p = self.parse_parameter()
            if p.name in seen_names:
                raise SyntaxError(f"Duplicate parameter '{p.name}' in procedure", line=p.line, col=p.col)
            seen_names.add(p.name)
            params.append(p)
            while self.cur.type == TOK_DELIM and self.cur.value == ',':
                self.advance()
                p = self.parse_parameter()
                if p.name in seen_names:
                    raise SyntaxError(f"Duplicate parameter '{p.name}' in procedure", line=p.line, col=p.col)
                seen_names.add(p.name)
                params.append(p)
        self.expect(TOK_RBRACE)

        def _is_declaration_start():
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
                next_tok = self.tokens[self.pos+1] if self.pos+1 < len(self.tokens) else None
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
            decl = self.parse_declaration()
            for d in decl.declarators:
                if d.name in seen_names:
                    raise SyntaxError(f"Duplicate local '{d.name}' in procedure", line=d.line, col=d.col)
                seen_names.add(d.name)
            locals.append(decl)

        while not (self.cur.type == TOK_KEYWORD and self.cur.value in ("END", "RETURN")):
            body.append(self.parse_stmt())

        # Handle RETURN or END
        if self.cur.type == TOK_KEYWORD and self.cur.value == "RETURN":
            self.advance()
            # RETURN in a PROC has no expression
            body.append(ReturnStmt(None))
        else:
            self.expect(TOK_KEYWORD, "END")

        self.current_proc_name = None
        return ProcDecl(name, params, locals, body)

    def parse_func(self):
        start_line = self.cur.line
        start_col = self.cur.col
        self.expect(TOK_KEYWORD, "FUNC")
        
        # return type: can be TYPE (byte/word) or STRUCT_NAME
        ret_type_tok = self.cur
        if self.cur.type == TOK_TYPE:
            self.advance()
            ret_type_base = ret_type_tok.value
        elif self.cur.type == TOK_IDENT and self.cur.value.upper() in self.struct_names:
            # Struct return type
            ret_type_base = self.cur.value
            self.advance()
        else:
            self.error(f"Expected type for function return, got {self.cur.type}")
        
        ret_is_pointer = False
        if self.cur.type == TOK_PTR or (self.cur.type == TOK_OP and self.cur.value == "^"):
            ret_is_pointer = True
            self.advance()
        
        name = self.cur.value
        self.expect(TOK_IDENT)
        
        locals = []
        body = []
        params = []
        seen_names: set[str] = set()
        
        self.expect(TOK_LBRACE)
        # parse parameter list
        if self.cur.type != TOK_RBRACE:
            p = self.parse_parameter()
            if p.name in seen_names:
                raise SyntaxError(f"Duplicate parameter '{p.name}' in function", line=p.line, col=p.col)
            seen_names.add(p.name)
            params.append(p)
            while self.cur.type == TOK_DELIM and self.cur.value == ',':
                self.advance()
                p = self.parse_parameter()
                if p.name in seen_names:
                    raise SyntaxError(f"Duplicate parameter '{p.name}' in function", line=p.line, col=p.col)
                seen_names.add(p.name)
                params.append(p)
        self.expect(TOK_RBRACE)
        
        while self.cur.type in (TOK_TYPE, TOK_TYPEMOD) or (self.cur.type == TOK_IDENT and self.cur.value.upper() in self.struct_names):
            decl = self.parse_declaration()
            for d in decl.declarators:
                if d.name in seen_names:
                    raise SyntaxError(f"Duplicate local '{d.name}' in function", line=d.line, col=d.col)
                seen_names.add(d.name)
            locals.append(decl)
        
        while not (self.cur.type == TOK_KEYWORD and self.cur.value == "RETURN"):
            body.append(self.parse_stmt())
        
        # parse RETURN expression
        self.expect(TOK_KEYWORD, "RETURN")
        ret_expr = self.parse_expr()
        body.append(ReturnStmt(ret_expr))

        # consume END keyword
        self.expect(TOK_KEYWORD, "END")

        line_text = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.proc_src[name] = (self.filename, start_line, start_col, line_text)

        return FuncDecl(name, TypeNode(ret_type_base, ret_is_pointer), params, locals, body)

    def parse_parameter(self):
        # type: can be TYPE (byte/word) or STRUCT_NAME, optionally const
        is_const = False
        if self.cur.type == TOK_TYPEMOD and self.cur.value.upper() == "CONST":
            is_const = True
            self.advance()
        
        type_tok = self.cur
        if self.cur.type == TOK_TYPE:
            self.advance()
            type_base = type_tok.value
        elif self.cur.type == TOK_IDENT and self.cur.value.upper() in self.struct_names:
            # Struct parameter type
            type_base = self.cur.value
            self.advance()
        else:
            self.error(f"Expected type for parameter, got {self.cur.type}")
        
        is_pointer = False
        if self.cur.type == TOK_PTR or (self.cur.type == TOK_OP and self.cur.value == "^"):
            is_pointer = True
            self.advance()
        
        name = self.cur.value
        name_line = self.cur.line
        name_col = self.cur.col
        self.expect(TOK_IDENT)
        
        is_array = False
        if self.cur.type == TOK_OP and self.cur.value == '[':
            self.advance()
            self.expect(TOK_OP, ']')
            is_array = True
        
        return Parameter(TypeNode(type_base, is_pointer), name, is_array, name_line, name_col)

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

    def parse_declaration(self):
        is_const = False

        # CONST prefix
        if self.cur.type == TOK_TYPEMOD:
            if self.cur.value != "CONST":
                self.error("Unsupported type modifier")
            is_const = True
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
                col=decl_col
            )

        declarators = [parse_declarator()]

        while self.cur.type == TOK_DELIM and self.cur.value == ',':
            self.advance()
            declarators.append(parse_declarator())

        return Declaration(
            is_const=is_const,
            type=TypeNode(type_tok.value, is_pointer),
            declarators=declarators
        )


    def parse_lvalue(self):
        if self.cur.type != TOK_IDENT:
            self.error("Expected identifier")

        node = Identifier(self.cur.value)
        self.advance()

        while True:
            if self.cur.type in (TOK_SQB, TOK_OP) and self.cur.value == "[":
                self.advance()
                idx = self.parse_expr()
                if self.cur.type in (TOK_SQB, TOK_OP) and self.cur.value == "]":
                    self.advance()
                else:
                    self.error("Expected ']' after subscript")
                node = SubscriptExpr(node, idx)
                continue
            if (self.cur.type == TOK_PTR) or (self.cur.type == TOK_OP and self.cur.value == "^"):
                # Check for ptr^.field pattern
                if self.cur.type == TOK_PTR:
                    next_tok = self._peek_next()
                    if next_tok and next_tok.type == TOK_OP and next_tok.value == ".":
                        # This is ptr^.field - consume ^ and ., then field name
                        self.advance()  # consume ^
                        self.advance()  # consume .
                        if self.cur.type != TOK_IDENT:
                            self.error("Expected field name after '.'")
                        field_name = self.cur.value
                        self.advance()
                        node = FieldAccess(DerefExpr(node), field_name, is_deref=True)
                        continue
                # Otherwise, just treat as postfix dereference
                self.advance()
                node = DerefExpr(node)
                continue
            # Handle field access: obj.field
            if self.cur.type == TOK_OP and self.cur.value == ".":
                self.advance()
                if self.cur.type != TOK_IDENT:
                    self.error("Expected field name after '.'")
                field_name = self.cur.value
                self.advance()
                node = FieldAccess(node, field_name, is_deref=False)
                continue
            # Handle pointer field access: ptr^.field (handled as ptr^ then field)
            break

        return node

    def parse_assign(self):
        start_line = self.cur.line
        start_col = self.cur.col
        lhs = self.parse_lvalue()

        # defensive: if after lvalue we see '(', treat as a call statement
        if self.cur.type == TOK_LBRACE:
            if not isinstance(lhs, Identifier):
                self.error("Call target must be identifier")
            # parse args
            self.advance()
            args = []
            if self.cur.type != TOK_RBRACE:
                args.append(self.parse_expr())
                while self.cur.type == TOK_DELIM and self.cur.value == ',':
                    self.advance()
                    args.append(self.parse_expr())
            self.expect(TOK_RBRACE)
            return CallStmt(lhs.name, args)

        self.expect(TOK_EQU)

        rhs = self.parse_expr()
        node = AssignStmt(lhs, rhs)
        line_text = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.stmt_src[id(node)] = (self.filename, start_line, start_col, line_text)
        return node

    def parse_term(self):
        node = self.parse_factor()
        while self.cur.type == TOK_OP and self.cur.value in ("*", "/", "%"):
            op = BinOp(self.cur.value)
            self.advance()
            rhs = self.parse_factor()
            node = BinaryExpr(node, op, rhs)
        return node


    def parse_shift(self):
        node = self.parse_add()
        while self.cur.type == TOK_OP and self.cur.value in ("<<", ">>"):
            op = BinOp(self.cur.value)
            self.advance()
            rhs = self.parse_add()
            node = BinaryExpr(node, op, rhs)
        return node


    def parse_add(self):
        node = self.parse_term()
        while self.cur.type == TOK_OP and self.cur.value in ("+", "-"):
            op = BinOp(self.cur.value)
            self.advance()
            rhs = self.parse_term()
            node = BinaryExpr(node, op, rhs)
        return node


    def parse_rel(self):
        node = self.parse_shift()
        while self.cur.type == TOK_OP and self.cur.value in (
            "==", "!=", "<", "<=", ">", ">="
        ):
            op = BinOp(self.cur.value)
            self.advance()
            rhs = self.parse_shift()
            node = BinaryExpr(node, op, rhs)
        return node


    def parse_bitwise_and(self):
        node = self.parse_rel()
        while self.cur.type == TOK_OP and self.cur.value == "&":
            op = BinOp.BAND
            self.advance()
            rhs = self.parse_rel()
            node = BinaryExpr(node, op, rhs)
        return node


    def parse_bitwise_xor(self):
        node = self.parse_bitwise_and()
        while self.cur.type == TOK_OP and self.cur.value == "^":
            op = BinOp.BXOR
            self.advance()
            rhs = self.parse_bitwise_and()
            node = BinaryExpr(node, op, rhs)
        return node


    def parse_bitwise_or(self):
        node = self.parse_bitwise_xor()
        while self.cur.type == TOK_OP and self.cur.value == "|":
            op = BinOp.BOR
            self.advance()
            rhs = self.parse_bitwise_xor()
            node = BinaryExpr(node, op, rhs)
        return node


    def parse_logic_and(self):
        node = self.parse_bitwise_or()
        while self.cur.type == TOK_OP and self.cur.value == "&&":
            op = BinOp.LAND
            self.advance()
            rhs = self.parse_bitwise_or()
            node = BinaryExpr(node, op, rhs)
        return node


    def parse_logic_or(self):
        node = self.parse_logic_and()
        while self.cur.type == TOK_OP and self.cur.value == "||":
            op = BinOp.LOR
            self.advance()
            rhs = self.parse_logic_and()
            node = BinaryExpr(node, op, rhs)
        return node

    def parse_expr(self):
        return self.parse_logic_or()

    def parse_factor(self):
        # Handle unary operators (prefix)
        if self.cur.type == TOK_AT:
            # Address-of operator @expr
            self.advance()
            operand = self.parse_factor()  # Parse the expression to take address of
            return UnaryExpr(UnOp.ADDROF, operand)
        
        if self.cur.type == TOK_OP and self.cur.value == "~":
            op_line = self.cur.line
            op_col = self.cur.col
            self.advance()
            operand = self.parse_factor()  # Recursive call for nested unary operators
            return UnaryExpr(UnOp.BNOT, operand)
        
        if self.cur.type == TOK_NUMBER:
            val = self.cur.value
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
                    combined_val = first_val | (next_val << 8)
                    return IntLiteral(combined_val)
            
            return IntLiteral(first_val)

        if self.cur.type == TOK_IDENT:
            name = self.cur.value
            node = Identifier(name)
            self.advance()

            while True:
                # function call as expression: ident(...)
                if self.cur.type == TOK_LBRACE:
                    # parse argument list
                    self.advance()
                    args = []
                    if self.cur.type != TOK_RBRACE:
                        args.append(self.parse_expr())
                        while self.cur.type == TOK_DELIM and self.cur.value == ',':
                            self.advance()
                            args.append(self.parse_expr())
                    self.expect(TOK_RBRACE)
                    return CallExpr(name, args)
                if self.cur.type in (TOK_SQB, TOK_OP) and self.cur.value == "[":
                    self.advance()
                    idx = self.parse_expr()
                    if self.cur.type in (TOK_SQB, TOK_OP) and self.cur.value == "]":
                        self.advance()
                    else:
                        self.error("Expected ']' after subscript")
                    node = SubscriptExpr(node, idx)
                    continue
                # IMPORTANT: Check for ptr^.field BEFORE checking for standalone ^
                # This must be checked first because ^ can be consumed as postfix deref
                if self.cur.type == TOK_PTR:
                    next_tok = self._peek_next()
                    if next_tok and next_tok.type == TOK_OP and next_tok.value == ".":
                        self.advance()  # consume ^
                        self.advance()  # consume .
                        field_name = self.cur.value
                        self.expect(TOK_IDENT)
                        node = FieldAccess(DerefExpr(node), field_name, is_deref=True)
                        continue
                # For caret: only treat as postfix dereference if next token cannot start an expression
                # If it could be an expression (IDENT, NUMBER, LBRACE, etc.), then it's likely binary XOR
                if self.cur.type == TOK_PTR:
                    self.advance()
                    node = DerefExpr(node)
                    continue
                # Check for caret as postfix dereference
                # Only consume it if the next token is NOT an identifier or number (which would indicate binary XOR)
                if self.cur.type == TOK_OP and self.cur.value == "^":
                    # Look ahead to see if this might be binary XOR
                    next_tok = self._peek_next()
                    # If next token is IDENT or NUMBER on the SAME line, it's likely binary XOR
                    # If it's on a different line, it's the start of a new statement, so ^ is postfix deref
                    if next_tok and next_tok.type in (TOK_IDENT, TOK_NUMBER) and next_tok.line == self.cur.line:
                        # This is likely binary XOR (a ^ b), don't consume the ^
                        break
                    # Otherwise treat as postfix dereference
                    self.advance()
                    node = DerefExpr(node)
                    continue
                # Field access: obj.field
                if self.cur.type == TOK_OP and self.cur.value == ".":
                    self.advance()
                    field_name = self.cur.value
                    self.expect(TOK_IDENT)
                    node = FieldAccess(node, field_name, is_deref=False)
                    continue
                break
            return node

        if self.cur.type == TOK_LBRACE:
            self.advance()
            node = self.parse_expr()
            self.expect(TOK_RBRACE)
            return node

        self.error(f"Expected expression, got {self.cur.type}")

            
    def parse_if(self):
        start_line = self.cur.line
        start_col = self.cur.col
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
        cur_if = root_if

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
            cur_if = next_if

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
        node = root_if
        line_text = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.stmt_src[id(node)] = (self.filename, start_line, start_col, line_text)
        return node


    def parse_while(self):
        start_line = self.cur.line
        start_col = self.cur.col
        self.expect(TOK_KEYWORD, "WHILE")
        cond = self.parse_expr()

        body = []
        while not (self.cur.type == TOK_KEYWORD and self.cur.value == "END"):
            body.append(self.parse_stmt())

        self.expect(TOK_KEYWORD, "END")
        node = WhileStmt(cond, body)
        line_text = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.stmt_src[id(node)] = (self.filename, start_line, start_col, line_text)
        return node

    def parse_for(self):
        start_line = self.cur.line
        start_col = self.cur.col
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
        while not (
            self.cur.type == TOK_KEYWORD and self.cur.value == "NEXT"
        ):
            body.append(self.parse_stmt())

        self.expect(TOK_KEYWORD, "NEXT")
        # Action requires: NEXT <var>
        self.expect(TOK_IDENT)
        node = ForStmt(var, start, end, step, body)
        line_text = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.stmt_src[id(node)] = (self.filename, start_line, start_col, line_text)
        return node


    def parse_stmt(self):
        if self.cur.type in (TOK_TYPE, TOK_TYPEMOD):
            self.error("Local variable declarations must be placed before the first statement in a procedure")

        # blokové terminátory NESMÍ být parsovány jako statement
        if self.cur.type == TOK_KEYWORD and self.cur.value in ("END", "ENDIF", "ELSE"):
            self.error(f"Unexpected block terminator {self.cur.value}")

        if self.cur.type == TOK_PREPROC and self.cur.value.upper() == ".SEGMENT":
            # Parse .segment directive in statement context
            self.advance()
            if self.cur.type != TOK_STRING:
                self.error("Expected string after .segment")
            segment_name = self.cur.value
            self.advance()
            return SegmentDirective(segment_name)

        if self.cur.type == TOK_KEYWORD:
            if self.cur.value == "ASM":
                self.advance()
                if self.cur.type != TOK_ASM_BLOCK:
                    self.error("Expected ASM block after ASM")
                block_text = self.cur.value
                self.advance()
                return AsmBlock(block_text)
            if self.cur.value == "IF":
                return self.parse_if()
            if self.cur.value == "WHILE":
                return self.parse_while()
            if self.cur.value == "FOR":
                return self.parse_for()
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
                ret_line = self.cur.line
                ret_col = self.cur.col
                line_text = self.source_lines[ret_line-1] if 1 <= ret_line <= len(self.source_lines) else ""
                self.stmt_src[id(node)] = (self.filename, ret_line, ret_col, line_text)
                return node

        # Call statement: IDENT(...)
        if self.cur.type == TOK_IDENT:
            # peek next token
            nxt = self.tokens[self.pos+1] if self.pos+1 < len(self.tokens) else None
            if nxt is not None and nxt.type == TOK_LBRACE:
                start_line = self.cur.line
                name = self.cur.value
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
                line_text = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
                self.stmt_src[id(node)] = (self.filename, start_line, line_text)
                return node

        return self.parse_assign()
