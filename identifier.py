from dataclasses import dataclass
import copy
from tokenizer import *
from token_types import *
import sys

# ---------------------------------------------------------------------------------
# global variable:
# name      = name in UPPERCASE
# localName = ''        # name of PROC / FUNC this local variable belongs to
# localPIdx = 0         # index of this FUNC / PROC parameter
# localIdx  = 0         # index of this local variable in local variables list

# parameter of FUNC or PROC
# name        _PROCNAME_PARNAME in UPPERCASE
# localName = PROCNAME  # name of PROC / FUNC this local variable belongs to
# localPIdx = 1..n      # index of this FUNC / PROC parameter
# localIdx  = 0         # index of this local variable in local variables list

# local variable in FUNC or PROC
# name        _PROCNAME_PARNAME in UPPERCASE
# localName = PROCNAME  # name of PROC / FUNC this local variable belongs to
# localPIdx = 0         # index of this FUNC / PROC parameter
# localIdx  = 1..n      # index of this local variable in local variables list

@dataclass
class Identifier:
    name:       str     = ''        # name in UPPERCASE
    bytes:      int     = 0         # bytes to reserve for variable
    isPtr:      bool    = False     # true if is pointer
    ptrBytes:   int     = 0         # bytes pointer is pointing to
    isFixed:    bool    = False     # variable is on fixed memory location
    addr:       str     = ''        # memory address in its original form
    isConst:    bool    = False     # store in CODE segment
    isInit:     bool    = False     # initialize to initVal
    initVal:    str     = ''        # initial value
    isType:     bool    = False     # is part of structure definition
    typeLen:    int     = 0         # type length in Bytes
    typeName:   str     = ''        # name of structure this variable is part of
    isStruct:   bool    = False     # is structure instance
    isProc:     bool    = False     # is procedure
    isFunc:     bool    = False     # is function
    procName:   str     = ''        # name of PROC / FUNC
    localName:  str     = ''        # full name including PROC / FUNC name
    localPIdx:  int     = 0         # index of this FUNC / PROC parameter
    localIdx:   int     = 0         # index of this local variable in local variables list
    declLine:   int     = 0         # line where has been declared
    declCol:    int     = 0         # column where has been declared

    def __post_init__(self):
        # automaticky převést jméno na UPPERCASE
        self.name       = self.name.upper()  

    def _reset(self):
        self.name       = ''        # name in UPPERCASE
        self.bytes      = 0         # bytes to reserve for variable
        self.isPtr      = False     # true if is pointer
        self.ptrBytes   = 0         # bytes pointer is pointing to
        self.isFixed    = False     # variable is on fixed memory location
        self.addr       = ''        # memory address in its original form
        self.isConst    = False     # store in CODE segment
        self.isInit     = False     # initialize to initVal
        self.initVal    = ''        # Initial value
        self.isType     = False     # is part of structure definition
        self.typeLen    = 0         # type length in Bytes
        self.typeName   = ''        # name of structure this variable is part of
        self.isStruct   = False     # is structure instance
        self.isProc     = False     # is procedure
        self.isFunc     = False     # is function
        self.procName   = ''        # name of PROC / FUNC
        self.localName  = ''        # full name including PROC / FUNC name
        self.localPIdx  = 0         # index of this FUNC / PROC parameter
        self.localIdx   = 0         # index of this local variable in local variables list
        self.declLine   = 0         # line where has been declared
        self.declCol    = 0         # column where has been declared


# ---------------------------------------------------------------------------------
class Identifiers:
    _identifiers: list[Identifier]
    pos: int

    def __init__(self):
        self._identifiers = []
        self.pos = 0

    def _error(self, errtxt:str):
        print(f'IDENTIFIER ERROR: {errtxt}.', file = sys.stderr)        
        exit(1)


    def add(self, ide: Identifier) -> Identifier:
        """
        Uloží kopii identifikátoru (aby následné resetování originálu nesmazalo uloženou položku)
        Normalizuje název na UPPERCASE.
        Vrátí uložený objekt.
        """
        if not isinstance(ide, Identifier):
            raise TypeError("add expects Identifier")
        ide_copy = copy.deepcopy(ide)
        ide_copy.name = ide_copy.name.upper() if ide_copy.name is not None else ''
        self._identifiers.append(ide_copy)
        self.pos += 1
        return ide_copy
       
    def findByName(self, nm: str):
        if nm is None:
            return None
        target = nm.upper()
        return next((i for i in self._identifiers if (i.localName == target and i.isProc == False and i.isFunc == False)), None) # Fixme: filter search for PROC and FUNC names only

    def findAllByName(self, nm: str):
        if nm is None:
            return None
        target = nm.upper()
        return [i for i in self._identifiers if (i.localName == target and i.isProc == False and i.isFunc == False)]                   
        
    def findByPROCName(self, nm: str):
        if nm is None:
            return None
        target = nm.upper()
        return next((i for i in self._identifiers if (i.name == target and i.isProc == True)), None) # Fixme: filter search for PROC and FUNC names only

    def findAllByPROCName(self, nm:str):
        if nm is None:
            return None
        mn = nm.upper()        
        return [i for i in self._identifiers if (i.name == mn and i.isProc == True)]           
    
    def _peek(self, offset:int):        
        i = self.pos + offset
        if i < len(self._identifiers):
            return self._identifiers[i]
        return None

        
