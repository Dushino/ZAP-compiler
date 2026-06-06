


proc NMI_HANDLER() #keep #asm #NOEXPORT
    ; NMI handler code goes here
    rti
end

proc my_poke(word adr, byte value)    #asm
    lda _MY_POKE$VALUE
    sta _MY_POKE$ADR
end

proc main()
    my_poke($2000, $42)  ; Example usage of my_poke to write value 0x42 to address 0x2000
end
