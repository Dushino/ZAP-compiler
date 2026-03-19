; Test: zero page overflow detected via -cfg linker config
; The tiny_zp.cfg defines ZP starting at $FE (only 2 bytes available)
proc main()
    word a, b
    a = 1
    b = a * 2
end
