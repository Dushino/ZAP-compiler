import re

JMP_RE: re.Pattern[str] = re.compile(r'^\s*JMP\s+(\w+)', re.IGNORECASE)
LABEL_RE: re.Pattern[str] = re.compile(r'^(\w+):')

def jump_threading(lines: list[str]) -> list[str]:

    # mapování label -> index
    label_pos = {}
    for i, line in enumerate(lines):
        m: re.Match[str] | None = LABEL_RE.match(line)
        if m:
            label_pos[m.group(1)] = i

    out = []
    i = 0
    while i < len(lines):
        line: str = lines[i]

        # ORA X ; JMP L  -> JMP L
        if line.strip() == "ORA X":
            if i + 1 < len(lines):
                next_line: str = lines[i + 1].strip()
                if next_line.startswith("JMP "):
                    out.append("\t" + next_line)
                    i += 2
                    continue

        # BEQ L ; JMP L  -> JMP L
        if line.strip().startswith("BEQ"):
            parts: list[str] = line.strip().split()
            if len(parts) == 2:
                label: str = parts[1]
                if i + 1 < len(lines):
                    next_line: str = lines[i + 1].strip()
                    if next_line == f"JMP {label}":
                        out.append(f"\tJMP {label}")
                        i += 2
                        continue

        # JMP L1 ; L1:
        m: re.Match[str] | None = JMP_RE.match(line)
        if m:
            target: str = m.group(1)

            if target in label_pos:
                tgt_idx = label_pos[target]

                # skok na následující řádek
                if tgt_idx == i + 1:
                    i += 1
                    continue

                # JMP L1 -> L1: JMP L2
                next_line = lines[tgt_idx + 1] if tgt_idx + 1 < len(lines) else ""
                m2: re.Match[str] | None = JMP_RE.match(next_line)
                if m2:
                    new_target: str = m2.group(1)
                    out.append(f"\tJMP {new_target}")
                    i += 1
                    continue

        out.append(line)
        i += 1

    return out

def cleanup_labels(lines: list[str]) -> list[str]:
    # najdi všechny cíle skoků
    used = set()
    for l in lines:
        l: str = l.strip()
        if l.startswith(("JMP ", "BEQ ", "BNE ", "BCC ", "BCS ")):
            used.add(l.split()[1])

    out = []
    for i, l in enumerate(lines):
        if l.endswith(":"):
            label: str = l[:-1]
            if label not in used:
                continue
            # více labelů za sebou
            if i + 1 < len(lines) and lines[i + 1].strip().endswith(":"):
                continue
        out.append(l)

    return out
