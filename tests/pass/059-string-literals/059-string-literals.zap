byte result1 @40000 = 0
byte result2 @40001 = 0

proc main()
    byte str1[15] = "ZAPA"
    byte str2[4] = "ZAP"
    
    result1 = str1[0]  ; Expect 'Z' (90)
    result2 = str2[1]  ; Expect 'A' (65)
end
