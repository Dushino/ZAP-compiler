byte result @40000 = 0

proc main()
    byte x = 30
    byte y = 20
    word x1 = $1030

    if x != y then
        result = 1
    endif

    if x1 != x then
        result = result + $10
    endif
end
