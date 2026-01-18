; if - then - else result
byte result

proc main()
    byte x1     @40000 = 5
    byte result @40001 = 0

    if x1 == 5 then
        result = result + 1
    else
        result = result + 2
    endif
    
    if x1 > 3 then
        if x1 < 10 then
            result = result + 16
        endif
    endif
end
