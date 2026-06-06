; Test pure-asm func:
;   - #asm modifier works on func declarations
;   - Parameter name equates are emitted before the raw ASM body
;   - No return sequence is emitted by the compiler (rts in assembly body)
;   - Semantic check for missing RETURN is suppressed for #asm funcs
;   - Return value in A register per ZAP calling convention
;   - Result stored to fixed absolute address so it is stable across all variants

byte result @ $4200

func byte add_bytes(byte a, byte b) #asm
    clc
    lda _ADD_BYTES$A
    adc _ADD_BYTES$B
    rts
end

proc main()
    result = add_bytes(3, 4)
end
