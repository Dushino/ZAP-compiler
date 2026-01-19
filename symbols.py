from dataclasses import dataclass
from typing import Optional, Protocol
from errors import SemanticError


@dataclass(frozen=True)
class SemType:
    base: str            # "byte", "word"
    is_pointer: bool     # ^

    @property
    def width(self) -> int:
        if self.is_pointer:
            return 2
        if self.base == "byte":
            return 1
        if self.base == "word":
            return 2
        raise ValueError(self.base)


@dataclass
class Symbol:
    name: str
    type: SemType
    is_const: bool
    const_value: int | None    
    is_array: bool
    array_len: Optional[int]
    init: Optional[object]   # InitValue z AST (zatím)
    address: Optional[int] = None   # pevná adresa pro HW porty
    is_volatile: bool = False       # true → nelze optimalizovat čtení
    proc_name: str = ""             # jméno procedury (pro lokály)

    def asm_name(self) -> str:
        """Return assembly name: _NAME for globals, _PROC_NAME for locals."""
        if self.proc_name:
            return f"_{self.proc_name}_{self.name}"
        return f"_{self.name}"


class SymbolTable:
    def __init__(self):
        self._symbols: dict[str, Symbol] = {}

    def define(self, sym: Symbol):
        if sym.name in self._symbols:
            raise SemanticError(f"Variable '{sym.name}' already defined")
        self._symbols[sym.name] = sym

    def lookup(self, name: str) -> Symbol:
        return self._symbols[name]

    def __iter__(self):
        return iter(self._symbols.values())


class SymbolLookup(Protocol):
    def lookup(self, name: str) -> Symbol: ...


@dataclass
class ProcSymbol:
    name: str
    param_count: int = 0


class ProcTable:
    def __init__(self):
        self._procs: dict[str, ProcSymbol] = {}

    def define(self, p: ProcSymbol):
        if p.name in self._procs:
            raise SemanticError(f"Procedure '{p.name}' already defined")
        self._procs[p.name] = p

    def lookup(self, name: str) -> ProcSymbol:
        return self._procs[name]


class ScopedSymbolTable:
    def __init__(self, parent: SymbolTable):
        self.parent = parent
        self.local = SymbolTable()

    def lookup(self, name: str):
        try:
            return self.local.lookup(name)
        except KeyError:
            return self.parent.lookup(name)

@dataclass
class FuncSymbol:
    name: str
    ret_type: SemType
    param_count: int = 0


class FuncTable:
    def __init__(self):
        self._funcs: dict[str, FuncSymbol] = {}

    def define(self, f: FuncSymbol):
        if f.name in self._funcs:
            raise SemanticError(f"Function '{f.name}' already defined")
        self._funcs[f.name] = f

    def lookup(self, name: str) -> FuncSymbol:
        try:
            return self._funcs[name]
        except KeyError:
            raise SemanticError(f"Undefined function '{name}'")

