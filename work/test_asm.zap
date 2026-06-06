


proc NMI_HANDLER() #keep #asm #NOEXPORT
    ; NMI handler code goes here
    rti
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

