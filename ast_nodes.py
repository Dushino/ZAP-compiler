
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum, auto
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
    array_size: Optional["Expr"]      # None = není pole
    address: Optional["Expr"]         # None = bez @
    initializer: Optional[InitValue]
    line: int = 0
    col: int = 0

    def __repr__(self) -> str:
        parts = [self.name]

        if self.array_size is not None:
            parts.append(f"[{self.array_size}]")

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

    def __repr__(self) -> str:
        c = "const " if self.is_const else ""
        decls = ", ".join(repr(d) for d in self.declarators)
        return f"{c}Declaration({self.type}: {decls})"


@dataclass(frozen=True)
class StructField(ASTNode):
    """Struct field definition"""
    type: TypeNode
    name: str
    address: Optional["Expr"] = None    # None = no fixed address

    def __repr__(self) -> str:
        addr_str = f" @{self.address}" if self.address else ""
        return f"StructField({self.type} {self.name}{addr_str})"


@dataclass(frozen=True)
class StructDef(ASTNode):
    """Struct type definition"""
    name: str
    fields: List[StructField]

    def __repr__(self) -> str:
        fields_str = ", ".join(repr(f) for f in self.fields)
        return f"struct {self.name} {{ {fields_str} }}"


class Expr(ASTNode):
    pass


@dataclass(frozen=True)
class IntLiteral(Expr):
    value: int

    def __repr__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class Identifier(Expr):
    name: str

    def __repr__(self) -> str:
        return self.name

@dataclass(frozen=True)
class DerefExpr(Expr):
    pointer: Expr

    def __repr__(self):
        return f"{self.pointer}^"


@dataclass(frozen=True)
class SubscriptExpr(Expr):
    array: Expr
    index: Expr

    def __repr__(self):
        return f"{self.array}[{self.index}]"


@dataclass(frozen=True)
class FieldAccess(Expr):
    """Struct field access: obj.field or ptr^.field"""
    object: Expr
    field: str
    is_deref: bool = False    # True if via pointer dereference (ptr^.field)

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

    def __repr__(self):
        return f"({self.op.value}{self.expr})"


@dataclass(frozen=True)
class Parameter:
    type: TypeNode
    name: str
    is_array: bool  # True if []
    line: int = 0
    col: int = 0

@dataclass(frozen=True)
class ProcDecl:
    name: str
    params: list[Parameter]
    locals: list[Declaration]
    body: list


@dataclass(frozen=True)
class CallStmt:
    name: str
    args: list


@dataclass(frozen=True)
class AssignStmt:
    lhs: Expr
    rhs: Expr


@dataclass(frozen=True)
class FuncDecl:
    name: str
    ret_type: TypeNode        # byte / word
    params: list[Parameter]
    locals: list[Declaration]
    body: list                # statementy


@dataclass(frozen=True)
class ReturnStmt:
    expr: Optional[Expr]


@dataclass(frozen=True)
class CallExpr(Expr):
    name: str
    args: list


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
