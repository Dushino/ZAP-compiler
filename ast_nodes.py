
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
from symbols import SemType


class ASTNode:
    """Base class for all AST nodes."""
    pass


@dataclass(frozen=True)
class AsmBlock(ASTNode):
    """Inline assembly block node."""
    text: str


@dataclass(frozen=True)
class IncbinDirective(ASTNode):
    """Binary include directive node (.incbin)."""
    filename: str


@dataclass(frozen=True)
class ErrorDirective(ASTNode):
    """Compile-time error directive emitted by the parser."""
    message: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class WarningDirective(ASTNode):
    """Compile-time warning directive emitted by the parser."""
    message: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class InfoDirective(ASTNode):
    """Compile-time info directive emitted by the parser."""
    message: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class TypeNode(ASTNode):
    """Type specifier with base name and pointer flag."""
    base: str            # "byte", "word"
    is_pointer: bool     # True pokud ^

    def __repr__(self) -> str:
        """Return a concise type representation for debugging."""
        p = "^" if self.is_pointer else ""
        return f"Type({self.base}{p})"


class InitValue(ASTNode):
    """Base class for initializer expressions."""
    pass


@dataclass(frozen=True)
class ExprInit(InitValue):
    """Initializer that wraps a single expression."""
    expr: "Expr"

    def __repr__(self) -> str:
        """Return a readable initializer representation."""
        return f"InitExpr({self.expr})"


@dataclass(frozen=True)
class ListInit(InitValue):
    """Initializer with a list of expressions or nested initializers."""
    values: List["Expr | InitValue"]  # Can contain expressions or nested initializers

    def __repr__(self) -> str:
        """Return a readable list-initializer representation."""
        vals = ", ".join(repr(v) for v in self.values)
        return f"InitList([{vals}])"


@dataclass(frozen=True)
class StringInit(InitValue):
    """Initializer for string literals."""
    value: str
    line: int = 0
    col: int = 0

    def __repr__(self) -> str:
        """Return a readable string-initializer representation."""
        return f'InitString("{self.value}")'


@dataclass(frozen=True)
class Declarator(ASTNode):
    """Declarator for a single variable instance."""
    name: str
    array_size: Optional["Expr"] = None      # DEPRECATED: use array_sizes
    address: Optional["Expr"] = None         # None = bez @
    initializer: Optional[InitValue] = None
    array_sizes: Optional[List["Expr"]] = None  # Multi-dimensional: [size1, size2, ...]
    line: int = 0
    col: int = 0
    is_static: bool = False  # True for STATIC variables

    def __repr__(self) -> str:
        """Return a readable declarator representation."""
        parts = [self.name]

        # Show array dimensions
        sizes = self.array_sizes if self.array_sizes else (
            [self.array_size] if self.array_size is not None else []
        )
        for size in sizes:
            parts.append(f"[{size}]")

        if self.address is not None:
            parts.append(f"@{self.address}")

        if self.initializer is not None:
            parts.append(f"={self.initializer}")

        return "Decl(" + " ".join(parts) + ")"


@dataclass(frozen=True)
class Declaration(ASTNode):
    """Variable declaration with type and one or more declarators."""
    is_const: bool
    type: TypeNode
    declarators: List[Declarator]
    is_static: bool = False  # True if STATIC modifier was present
    is_port: bool = False    # True if PORT modifier was present (hardware port-mapped variable)
    port_rd: bool = False    # #RD - port readable
    port_wr: bool = False    # #WR - port writable
    # Declaration modifiers
    keep: bool = False      # #KEEP prevents dead-code elimination of unused globals
    noexport: bool = False  # #NOEXPORT prevents exporting from a module
    export: bool = False    # #EXPORT forces export even in non-module files

    def __repr__(self) -> str:
        """Return a readable declaration representation."""
        c = "const " if self.is_const else ""
        s = "static " if self.is_static else ""
        p = "port " if self.is_port else ""
        r = "rd " if self.port_rd else ""
        w = "wr " if self.port_wr else ""
        decls = ", ".join(repr(d) for d in self.declarators)
        return f"{c}{s}{p}{r}{w}Declaration({self.type}: {decls})"


@dataclass(frozen=True)
class StructField(ASTNode):
    """Struct field definition"""
    type: TypeNode
    name: str
    address: Optional["Expr"] = None    # None = no fixed address
    array_sizes: Optional[List["Expr"]] = None  # Multi-dimensional array: [size1, size2, ...]
    # Port modifiers on a field: None = unspecified, True/False explicit
    is_port: bool = False
    port_rd: Optional[bool] = None
    port_wr: Optional[bool] = None

    def __repr__(self) -> str:
        """Return a readable struct-field representation."""
        addr_str = f" @{self.address}" if self.address else ""
        array_str = ""
        if self.array_sizes:
            array_str = "".join(f"[{s}]" for s in self.array_sizes)
        mods = []
        if self.is_port:
            mods.append("#PORT")
        if self.port_rd is True:
            mods.append("#RD")
        if self.port_wr is True:
            mods.append("#WR")
        mods_str = (" " + " ".join(mods)) if mods else ""
        return f"StructField({self.type} {self.name}{array_str}{addr_str}{mods_str})"


@dataclass(frozen=True)
class StructDef(ASTNode):
    """Struct type definition"""
    name: str
    fields: List[StructField]
    # Optional struct-level port defaults
    is_port: bool = False
    port_rd: Optional[bool] = None
    port_wr: Optional[bool] = None
    # Declaration modifiers
    noexport: bool = False  # #NOEXPORT prevents exporting from a module
    export: bool = False    # #EXPORT forces export even in non-module files
    line: int = 0
    col: int = 0

    def __repr__(self) -> str:
        """Return a readable struct definition representation."""
        mods = []
        if self.is_port:
            mods.append("#PORT")
        if self.port_rd is True:
            mods.append("#RD")
        if self.port_wr is True:
            mods.append("#WR")
        mods_str = (" " + " ".join(mods)) if mods else ""
        fields_str = ", ".join(repr(f) for f in self.fields)
        return f"struct {self.name}{mods_str} {{ {fields_str} }}"


class Expr(ASTNode):
    """Base class for expressions."""
    pass


@dataclass(frozen=True)
class IntLiteral(Expr):
    """Integer literal expression."""
    value: int
    line: int = 0
    col: int = 0

    def __repr__(self) -> str:
        """Return the literal as a string for debugging."""
        return str(self.value)


@dataclass(frozen=True)
class StringLiteral(Expr):
    """String literal expression (address of null-terminated data)."""
    value: str
    line: int = 0
    col: int = 0

    def __repr__(self) -> str:
        """Return the literal as a string for debugging."""
        return f'"{self.value}"'


@dataclass(frozen=True)
class StructLiteral(Expr):
    """Struct literal expression: { ... }"""
    values: List["Expr | InitValue"]
    line: int = 0
    col: int = 0

    def __repr__(self) -> str:
        """Return a readable struct-literal representation."""
        vals = ", ".join(repr(v) for v in self.values)
        return f"{{{vals}}}"


@dataclass(frozen=True)
class Identifier(Expr):
    """Identifier reference expression."""
    name: str
    line: int = 0
    col: int = 0

    def __repr__(self) -> str:
        """Return the identifier name for debugging."""
        return self.name

@dataclass(frozen=True)
class DerefExpr(Expr):
    """Pointer dereference expression."""
    pointer: Expr
    line: int = 0
    col: int = 0

    def __repr__(self):
        """Return a readable dereference representation."""
        return f"{self.pointer}^"


@dataclass(frozen=True)
class SubscriptExpr(Expr):
    """Array subscript: arr[index] or nested arr[i][j]
    
    For multi-dimensional arrays, nesting creates the structure:
      arr[i][j] → SubscriptExpr(SubscriptExpr(arr, i), j)
    """
    array: Expr
    index: Expr
    line: int = 0
    col: int = 0

    def __repr__(self):
        """Return a readable subscript representation."""
        return f"{self.array}[{self.index}]"


@dataclass(frozen=True)
class FieldAccess(Expr):
    """Struct field access: obj.field or ptr^.field"""
    object: Expr
    field: str
    is_deref: bool = False    # True if via pointer dereference (ptr^.field)
    line: int = 0
    col: int = 0

    def __repr__(self):
        """Return a readable field-access representation."""
        op = "^." if self.is_deref else "."
        return f"{self.object}{op}{self.field}"

class BinOp(Enum):
    """Binary operator enumeration."""
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    MOD = "%"

    EQ  = "=="
    NE  = "!="
    LT  = "<"
    GT  = ">"
    LE  = "<="
    GE  = ">="

    BAND = "&"
    BOR  = "|"
    BXOR = "^"
    LSHIFT = "<<"
    RSHIFT = ">>"
    LAND = "&&"
    LOR  = "||"


@dataclass(frozen=True)
class BinaryExpr(Expr):
    """Binary operator expression node."""
    left: Expr
    op: BinOp
    right: Expr
    line: int = 0
    col: int = 0

    def __repr__(self):
        """Return a readable binary expression representation."""
        return f"({self.left} {self.op.value} {self.right})"


class UnOp(Enum):
    """Unary operator enumeration."""
    NOT = "!"
    BNOT = "~"  # Bitwise NOT
    ADDROF = "@"  # Address-of operator
    NEG = "-"   # Arithmetic negation (unary minus)


@dataclass(frozen=True)
class UnaryExpr(Expr):
    """Unary operator expression node."""
    op: UnOp
    expr: Expr
    line: int = 0
    col: int = 0

    def __repr__(self):
        """Return a readable unary expression representation."""
        return f"({self.op.value}{self.expr})"


@dataclass(frozen=True)
class CallExpr(Expr):
    """Function call expression node."""
    name: str
    args: list
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class FuncDecl:
    """Function declaration node."""
    name: str
    ret_type: TypeNode        # byte / word
    params: list[Parameter]
    locals: list[Declaration]
    body: list                # statementy
    # Declaration modifiers
    keep: bool = False      # #KEEP prevents dead-code elimination of unused func
    noexport: bool = False  # #NOEXPORT prevents export even in non-module files
    export: bool = False


@dataclass(frozen=True)
class Parameter:
    """Function/procedure parameter definition."""
    type: TypeNode
    name: str
    is_array: bool  # True if []
    default_value: Optional["Expr"] = None  # Default value expression, None if required param
    line: int = 0
    col: int = 0

@dataclass(frozen=True)
class ProcDecl:
    """Procedure declaration node."""
    name: str
    params: list[Parameter]
    locals: list[Declaration]
    body: list
    # Declaration modifiers
    keep: bool = False      # #KEEP prevents dead-code elimination of unused proc
    noexport: bool = False  # #NOEXPORT prevents exporting from a module
    export: bool = False    # #EXPORT forces export even in non-module files


@dataclass(frozen=True)
class CallStmt:
    """Procedure call statement node."""
    name: str
    args: list


@dataclass(frozen=True)
class AssignStmt:
    """Assignment statement node."""
    lhs: Expr
    rhs: Expr




@dataclass(frozen=True)
class ReturnStmt:
    """Return statement node."""
    expr: Optional[Expr]



@dataclass
class FuncSymbol:
    """Lightweight function symbol for type checking."""
    name: str
    ret_type: SemType


@dataclass(frozen=False)
class Program:
    """Top-level program container for declarations and procedures."""
    decls: list
    procs: list
    # funcs: list
    debug: dict | None = None
    # Exports collected during module resolution
    exports: set[str] | None = None
    # Ordered list of module constructors to run at program init (from deepest include to top-level)
    constructors: list[str] | None = None


@dataclass(frozen=True)
class EnumItem(ASTNode):
    """Single enum item entry."""
    name: str
    value: "Expr | None" = None
    line: int = 0
    col: int = 0
    filename: str = ""


@dataclass(frozen=True)
class EnumDecl(ASTNode):
    """Enum declaration node."""
    name: str
    base: str  # "byte" or "word"
    items: list[EnumItem]
    # Declaration modifiers
    noexport: bool = False  # #NOEXPORT prevents exporting from a module
    export: bool = False    # #EXPORT forces export even in non-module files
    line: int = 0
    col: int = 0
    filename: str = ""


@dataclass()
class IfStmt:
    """If/else statement node."""
    cond: Expr
    then_body: list
    else_body: list | None


@dataclass(frozen=True)
class WhileStmt:
    """While loop statement node."""
    cond: Expr
    body: list


@dataclass(frozen=True)
class RepeatUntilStmt:
    """Repeat-until loop statement node."""
    body: list
    cond: Expr


@dataclass(frozen=True)
class BreakStmt:
    """Loop break statement node."""
    pass

@dataclass(frozen=True)
class ContinueStmt:
    """Loop continue statement node."""
    pass

@dataclass
class ForStmt:
    """For loop statement node."""
    var: Identifier
    start: Expr
    end: Expr
    step: Expr | None
    body: list


@dataclass(frozen=True)
class SwitchCase:
    """Single switch-case clause node."""
    labels: list[Expr]
    body: list
    is_default: bool = False


@dataclass(frozen=True)
class SwitchStmt:
    """Switch statement node with case list."""
    expr: Expr
    cases: list[SwitchCase]
