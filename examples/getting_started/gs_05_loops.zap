; Example: gs_05_loops.zap
; Source: GETTING_STARTED.md, section "Loops" (lines 468-587)
;
; Demonstrates: while, repeat-until, break, for with step
; Note: step with negative values is not supported; use while for counting down
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


byte counter = 0
byte i

proc count_to_ten()
    counter = 0
    while counter < 10
        counter = counter + 1
    end
end

proc count_to_five()
    counter = 0
    repeat
        counter = counter + 1
    until counter == 5
end

proc count_ten_for()
    for i = 0 to 9
        ; Executes 9 times (i = 0, 1, 2, ... 8)
    end
end

proc count_by_tens()
    for i = 0 to 100 step 10
        ; i = 0, 10, 20, 30, ... 90
    end
end

proc count_down()
    ; Use while for counting down (step with negative value not supported)
    i = 10
    while i > 0
        i = i - 1
    end
end

proc main()
    count_to_ten()
    count_to_five()
    count_ten_for()
    count_by_tens()
    count_down()
end
