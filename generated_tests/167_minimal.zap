byte result @40000 = 0
byte barr[3] = {$AA, $BB, $CC}

proc main()
    byte ^bptr
    bptr = @barr
    (bptr + 1)^ += 1
    if barr[1] == $BC
        result = 1
    end
end
