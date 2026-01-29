byte result @40000 = 0

proc main()
    byte a = 100
    byte b = 50
    
    ; Test different operators
    byte sum = a + b        ; 150, overflow to 150 (or wraps)
    byte diff = a - b       ; 50
    byte prod = 10 * 5      ; 50
    
    result = diff           ; Store diff = 50
end
