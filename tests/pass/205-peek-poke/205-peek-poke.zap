; PEEK and POKE with all valid argument types

byte result
byte val = $42
word addr = $D400
byte baddr = $80
long laddr = $12345678
word wval = $1234
long lval = $12345678

proc main()
    ; --- PEEK with byte address ---
    result = PEEK(baddr)

    ; --- PEEK with word address ---
    result = PEEK(addr)

    ; --- PEEK with literal address ---
    result = PEEK($D400)
    result = PEEK($80)

    ; --- PEEK with expression address ---
    result = PEEK(addr + 1)
    result = PEEK(baddr + 2)
    result = PEEK($D400 + 3)

    ; --- PEEK with LOWW/HIGHW of long (valid: LOWW/HIGHW return WORD) ---
    result = PEEK(LOWW(laddr))
    result = PEEK(HIGHW(laddr))

    ; --- POKE with byte value ---
    POKE($D400, $42)
    POKE($D400, val)
    POKE(addr, val)
    POKE(baddr, val)

    ; --- POKE with expression address ---
    POKE(addr + 1, val)
    POKE(baddr + 2, val)
    POKE($D400 + 3, $FF)

    ; --- POKE with LOW/HIGH of word value (valid: LOW/HIGH return BYTE) ---
    POKE(addr, LOW(wval))
    POKE(addr, HIGH(wval))

    ; --- POKE with LOW/HIGH of LOWW/HIGHW of long value ---
    POKE(addr, LOW(LOWW(lval)))
    POKE(addr, HIGH(LOWW(lval)))
    POKE(addr, LOW(HIGHW(lval)))
    POKE(addr, HIGH(HIGHW(lval)))

    ; --- POKE with expression value ---
    POKE(addr, val + 1)
    POKE(addr, $42 + $10)

    ; --- PEEK used in expressions ---
    result = PEEK(addr) + 1
    result = PEEK(addr) + val
end
