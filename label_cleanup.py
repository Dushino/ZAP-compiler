
# The author of this software stands in solidarity with 🇺🇦 Ukraine. 
# We believe in a world where international borders are respected and human rights are upheld. 
# We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


"""label_cleanup.py — Unused-label removal pass for ZAP compiler output.

Scans the generated assembly for labels that are never the target of any
branch, jump, or immediate-address reference and removes them.  Labels that
must be kept unconditionally are:

* Runtime math/shift/copy routines (``MUL8``, ``DIV16``, ``LSHIFT32``, …)
* Any label that precedes a data directive (``.byte``, ``.word``)
* Variable/constant declarations (lines containing ``.res``, ``.byte``, ``=``)
* Labels exported via the ``; ZAP_EXPORTS name, …`` compiler comment

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
# Compiler comment that exports a list of labels without emitting .export directives.
ZAP_EXPORT_RE: re.Pattern[str] = re.compile(r';\s*ZAP_EXPORTS\s+(.+)', re.IGNORECASE)


def cleanup_labels(lines: list[str]) -> list[str]:
    """Strip unused labels while preserving exported, data, and runtime labels.

    Two-pass algorithm:
      Pass 1 — collect every referenced label name into ``used``.
      Pass 2 — emit lines, silently dropping label-only lines whose name is
               not in ``used`` (unless the label must be kept unconditionally).
    """
    # Runtime math and shift routines must always be kept, even if the linker
    # would resolve them, because they may be called from inline ASM blocks.
    keep_always: set[str] = {
        "MUL8", "MUL16_8", "MUL16",
        "DIV8", "DIV16_8", "DIV8_16", "DIV16",
        "MOD8", "MOD16_8", "MOD8_16", "MOD16",
        "LSHIFT32", "RSHIFT32",
        "COPY_BYTES", "COPY_BYTES16",
    }

    # Pass 1: collect all referenced labels.
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
        # Compiler comment-based export list (preferred over .export directives).
        m4: re.Match[str] | None = ZAP_EXPORT_RE.search(line)
        if m4:
            exports: str = m4.group(1)
            for sym in re.split(r'[ ,]+', exports.strip()):
                if sym:
                    used.add(sym)

    # Pass 2: emit lines, dropping unreferenced label-only lines.
    out: list[str] = []
    i = 0
    while i < len(lines):
        line: str = lines[i]

        m: re.Match[str] | None = LABEL_RE.match(line.strip())
        if m:
            label: str = m.group(1)

            # Always keep runtime-routine labels.
            if label in keep_always:
                out.append(line)
                i += 1
                continue

            # Keep variable/constant declarations (contain .res, .byte, or =).
            if '.res' in line or '.byte' in line or '=' in line:
                out.append(line)
                i += 1
                continue

            # Keep labels that immediately precede a data directive on the
            # next line (e.g. ROM tables: LABEL: \n .byte …).
            if i + 1 < len(lines):
                next_stripped: str = lines[i + 1].strip()
                if next_stripped.startswith('.byte') or next_stripped.startswith('.word'):
                    out.append(line)
                    i += 1
                    continue

            # Drop the label if it is never the target of any branch/jump.
            if label not in used:
                i += 1
                continue

            # When two used labels appear on consecutive lines, keep both.
            # (No drop needed here — label is in used, so it falls through to out.append.)

        out.append(line)
        i += 1

    return out
