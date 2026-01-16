; declaring local and global vars

byte var1
word var2

; no parameters
proc proc1()
    byte var1
    word var2
    
end

; one parameter
proc proc2(byte a1)
    byte var1
    word var2
end

; more parameters
proc proc3(byte a1, word a2, byte ^a3)
    byte var1
    word var2

end

; main -----------------------------------------
proc main()
    byte var1
    word var2    
end

