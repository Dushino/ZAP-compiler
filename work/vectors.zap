; vectors.zap
; vectors for reset, nmi, irq, brk
.module "vectors.zap"

proc vectors() #keep #asm #NOEXPORT
    .segment "VECTORS"
    .word _NMI_HANDLER  ; NMI vector
    .word _RESET_HANDLER  ; Reset vector
    .word _IRQ_HANDLER  ; IRQ/BRK vector

;    .segment "FONT"  ; Ensure the rest of the code is in the correct segment
;    .incbin "../fonts/font.bin"
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


