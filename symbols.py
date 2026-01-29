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
    array_sizes: Optional[List[int]] = None  # For arrays: [size1, size2, ...]

    @property
    def width(self) -> int:
        """Width of this field in bytes"""
        # Calculate element width
        if self.is_pointer:
            elem_width = 2
        elif self.base_type == "byte":
            elem_width = 1
        elif self.base_type == "word":
            elem_width = 2
        else:
            # For struct types, will be calculated by StructRegistry
            elem_width = 0  # Will be looked up
        
        # If it's an array, multiply by total elements
        if self.array_sizes:
            total_elements = 1
            for size in self.array_sizes:
                total_elements *= size
            return elem_width * total_elements
        
        return elem_width


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
    array_len: Optional[int]   # DEPRECATED: use array_dims for multi-dim support
    init: Optional[object]     # InitValue z AST (zatím)
    address: Optional[int] = None   # pevná adresa pro HW porty
    is_volatile: bool = False       # true → nelze optimalizovat čtení
    proc_name: str = ""             # jméno procedury (pro lokály)
    array_dims: Optional[List[int]] = None  # [10, 20, 30] for 3D array
    is_static: bool = False         # true → static local variable (initialized once at program start)
    is_port: bool = False           # true → PORT modifier (hardware port-mapped variable)

    def asm_name(self) -> str:
        """Return assembly name: _NAME for globals, _PROC_NAME for locals."""
        if self.proc_name:
            return f"_{self.proc_name}_{self.name}"
        return f"_{self.name}"
    
    def get_total_array_size(self) -> int:
        """Calculate total size in bytes for array (including element type width)"""
        if not self.is_array:
            return 0
        
        # Get element size based on type
        element_width = self.type.width
        
        # Multiply by all dimension sizes
        total = element_width
        if self.array_dims:
            # Check for any None values (should be resolved during semantic analysis)
            if any(d is None for d in self.array_dims):
                # Inferred dimension not resolved - can't calculate size
                return 0
            for dim in self.array_dims:
                total *= dim
        elif self.array_len:
            # Backward compatibility with 1D array_len
            total *= self.array_len
        
        return total


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
    required_params: int = 0  # params without defaults


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
    required_params: int = 0  # params without defaults


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

