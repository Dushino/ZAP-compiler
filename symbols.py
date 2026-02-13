from dataclasses import dataclass
from typing import Iterator, Optional, Protocol, List
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
    # Port modifiers on the field: None = unspecified, True/False explicit
    is_port: bool = False
    port_rd: Optional[bool] = None
    port_wr: Optional[bool] = None

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
    # Optional default port modifiers for this struct type
    is_port_default: bool = False
    port_rd_default: Optional[bool] = None
    port_wr_default: Optional[bool] = None

    def get_field(self, field_name: str) -> Optional[StructFieldInfo]:
        """Get field by name"""
        for f in self.fields:
            if f.name.upper() == field_name.upper():
                return f
        return None


class StructRegistry:
    """Registry for struct definitions"""
    def __init__(self) -> None:
        self._structs: dict[str, StructInfo] = {}

    def define(self, struct_info: StructInfo, node=None) -> None:
        """Register a struct definition. Optional `node` can be provided so the raised
        SemanticError carries source context when appropriate."""
        if struct_info.name.upper() in self._structs:
            # Prefer to attach provided node (if caller has it); otherwise keep None so
            # callers can catch/wrap and attach their own context.
            raise SemanticError(f"Struct '{struct_info.name}' already defined", node=node)
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
        base_lower: str = self.base.lower() if isinstance(self.base, str) else ""
        if base_lower == "byte":
            return 1
        if base_lower == "word":
            return 2
        # Unknown type encountered during width computation - report as semantic error
        raise SemanticError(f"Unknown type: {self.base}", node=None)
    
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
    port_rd: bool = False           # #RD - port readable
    port_wr: bool = False           # #WR - port writable
    # Declaration modifiers
    is_keep: bool = False           # #KEEP - don't dead-strip this symbol
    noexport: bool = False          # #NOEXPORT - do not export this symbol from .module
    export: bool = False            # #EXPORT - force export even from non-module
    # Optional shared storage slot for local sharing
    shared_slot: str | None = None
    # ZP prioritization: frequency score for allocation ordering (higher = more important for ZP)
    zp_priority: int = 0            # Loop-weighted frequency score for ZP allocation

    def asm_name(self) -> str:
        """Return assembly name: _NAME for globals, _PROC_NAME for locals."""
        if self.shared_slot:
            return self.shared_slot
        if self.proc_name:
            return f"_{self.proc_name}_{self.name}"
        return f"_{self.name}"
    
    def get_total_array_size(self) -> int:
        """Calculate total size in bytes for array (including element type width)"""
        if not self.is_array:
            return 0
        
        # Get element size based on type
        element_width: int = self.type.width
        
        # Multiply by all dimension sizes
        total: int = element_width
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
    def __init__(self) -> None:
        self._symbols: dict[str, Symbol] = {}
        # Registry for enum definitions: enum_name -> {'base': 'BYTE'|'WORD', 'members': {NAME: value}}
        self._enums: dict[str, dict] = {}
        # Name of the owning procedure for local symbol tables (empty for globals)
        self._proc_name: str = ""

    @staticmethod
    def _key(name: str) -> str:
        return name.upper() if isinstance(name, str) else name

    def define(self, sym: Symbol, node=None) -> None:
        key = self._key(sym.name)
        if key in self._symbols:
            raise SemanticError(f"Variable '{sym.name}' already defined", node=node)
        
        # Constraint: Pointer arrays must fit in ZEROPAGE (max 255 bytes) for Y-indexed indirect addressing
        if sym.is_array and sym.type.is_pointer:
            total_size = sym.get_total_array_size()
            if total_size > 255:
                raise SemanticError(
                    f"Pointer array '{sym.name}' exceeds maximum size of 255 bytes (got {total_size} bytes). "
                    f"Pointer arrays must fit in ZEROPAGE for efficient Y-indexed indirect addressing.",
                    node=node
                )
        
        self._symbols[key] = sym

    def lookup(self, name: str) -> Symbol:
        return self._symbols[self._key(name)]

    def __iter__(self) -> Iterator[Symbol]:
        return iter(self._symbols.values())


class SymbolLookup(Protocol):
    def lookup(self, name: str) -> Symbol: ...


@dataclass
class ProcSymbol:
    name: str
    param_count: int = 0
    required_params: int = 0  # params without defaults
    owner_file: str | None = None    # file where this proc was defined
    exported: bool = True            # whether this proc is visible outside its owner file


class ProcTable:
    def __init__(self) -> None:
        # Map name -> list of ProcSymbol (allow same name in different modules if not exported)
        self._procs: dict[str, list[ProcSymbol]] = {}

    def define(self, p: ProcSymbol, node=None) -> None:
        # Ensure no duplicate definitions within same owner
        lst: List[ProcSymbol] = self._procs.setdefault(p.name, [])
        for existing in lst:
            if existing.owner_file == p.owner_file:
                raise SemanticError(f"Procedure '{p.name}' already defined", node=node)
            # If both are exported, that's a global conflict
            if existing.exported and p.exported:
                raise SemanticError(f"Procedure '{p.name}' already defined", node=node)
        lst.append(p)

    def lookup(self, name: str, caller_file: str | None = None, node=None) -> ProcSymbol:
        """Lookup a procedure symbol by name.
        If multiple candidates exist, prefer one defined in caller_file. Otherwise prefer an exported symbol.
        If the found symbol is not exported and caller_file is different, raises SemanticError.
        """
        if name not in self._procs:
            raise SemanticError(f"Undefined procedure '{name}'", node=node)
        candidates: List[ProcSymbol] = self._procs[name]
        # Prefer candidate defined in caller_file
        if caller_file is not None:
            for c in candidates:
                if c.owner_file == caller_file:
                    return c
        # Otherwise, look for exported candidates
        exported: List[ProcSymbol] = [c for c in candidates if c.exported]
        if len(exported) == 1:
            return exported[0]
        if len(exported) > 1:
            raise SemanticError(f"Procedure '{name}' already defined", node=node)
        # No exported candidate - procedure exists but is internal to some module(s)
        raise SemanticError(f"Undefined procedure '{name}'", node=node)


class ScopedSymbolTable:
    def __init__(self, parent: SymbolTable) -> None:
        self.parent: SymbolTable = parent
        self.local = SymbolTable()

    def lookup(self, name: str) -> Symbol:
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
    def __init__(self) -> None:
        self._funcs: dict[str, FuncSymbol] = {}

    def define(self, f: FuncSymbol, node=None) -> None:
        if f.name in self._funcs:
            raise SemanticError(f"Function '{f.name}' already defined", node=node)
        self._funcs[f.name] = f

    def lookup(self, name: str, node=None) -> FuncSymbol:
        try:
            return self._funcs[name]
        except KeyError:
            raise SemanticError(f"Undefined function '{name}'", node=node)

