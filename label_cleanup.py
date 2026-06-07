
# The author of this software stands in solidarity with 🇺🇦 Ukraine.
# We believe in a world where international borders are respected and human rights are upheld.
# We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


"""label_cleanup.py — Unused compiler-internal label removal pass for ZAP compiler output.

Scans the generated assembly for ``__ZAP_*`` labels that are never the target
of any branch, jump, or immediate-address reference and removes them.

Only ``__ZAP_*`` prefixed labels are compiler-generated internal labels (loop
boundaries, if/else branch targets, etc.).  All other labels — procedure/function
entry points, user ASM labels, math routines, variable declarations — are kept
unconditionally.  Labels inside ``; ASM_BLOCK_BEGIN`` … ``; ASM_BLOCK_END``
regions are never touched regardless of prefix.

Usage in the pipeline (compiler_pipeline.py)
---------------------------------------------
    from jump_threading import jump_threading
    from label_cleanup import cleanup_labels
    cg.code = jump_threading(cg.code)   # thread redundant jump chains first
    cg.code = cleanup_labels(cg.code)   # then remove labels made unreferenced
"""

import re

LABEL_RE: re.Pattern[str] = re.compile(r'^(\w+):')
# All 6502/65C02 branch and jump mnemonics, case-insensitive so that labels
# referenced from inline ASM blocks (which use lowercase) are preserved.
JUMP_RE: re.Pattern[str] = re.compile(
    r'\b(JMP|JSR|BEQ|BNE|BCC|BCS|BRA|BPL|BMI|BVC|BVS)\s+(\w+)\b',
    re.IGNORECASE,
)
# References to labels in immediates: LDA #<LABEL  or  LDX #>LABEL
IMM_LO_RE: re.Pattern[str] = re.compile(r'#<\s*(\w+)')
IMM_HI_RE: re.Pattern[str] = re.compile(r'#>\s*(\w+)')


def cleanup_labels(lines: list[str]) -> list[str]:
    """Strip unreferenced compiler-internal (``__ZAP_*``) labels.

    Only ``__ZAP_*`` labels are candidates for removal.  All other labels
    (user-defined proc/func entry points, ASM block labels, math routines,
    variable/constant declarations) are kept unconditionally.

    Two-pass algorithm:
      Pass 1 — collect every referenced ``__ZAP_*`` label name into ``used``.
      Pass 2 — emit lines, silently dropping ``__ZAP_*`` label-only lines
               whose name is not in ``used``.  Labels inside ASM blocks are
               never dropped.
    """
    # Pass 1: collect all referenced __ZAP_* labels.
    used: set[str] = set()
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

    # Pass 2: emit lines, dropping unreferenced __ZAP_* label-only lines.
    out: list[str] = []
    in_asm_block: bool = False
    for line in lines:
        stripped: str = line.strip()

        if stripped == "; ASM_BLOCK_BEGIN":
            in_asm_block = True
        elif stripped == "; ASM_BLOCK_END":
            in_asm_block = False

        if not in_asm_block:
            m: re.Match[str] | None = LABEL_RE.match(stripped)
            if m:
                label: str = m.group(1)
                # Only remove unreferenced __ZAP_* internal labels.
                if label.startswith("__ZAP_") and label not in used:
                    continue

        out.append(line)

    return out
