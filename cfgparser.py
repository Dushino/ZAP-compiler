"""Parser for ld65 linker configuration files.

Extracts memory area definitions (start, size) and segment-to-memory mappings
so the ZAP compiler can automatically determine zero-page budget from the
target platform's linker config.
"""

import re
from typing import Optional


class CfgParseError(Exception):
    """Raised when the linker config file cannot be parsed."""
    pass


def parse_ld65_cfg(filepath: str) -> dict:
    """Parse an ld65 linker config file and return structured data.

    Returns a dict with:
        'memory': {name: {'start': int|None, 'size': int|None, ...}, ...}
        'segments': {name: {'load': str, 'type': str, ...}, ...}
        'zp_start': int|None   — resolved start address of ZP memory area
        'zp_size':  int|None   — resolved size of ZP memory area
    """
    try:
        with open(filepath, encoding='utf-8-sig') as f:
            text = f.read()
    except FileNotFoundError:
        raise CfgParseError(f"Linker config file not found: {filepath}")
    except Exception as e:
        raise CfgParseError(f"Cannot read linker config file '{filepath}': {e}")

    # Strip comments (# ... to end of line, but not inside quotes)
    text = _strip_comments(text)

    memory = _parse_block(text, "MEMORY")
    segments = _parse_block(text, "SEGMENTS")

    # Resolve: find which memory area the ZEROPAGE segment loads from
    zp_start = None
    zp_size = None

    zp_mem_name = None
    for seg_name, seg_attrs in segments.items():
        if seg_name.upper() == "ZEROPAGE":
            zp_mem_name = seg_attrs.get("load")
            break

    if zp_mem_name and zp_mem_name in memory:
        mem = memory[zp_mem_name]
        zp_start = mem.get("start")
        zp_size = mem.get("size")

    return {
        "memory": memory,
        "segments": segments,
        "zp_start": zp_start,
        "zp_size": zp_size,
    }


def _strip_comments(text: str) -> str:
    """Remove # comments from ld65 config text, preserving quoted strings."""
    result = []
    for line in text.split('\n'):
        # Simple approach: find # not inside quotes
        in_quote = False
        for i, ch in enumerate(line):
            if ch == '"':
                in_quote = not in_quote
            elif ch == '#' and not in_quote:
                line = line[:i]
                break
        result.append(line)
    return '\n'.join(result)


def _parse_block(text: str, block_name: str) -> dict:
    """Parse a named block (MEMORY, SEGMENTS) from ld65 config text.

    Returns {entry_name: {attr: value, ...}, ...}.
    """
    # Find block: BLOCK_NAME { ... }
    pattern = re.compile(
        rf'\b{block_name}\s*\{{([^}}]*)\}}',
        re.IGNORECASE | re.DOTALL
    )
    match = pattern.search(text)
    if not match:
        return {}

    body = match.group(1)
    entries = {}

    # Split on semicolons to get individual entries
    for entry_text in body.split(';'):
        entry_text = entry_text.strip()
        if not entry_text:
            continue

        # Entry format: NAME: attr = val, attr = val, ...
        colon_pos = entry_text.find(':')
        if colon_pos < 0:
            continue

        name = entry_text[:colon_pos].strip()
        attrs_text = entry_text[colon_pos + 1:]

        attrs = {}
        # Parse comma-separated key=value pairs
        for part in attrs_text.split(','):
            part = part.strip()
            if not part:
                continue
            eq_pos = part.find('=')
            if eq_pos < 0:
                continue
            key = part[:eq_pos].strip().lower()
            val = part[eq_pos + 1:].strip()

            # Try to resolve as integer
            resolved = _try_resolve_int(val)
            if resolved is not None:
                attrs[key] = resolved
            else:
                # Store as string (strip quotes if present)
                attrs[key] = val.strip('"')

        entries[name] = attrs

    return entries


def _try_resolve_int(val: str) -> Optional[int]:
    """Try to resolve a value as an integer.

    Handles: $XXXX (hex), 0xXXXX (hex), decimal.
    Returns None for expressions containing symbols like %S.
    """
    val = val.strip()

    # Skip expressions with ld65 symbols (%S, %O, etc.)
    if '%' in val:
        return None

    # Skip expressions with arithmetic on unresolvable parts
    # But handle simple $XXXX - $YYYY arithmetic
    if '-' in val and not val.startswith('-'):
        parts = val.split('-')
        if len(parts) == 2:
            left = _try_resolve_int(parts[0])
            right = _try_resolve_int(parts[1])
            if left is not None and right is not None:
                return left - right
        return None

    if '+' in val:
        parts = val.split('+')
        if len(parts) == 2:
            left = _try_resolve_int(parts[0])
            right = _try_resolve_int(parts[1])
            if left is not None and right is not None:
                return left + right
        return None

    # $XXXX hex
    m = re.match(r'^\$([0-9a-fA-F]+)$', val)
    if m:
        return int(m.group(1), 16)

    # 0xXXXX hex
    if val.lower().startswith('0x'):
        try:
            return int(val, 16)
        except ValueError:
            return None

    # Plain decimal
    try:
        return int(val)
    except ValueError:
        return None
