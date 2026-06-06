; Test pure-asm proc with parameters:
;   - Parameter name equates are emitted before the raw ASM body
;   - Raw assembly can reference ZAP-generated symbols like _PROC$PARAMNAME
;   - No RTS is emitted after the ASM block (it is in the asm body)
;   - Store to fixed absolute address so result is stable across all variants

proc my_poke(byte val) #asm
    lda _MY_POKE$VAL
    sta $4200
    rts
end

proc main()
    my_poke($42)
end
