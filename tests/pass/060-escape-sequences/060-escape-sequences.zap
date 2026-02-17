byte result1 @40000 = 0
byte result2 @40001 = 0

proc main()
    ; Local variables must be declared first
    byte tab = '\t'
    byte newline = '\n'
    byte cr = '\r'
    byte str[4] = "\n\t\\"

    ; Test char literals
    result1 = tab + newline
    
    ; Test string literals
    result2 = str[2] ; Expect backslash
end
