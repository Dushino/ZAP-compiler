
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
from symbols import SemType


class ASTNode:
    pass


@dataclass(frozen=True)
class AsmBlock(ASTNode):
    text: str


@dataclass(frozen=True)
class SegmentDirective(ASTNode):
    name: str


@dataclass(frozen=True)
class IncbinDirective(ASTNode):
    filename: str


@dataclass(frozen=True)
class TypeNode(ASTNode):
    base: str            # "byte", "word"
    is_pointer: bool     # True pokud ^

    def __repr__(self) -> str:
        p = "^" if self.is_pointer else ""
        return f"Type({self.base}{p})"


class InitValue(ASTNode):
    pass


@dataclass(frozen=True)
class ExprInit(InitValue):
    expr: "Expr"

    def __repr__(self) -> str:
        return f"InitExpr({self.expr})"


@dataclass(frozen=True)
class ListInit(InitValue):
    values: List["Expr | InitValue"]  # Can contain expressions or nested initializers

    def __repr__(self) -> str:
        vals = ", ".join(repr(v) for v in self.values)
        return f"InitList([{vals}])"


@dataclass(frozen=True)
class StringInit(InitValue):
    value: str

    def __repr__(self) -> str:
        return f'InitString("{self.value}")'


@dataclass(frozen=True)
class Declarator(ASTNode):
    name: str
    array_size: Optional["Expr"] = None      # DEPRECATED: use array_sizes
    address: Optional["Expr"] = None         # None = bez @
    initializer: Optional[InitValue] = None
    array_sizes: Optional[List["Expr"]] = None  # Multi-dimensional: [size1, size2, ...]
    line: int = 0
    col: int = 0
    is_static: bool = False  # True for STATIC variables

    def __repr__(self) -> str:
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

    def __repr__(self) -> str:
        addr_str = f" @{self.address}" if self.address else ""
        array_str = ""
        if self.array_sizes:
            array_str = "".join(f"[{s}]" for s in self.array_sizes)
        return f"StructField({self.type} {self.name}{array_str}{addr_str})"


@dataclass(frozen=True)
class StructDef(ASTNode):
    """Struct type definition"""
    name: str
    fields: List[StructField]
    line: int = 0
    col: int = 0

    def __repr__(self) -> str:
        fields_str = ", ".join(repr(f) for f in self.fields)
        return f"struct {self.name} {{ {fields_str} }}"


class Expr(ASTNode):
    pass


@dataclass(frozen=True)
class IntLiteral(Expr):
    value: int
    line: int = 0
    col: int = 0

    def __repr__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class Identifier(Expr):
    name: str
    line: int = 0
    col: int = 0

    def __repr__(self) -> str:
        return self.name

@dataclass(frozen=True)
class DerefExpr(Expr):
    pointer: Expr
    line: int = 0
    col: int = 0

    def __repr__(self):
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
        op = "^." if self.is_deref else "."
        return f"{self.object}{op}{self.field}"

class BinOp(Enum):
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
    left: Expr
    op: BinOp
    right: Expr
    line: int = 0
    col: int = 0

    def __repr__(self):
        return f"({self.left} {self.op.value} {self.right})"


class UnOp(Enum):
    NOT = "!"
    BNOT = "~"  # Bitwise NOT
    ADDROF = "@"  # Address-of operator


@dataclass(frozen=True)
class UnaryExpr(Expr):
    op: UnOp
    expr: Expr
    line: int = 0
    col: int = 0

    def __repr__(self):
        return f"({self.op.value}{self.expr})"


@dataclass(frozen=True)
class CallExpr(Expr):
    name: str
    args: list
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class FuncDecl:
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
    type: TypeNode
    name: str
    is_array: bool  # True if []
    default_value: Optional["Expr"] = None  # Default value expression, None if required param
    line: int = 0
    col: int = 0

@dataclass(frozen=True)
class ProcDecl:
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
    name: str
    args: list


@dataclass(frozen=True)
class AssignStmt:
    lhs: Expr
    rhs: Expr




@dataclass(frozen=True)
class ReturnStmt:
    expr: Optional[Expr]



@dataclass
class FuncSymbol:
    name: str
    ret_type: SemType


@dataclass(frozen=False)
class Program:
    decls: list
    procs: list
    # funcs: list
    debug: dict | None = None
    # Exports collected during module resolution
    exports: set[str] | None = None


@dataclass(frozen=True)
class EnumItem(ASTNode):
    name: str
    value: "Expr | None" = None
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class EnumDecl(ASTNode):
    name: str
    base: str  # "byte" or "word"
    items: list[EnumItem]
    line: int = 0
    col: int = 0


@dataclass()
class IfStmt:
    cond: Expr
    then_body: list
    else_body: list | None


@dataclass(frozen=True)
class WhileStmt:
    cond: Expr
    body: list


@dataclass(frozen=True)
class BreakStmt:
    pass

@dataclass(frozen=True)
class ContinueStmt:
    pass

@dataclass
class ForStmt:
    var: Identifier
    start: Expr
    end: Expr
    step: Expr | None
    body: list
