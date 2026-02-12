byte result @40000 = 0

proc main()
    byte a = 10
    byte b = 20
    ; Test: !(a < b) = !(true) = false = 0
    if !(a < b) then
        result = 1
    else
        result = 0
    endif
end
