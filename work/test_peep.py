import sys

code = [
    "\tLDY #0",
    "\tLDA (_CURPTR),Y",
    "\tORA #$80",
    "\tLDY #0",
    "\tSTA (_CURPTR),Y"
]

def _parse_imm(operand: str) -> int | None:
    if not operand.startswith("#"):
        return None
    value = operand[1:]
    try:
        if value.startswith("$"):
            return int(value[1:], 16)
        return int(value, 10)
    except ValueError:
        return None

def _clobbers_y(line: str) -> bool:
    op = line.split(maxsplit=1)[0].upper() if line else ""
    return op in {"LDY", "INY", "DEY", "TAY", "TYA", "PLY"}

optimized = []
i = 0
while i < len(code):
    line = code[i]
    line_stripped = line.strip()
    line_upper = line_stripped.upper()
    
    if line_upper.startswith("LDX #") or line_upper.startswith("LDY #"):
        load_instr = line_stripped.split(';')[0].strip().upper()
        reg = "X" if load_instr.startswith("LDX") else "Y"
        imm1 = _parse_imm(load_instr.split(maxsplit=1)[1])
        
        if imm1 is not None:
            j = i + 1
            found_match = False
            intervening_safe = True
            match_idx = -1
            
            while j < len(code) and j <= i + 4:
                look_line = code[j].strip()
                look_u = look_line.split(';')[0].strip().upper()
                
                if not look_u:
                    j += 1
                    continue
                if look_u.endswith(":"):
                    intervening_safe = False
                    break
                
                if look_u.startswith(f"LD{reg} #"):
                    imm2 = _parse_imm(look_u.split(maxsplit=1)[1])
                    if imm2 is not None and imm1 == imm2:
                        found_match = True
                        match_idx = j
                        break
                    else:
                        intervening_safe = False
                        break
                
                clobbers = False if reg == "X" else _clobbers_y(look_u)
                if clobbers:
                    intervening_safe = False
                    break
                    
                j += 1
            
            if found_match and intervening_safe:
                for k in range(i, match_idx):
                    optimized.append(code[k])
                i = match_idx + 1
                continue
    optimized.append(code[i])
    i += 1

for line in optimized:
    print(line)

