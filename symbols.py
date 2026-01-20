from dataclasses import dataclass
from typing import Optional, Protocol, List
from errors import SemanticError


@dataclass(frozen=True)
class StructFieldInfo:
    """Information about a struct field"""
    name: str
    base_type: str        # "byte", "word", or struct name
    is_pointer: bool
    offset: int           # Byte offset from struct start
    fixed_address: Optional[int] = None  # If field has @address

    @property
    def width(self) -> int:
        """Width of this field in bytes"""
        if self.is_pointer:
            return 2
        if self.base_type == "byte":
            return 1
        if self.base_type == "word":
            return 2
        # For struct types, will be calculated by StructRegistry
        return 0  # Will be looked up


@dataclass(frozen=True)
class StructInfo:
    """Information about a defined struct"""
    name: str
    fields: List[StructFieldInfo]
    size: int  # Total size in bytes

    def get_field(self, field_name: str) -> Optional[StructFieldInfo]:
        """Get field by name"""
        for f in self.fields:
            if f.name.upper() == field_name.upper():
                return f
        return None


class StructRegistry:
    """Registry for struct definitions"""
    def __init__(self):
        self._structs: dict[str, StructInfo] = {}

    def define(self, struct_info: StructInfo):
        """Register a struct definition"""
        if struct_info.name.upper() in self._structs:
            raise SemanticError(f"Struct '{struct_info.name}' already defined")
        self._structs[struct_info.name.upper()] = struct_info

    def lookup(self, name: str) -> Optional[StructInfo]:
        """Look up a struct by name"""
        return self._structs.get(name.upper())

    def is_defined(self, name: str) -> bool:
        """Check if a struct is defined"""
        return name.upper() in self._structs


@dataclass(frozen=True)
class SemType:
    base: str            # "byte", "word", or struct name
    is_pointer: bool     # ^ (pointer)
    is_struct: bool = False  # True if base is a struct name
    struct_info: Optional[StructInfo] = None  # Struct metadata if is_struct=True

    @property
    def width(self) -> int:
        if self.is_pointer:
            return 2
        if self.is_struct and self.struct_info:
            return self.struct_info.size
        base_lower = self.base.lower() if isinstance(self.base, str) else ""
        if base_lower == "byte":
            return 1
        if base_lower == "word":
            return 2
        raise ValueError(f"Unknown type: {self.base}")
    
    def get_size(self) -> int:
        """Alias for width property"""
        return self.width


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

