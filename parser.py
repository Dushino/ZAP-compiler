
from tokenizer import Tokenizer, Token
from token_types import *
from ast_nodes import *
from errors import SyntaxError

class Parser:
    def __init__(self, source: str, filename: str | None = None):
        self.filename = filename or "<input.act>"
        self.source = source
        self.source_lines = source.splitlines()
        self.tok = Tokenizer(source)
        self.tok.tokenize()
        self.tokens = self.tok._getTokens()        
        self.cur = self.tokens[0]
        self.pos = 0
        # Debug maps
        self.current_proc_name: str | None = None
        self.stmt_src: dict[int, tuple[str, int, str]] = {}
        self.local_decl_src: dict[tuple[str, str], tuple[str, int, str]] = {}
        self.global_decl_src: dict[str, tuple[str, int, str]] = {}
        self.proc_src: dict[str, tuple[str, int, str]] = {}

    def advance(self):
        self.pos += 1
        if self.pos < len(self.tokens):
            self.cur = self.tokens[self.pos]
        else:
            self.cur = Token(TOK_EOF, "", self.cur.line, self.cur.col)

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

        while self.cur.type != TOK_EOF:
            if self.cur.type == TOK_PREPROC and self.cur.value.upper() == ".SEGMENT":
                # Parse .segment directive at top level
                self.advance()
                if self.cur.type != TOK_STRING:
                    self.error("Expected string after .segment")
                segment_name = self.cur.value
                self.advance()
                procs.append(SegmentDirective(segment_name))
            elif self.cur.type in (TOK_TYPE, TOK_TYPEMOD):
                decls.append(self.parse_declaration())
            elif self.cur.type == TOK_KEYWORD and self.cur.value == "PROC":
                procs.append(self.parse_proc())
            elif self.cur.type == TOK_KEYWORD and self.cur.value == "FUNC":
                procs.append(self.parse_func())
            else:
                self.error("Expected declaration, PROC, or FUNC")
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


    def parse_proc(self):
        start_line = self.cur.line
        self.expect(TOK_KEYWORD, "PROC")
        name = self.cur.value
        self.expect(TOK_IDENT)

        # record proc source info
        line_text = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.proc_src[name] = (self.filename, start_line, line_text)
        self.current_proc_name = name

        locals = []
        body = []
        params = []

        self.expect(TOK_LBRACE)
        # parse parameter list
        if self.cur.type != TOK_RBRACE:
            params.append(self.parse_parameter())
            while self.cur.type == TOK_DELIM and self.cur.value == ',':
                self.advance()
                params.append(self.parse_parameter())
        self.expect(TOK_RBRACE)

        while self.cur.type in (TOK_TYPE, TOK_TYPEMOD):
            locals.append(self.parse_declaration())

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
        self.expect(TOK_KEYWORD, "FUNC")
        
        # return type
        ret_type_tok = self.cur
        self.expect(TOK_TYPE)
        ret_is_pointer = False
        if self.cur.type == TOK_PTR:
            ret_is_pointer = True
            self.advance()
        
        name = self.cur.value
        self.expect(TOK_IDENT)
        
        locals = []
        body = []
        params = []
        
        self.expect(TOK_LBRACE)
        # parse parameter list
        if self.cur.type != TOK_RBRACE:
            params.append(self.parse_parameter())
            while self.cur.type == TOK_DELIM and self.cur.value == ',':
                self.advance()
                params.append(self.parse_parameter())
        self.expect(TOK_RBRACE)
        
        while self.cur.type in (TOK_TYPE, TOK_TYPEMOD):
            locals.append(self.parse_declaration())
        
        while not (self.cur.type == TOK_KEYWORD and self.cur.value == "RETURN"):
            body.append(self.parse_stmt())
        
        # parse RETURN expression
        self.expect(TOK_KEYWORD, "RETURN")
        ret_expr = self.parse_expr()
        body.append(ReturnStmt(ret_expr))
        
        return FuncDecl(name, TypeNode(ret_type_tok.value, ret_is_pointer), params, locals, body)

    def parse_parameter(self):
        # type
        type_tok = self.cur
        self.expect(TOK_TYPE)
        
        is_pointer = False
        if self.cur.type == TOK_PTR:
            is_pointer = True
            self.advance()
        
        name = self.cur.value
        self.expect(TOK_IDENT)
        
        is_array = False
        if self.cur.type == TOK_OP and self.cur.value == '[':
            self.advance()
            self.expect(TOK_OP, ']')
            is_array = True
        
        return Parameter(TypeNode(type_tok.value, is_pointer), name, is_array)

    def parse_declaration(self):
        is_const = False

        # CONST prefix
        if self.cur.type == TOK_TYPEMOD:
            if self.cur.value != "CONST":
                self.error("Unsupported type modifier")
            is_const = True
            self.advance()

        # type
        type_tok = self.cur
        self.expect(TOK_TYPE)

        is_pointer = False
        if self.cur.type == TOK_PTR:
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
            self.expect(TOK_IDENT)

            array_size = None
            if _is_sqb("["):
                # [expr] or []
                self.advance()
                if not _is_sqb("]"):
                    array_size = self.parse_expr()
                else:
                    # [] → infer size from initializer
                    array_size = IntLiteral(-1)
                _expect_sqb("]")  # closing ]

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
                            values.append(self.parse_expr())
                            while self.cur.type == TOK_DELIM and self.cur.value == ',':
                                self.advance()
                                values.append(self.parse_expr())
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
                self.local_decl_src[(self.current_proc_name, name)] = (self.filename, decl_line, line_text)
            else:
                self.global_decl_src[name] = (self.filename, decl_line, line_text)
            return Declarator(name, array_size, address, init)

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
            if self.cur.type == TOK_PTR:
                self.advance()
                node = DerefExpr(node)
                continue
            break

        return node

    def parse_assign(self):
        start_line = self.cur.line
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
        self.stmt_src[id(node)] = (self.filename, start_line, line_text)
        return node

    def parse_term(self):
        node = self.parse_factor()
        while self.cur.type == TOK_OP and self.cur.value in ("*", "/", "%"):
            op = BinOp(self.cur.value)
            self.advance()
            rhs = self.parse_factor()
            node = BinaryExpr(node, op, rhs)
        return node


    def parse_logic_and(self):
        node = self.parse_rel()
        while self.cur.type == TOK_OP and self.cur.value == "&&":
            op = BinOp.LAND
            self.advance()
            rhs = self.parse_rel()
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

    def parse_rel(self):
        node = self.parse_add()
        while self.cur.type == TOK_OP and self.cur.value in (
            "==", "!=", "<", "<=", ">", ">="
        ):
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
    

    def parse_factor(self):
        if self.cur.type == TOK_NUMBER:
            val = self.cur.value
            self.advance()
            return IntLiteral(int(val, 0))

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
                if self.cur.type == TOK_PTR:
                    self.advance()
                    node = DerefExpr(node)
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
        self.stmt_src[id(node)] = (self.filename, start_line, line_text)
        return node


    def parse_while(self):
        start_line = self.cur.line
        self.expect(TOK_KEYWORD, "WHILE")
        cond = self.parse_expr()

        body = []
        while not (self.cur.type == TOK_KEYWORD and self.cur.value == "END"):
            body.append(self.parse_stmt())

        self.expect(TOK_KEYWORD, "END")
        node = WhileStmt(cond, body)
        line_text = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
        self.stmt_src[id(node)] = (self.filename, start_line, line_text)
        return node

    def parse_for(self):
        start_line = self.cur.line
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
        self.stmt_src[id(node)] = (self.filename, start_line, line_text)
        return node


    def parse_stmt(self):
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
                start_line = self.cur.line  # line after reading RETURN token; approximate
                line_text = self.source_lines[start_line-1] if 1 <= start_line <= len(self.source_lines) else ""
                self.stmt_src[id(node)] = (self.filename, start_line, line_text)
                return node

        # Call statement: IDENT(...)
        if self.cur.type == TOK_IDENT:
            # peek next token
            nxt = self.tokens[self.pos+1] if self.pos+1 < len(self.tokens) else None
            if nxt is not None and nxt.type == TOK_LBRACE:
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
                return CallStmt(name, args)

        return self.parse_assign()
