; declaring local and global vars

byte gvar1
word gvar2


; no parameters
proc proc1()
    byte var1
    word var2

    var1 = 1
    var2 = 2048
    gvar1 = var1
    gvar2 = var2
end

; one parameter
proc proc2(byte a1)
    byte var1
    word var2

    var1 = 2
    var2 = 2049
    gvar1 = var1
    gvar2 = var2
end

; more parameters
proc proc3(byte a1, word a2, byte ^a3)
    byte var1
    word var2

    var1 = 3
    var2 = 2050
    gvar1 = var1
    gvar2 = var2
end

; main -----------------------------------------
proc main()
    proc1()
    proc2()
    proc3()

end

