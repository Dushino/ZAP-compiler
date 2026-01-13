import re

LABEL_RE = re.compile(r'^(\w+):')
JUMP_RE = re.compile(r'\b(JMP|JSR|BEQ|BNE|BCC|BCS|BRA)\s+(\w+)\b')
# References to labels in immediates like LDA #<LABEL or LDX #>LABEL
IMM_LO_RE = re.compile(r'#<\s*(\w+)')
IMM_HI_RE = re.compile(r'#>\s*(\w+)')
EXPORT_RE = re.compile(r'\.export\s+(.+)')

def cleanup_labels(lines: list[str]) -> list[str]:
    # 1) zjisti všechny cíle skoků a datové reference
    used = set()
    for line in lines:
        m = JUMP_RE.search(line)
        if m:
            used.add(m.group(2))
        m2 = IMM_LO_RE.search(line)
        if m2:
            used.add(m2.group(1))
        m3 = IMM_HI_RE.search(line)
        if m3:
            used.add(m3.group(1))
        m4 = EXPORT_RE.search(line)
        if m4:
            exports = m4.group(1)
            for sym in re.split(r'[ ,]+', exports.strip()):
                if sym:
                    used.add(sym)

    out = []
    i = 0
    while i < len(lines):
        line = lines[i]

        m = LABEL_RE.match(line.strip())
        if m:
            label = m.group(1)

            # Preserve variable declarations (contain .res, .byte, =, etc.)
            if '.res' in line or '.byte' in line or '=' in line:
                out.append(line)
                i += 1
                continue

            # Preserve labels that immediately precede data directives
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith('.byte') or next_line.startswith('.word'):
                    out.append(line)
                    i += 1
                    continue

            # label, na který se neskáče
            if label not in used:
                i += 1
                continue

            # více labelů za sebou → ponech jen poslední, but only drop unused ones
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if LABEL_RE.match(next_line):
                    if label not in used:
                        i += 1
                        continue

        out.append(line)
        i += 1

    return out

