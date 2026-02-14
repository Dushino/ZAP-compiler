from dataclasses import dataclass
from enum import Enum, auto
from symbols import SemType


class ExprKind(Enum):
    """Classify expression result as value, address, or lvalue."""
    VALUE = auto()
    ADDR = auto()
    LVALUE = auto()


@dataclass(frozen=True)
class ExprType:
    """Typed expression result with semantic type and value category."""
    sem_type: SemType     # byte / word / pointer
    kind: ExprKind        # VALUE / ADDR / LVALUE


