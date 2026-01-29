byte result @40000 = 0

proc main()
    byte a = $3c
    byte b = $0f

    byte orv  = a | b     ; $3f
    byte xorv = a ^ b     ; $33
    byte notv = ~a        ; $c3
    byte shl  = b << 1    ; $1e
    byte shr  = a >> 2    ; $0f

    result = orv + xorv + notv + shl + shr   ; aggregated byte math -> $62
end
