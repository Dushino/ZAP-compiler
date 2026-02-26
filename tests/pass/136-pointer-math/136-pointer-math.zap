byte result @40000 = 0

proc main() 
    byte byte_var @40001 = 0
    word word_var @40002 = 0
    long long_var @40004 = 0
    byte ^ptr_var @40007 = @byte_var
    word ^ptr_word @40008 = @word_var
    long ^ptr_long @40010 = @long_var

    word result_word = 0


    if ptr_long == @long_var
        byte_var = 1
    else
        byte_var = 2    
    end 

    ptr_long = ptr_long + 1
    ptr_long = 1 + ptr_long
    ptr_long = ptr_long - 1

    
    if ptr_long == @long_var + 1
        byte_var = 1
    end
    
    
    ; 1. PTR + INT and INT + PTR (with scaled steps)
    ptr_var = ptr_var + 5
    ptr_var = 5 + ptr_var

    ptr_word = ptr_word + 3  ; Should scale by 2 (sizeof WORD)
    ptr_word = 3 + ptr_word  ; Should scale by 2

    ; 2. PTR - INT
    ptr_word = ptr_word - 2  ; Should scale by 2

    ; 3. PTR - PTR (distance in elements)
    result_word = ptr_word - @word_var  ; Should divide by 2
    
    ; 4. Relational
    if ptr_word == 0
        byte_var = 1
    end

    if ptr_word > @word_var
        byte_var = 2
    end

    
    ; 5. Unary
    if !ptr_word
        byte_var = 3
    end

    
    ; 6. Loop context
    for ptr_var = @byte_var to @byte_var + 10 step 1
        result_word = result_word + 1
    end
    

    result = 1
end
