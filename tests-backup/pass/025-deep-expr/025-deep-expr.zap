; deep expresssion


proc main()
    byte result = ((1 + 2) * (3 + 4)) - ((5 - 2) * 2)   ; 3 * 7 - 3 * 2 = 21 - 6 = 15
    byte scr @40000

    if ((result > 5) && (result < 20)) || (result == 0)
        result = 1
    end
    scr = result
end