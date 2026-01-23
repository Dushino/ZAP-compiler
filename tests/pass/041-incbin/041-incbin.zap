BYTE result @40000 = 0

PROC setfont()

    ASM
    .segment "FONT"
    MYFONT:
    .incbin "font.fnt"
    .segment "CODE"
        lda #>MYFONT
        sta $02F4   ; set font high byte; CHBAS
    END
END

PROC main()
    setfont()
    result = 42
END
