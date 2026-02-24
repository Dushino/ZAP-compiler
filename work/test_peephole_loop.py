import sys

def mock_parse_imm(operand):
    if not operand.startswith("#"): return None
    v = operand[1:]
    if v.startswith("$"): return int(v[1:], 16)
    return int(v, 10)

lines = [
    "\tLDY #0",
    "\tLDA (_CURPTR),Y",
    "\tORA #$80",
    "\tLDY #0",
    "\tSTA (_CURPTR),Y"
]

for i, line in enumerate(lines):
    line_stripped = line.strip()
    line_upper = line_stripped.upper()
    if line_upper.startswith("LDX #") or line_upper.startswith("LDY #"):
        load_instr = line_stripped.split(';')[0].strip().upper()
        imm1 = mock_parse_imm(load_instr.split(maxsplit=1)[1])
        print(f"Index {i}: {load_instr} => parsed {imm1}")

