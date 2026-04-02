
# The author of this software stands in solidarity with 🇺🇦 Ukraine. 
# We believe in a world where international borders are respected and human rights are upheld. 
# We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


"""jump_threading.py — Jump-chain simplification pass for ZAP compiler output.

Eliminates redundant branches and trivial jump chains in the generated assembly:

  * ``JMP L`` where ``L`` is the very next line → remove the jump
  * ``JMP L1`` where ``L1:`` is immediately followed by ``JMP L2`` → rewrite
    as ``JMP L2`` (one-level threading)
  * ``BEQ L ; JMP L`` → collapse to ``JMP L``
  * ``ORA X ; JMP L`` → collapse to ``JMP L`` (legacy pattern, kept for safety)
  * ``RTS`` followed by (labels/comments) then ``RTS`` → drop the first ``RTS``

Usage in the pipeline (compiler_pipeline.py)
---------------------------------------------
    from jump_threading import jump_threading
    from label_cleanup import cleanup_labels
    cg.code = jump_threading(cg.code)   # thread redundant jump chains
    cg.code = cleanup_labels(cg.code)   # remove labels made unreferenced by threading
"""

import re

JMP_RE: re.Pattern[str] = re.compile(r'^\s*JMP\s+(\w+)', re.IGNORECASE)
LABEL_RE: re.Pattern[str] = re.compile(r'^(\w+):')


def jump_threading(lines: list[str]) -> list[str]:
    """Simplify jump chains and trivial branches in assembly output."""

    # Build label → line-index map for O(1) target look-up.
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
        # (legacy pattern left over from early codegen; kept defensively)
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

        # JMP L1 where L1 is immediately next, or L1 immediately jumps to L2.
        m: re.Match[str] | None = JMP_RE.match(line)
        if m:
            target: str = m.group(1)

            if target in label_pos:
                tgt_idx = label_pos[target]

                # Jump to the very next line → redundant; drop it.
                if tgt_idx == i + 1:
                    i += 1
                    continue

                # JMP L1 → L1: JMP L2 → rewrite as JMP L2 (one level of threading).
                next_line = lines[tgt_idx + 1] if tgt_idx + 1 < len(lines) else ""
                m2: re.Match[str] | None = JMP_RE.match(next_line)
                if m2:
                    new_target: str = m2.group(1)
                    out.append(f"\tJMP {new_target}")
                    i += 1
                    continue

        # RTS followed by (labels/comments/blanks) then RTS → drop the first RTS.
        # The fall-through will reach the second RTS, so the first is redundant.
        if line.strip().upper() == "RTS":
            j = i + 1
            while j < len(lines):
                s = lines[j].strip()
                if not s or s.startswith(";") or LABEL_RE.match(s):
                    j += 1
                    continue
                break
            if j < len(lines) and lines[j].strip().upper() == "RTS":
                # Skip the first RTS — fall-through reaches the second one
                i += 1
                continue

        out.append(line)
        i += 1

    return out
