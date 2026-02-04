byte result @40000 = 0

; Line comment should be ignored
proc main()
    byte x = 1  ; inline comment
    /* block comment
       spanning multiple lines */
    byte y = 2
    result = x + y
end
