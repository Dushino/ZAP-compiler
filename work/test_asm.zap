; vectors.zap
; vectors for reset, nmi, irq, brk


proc vectors() #keep #asm #NOEXPORT
    .segment "VECTORS"
    .word _NMI_HANDLER  ; NMI vector
    .word _RESET_HANDLER  ; Reset vector
    .word _IRQ_HANDLER  ; IRQ/BRK vector

    .segment "FONT"  ; Ensure the rest of the code is in the correct segment
    .incbin "../fonts/font.bin"
end


proc NMI_HANDLER() #keep #asm #NOEXPORT
    ; NMI handler code goes here
    rti
end


proc IRQ_HANDLER() #keep #asm #NOEXPORT
    ; IRQ handler code goes here
    rti
end


proc RESET_HANDLER() #keep #asm #NOEXPORT
    ; Reset handler code goes here
    jmp _MAIN  ; Jump to main function
end


func byte my_peek(word adr)  #asm
    lda _MY_PEEK$ADR
    rts
end

proc my_poke(word adr, byte value)    #asm 
    lda _MY_POKE$VALUE
    sta _MY_POKE$ADR
    rts
end



proc main() #noexport
    byte rv

    my_poke($2000, $42)  ; Example usage of my_poke to write value 0x42 to address 0x2000
    rv = my_peek($4000)
end

