; declaring local and global vars

byte var1
word var2

byte ^scr = 40000   ; screen address in Atari with BASIC enabled


proc putc(byte ^ptr, byte chcode)
    ptr^ = chcode
    ptr = ptr + 1
end


; no parameters
proc proc1()
    byte var1
    word var2
    putc(scr, 1)
end

; one parameter
proc proc2(byte a1)
    byte var1
    word var2
    putc(scr, 2)
end

; more parameters
proc proc3(byte a1, word a2, byte ^a3, word ^a4)
    byte var1
    word var2
    putc(scr, 3)
end

; main -----------------------------------------
proc main()
    byte var1 = $a5
    word var2 = $1234
    byte ptr1^ = 40040

    ptr1^ = 16

end

