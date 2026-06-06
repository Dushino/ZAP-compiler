; Test pure-asm proc:
;   - #asm modifier makes the entire body raw assembly (no prologue/epilogue/RTS)
;   - Modifiers after #asm (#NOEXPORT, #KEEP) must not appear in the emitted body

proc NMI_HANDLER() #keep #asm #NOEXPORT
    ; NMI handler stub
    rti
end

proc IRQ_HANDLER() #keep #asm
    rti
end

proc main()
end
