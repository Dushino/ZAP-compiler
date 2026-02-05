byte result @40000 = 0

func byte add(byte x = 2, byte y = 3) 
    return x + y
end

proc main()
    byte a = add()      ; uses defaults 2+3=5
    byte b = add(4)     ; uses 4+3=7
    result = a + b      ; expect 12
end
