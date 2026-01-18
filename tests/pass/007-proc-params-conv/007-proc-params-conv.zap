; procedure parameter type conversions

byte result1 @40000
byte result2 @40002
byte result3 @40004
byte result4 @40006
word result5 @40008
word result6 @40010


; takes byte param, assigns to local word
proc proc_byte_to_word(byte x)
    word local_word
    local_word = x
    result1 = local_word
end

; takes word param, assigns to local byte
proc proc_word_to_byte(word x)
    byte local_byte
    local_byte = x
    result2 = local_byte
end

; takes byte param, passes to word param
proc proc_byte_param(byte b)
    proc_word_to_byte(b)
end

; takes word param, passes to byte param
proc proc_word_param(word w)
    proc_byte_to_word(w)
end

; stores word param to byte result
proc store_word_as_byte(word x)
    result3 = x
end

; stores byte param to word result
proc store_byte_as_word(byte x)
    result5 = x
end


proc main()
    result1 = 0
    result2 = 0
    result3 = 0
    result4 = 0
    result5 = 0
    result6 = 0
    
    ; Test 1: byte to word conversion
    proc_byte_to_word(42)
    
    ; Test 2: word to byte conversion
    proc_word_to_byte(300)
    
    ; Test 3: byte param to word param
    proc_byte_param(50)
    
    ; Test 4: word param to byte param
    proc_word_param(512)
    
    ; Test 5: word stored as byte
    store_word_as_byte(258)
    
    ; Test 6: byte stored as word
    store_byte_as_word(99)
end
