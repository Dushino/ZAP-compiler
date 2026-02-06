import re

LABEL_RE: re.Pattern[str] = re.compile(r'^(\w+):')
JUMP_RE: re.Pattern[str] = re.compile(r'\b(JMP|JSR|BEQ|BNE|BCC|BCS|BRA)\s+(\w+)\b')
# References to labels in immediates like LDA #<LABEL or LDX #>LABEL
IMM_LO_RE: re.Pattern[str] = re.compile(r'#<\s*(\w+)')
IMM_HI_RE: re.Pattern[str] = re.compile(r'#>\s*(\w+)')
# Comment-based exports emitted by the compiler to avoid adding .export directives
ZAP_EXPORT_RE: re.Pattern[str] = re.compile(r';\s*ZAP_EXPORTS\s+(.+)', re.IGNORECASE)

def cleanup_labels(lines: list[str]) -> list[str]:
    # Runtime math routines should always be kept even if not referenced
    keep_always: set[str] = {
        "MUL8", "MUL16_8", "MUL16",
        "DIV8", "DIV16_8", "DIV8_16", "DIV16",
        "MOD8", "MOD16_8", "MOD8_16", "MOD16",
    }
    # 1) zjisti všechny cíle skoků a datové reference
    used = set()
    for line in lines:
        m: re.Match[str] | None = JUMP_RE.search(line)
        if m:
            used.add(m.group(2))
        m2: re.Match[str] | None = IMM_LO_RE.search(line)
        if m2:
            used.add(m2.group(1))
        m3: re.Match[str] | None = IMM_HI_RE.search(line)
        if m3:
            used.add(m3.group(1))
        # Compiler comment-based exports (preferred)
        m: re.Match[str] | None = ZAP_EXPORT_RE.search(line)
        if m:
            exports: str = m.group(1)
            for sym in re.split(r'[ ,]+', exports.strip()):
                if sym:
                    used.add(sym)

    out = []
    i = 0
    while i < len(lines):
        line: str = lines[i]

        m: re.Match[str] | None = LABEL_RE.match(line.strip())
        if m:
            label: str = m.group(1)

            # Keep selected runtime labels unconditionally
            if label in keep_always:
                out.append(line)
                i += 1
                continue

            # Preserve variable declarations (contain .res, .byte, =, etc.)
            if '.res' in line or '.byte' in line or '=' in line:
                out.append(line)
                i += 1
                continue

            # Preserve labels that immediately precede data directives
            if i + 1 < len(lines):
                next_line: str = lines[i + 1].strip()
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
                next_line: str = lines[i + 1].strip()
                if LABEL_RE.match(next_line):
                    if label not in used:
                        i += 1
                        continue

        out.append(line)
        i += 1

    return out

