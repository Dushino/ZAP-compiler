from dataclasses import dataclass
from enum import Enum, auto
from symbols import SemType


class ExprKind(Enum):
    VALUE = auto()
    ADDR = auto()
    LVALUE = auto()


@dataclass(frozen=True)
class ExprType:
    sem_type: SemType     # byte / word / pointer
    kind: ExprKind        # VALUE / ADDR / LVALUE


