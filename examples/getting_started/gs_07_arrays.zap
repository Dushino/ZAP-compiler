; Example: gs_07_arrays.zap
; Source: GETTING_STARTED.md, section "Arrays" (lines 711-781)
;
; Demonstrates: array declaration, access, loops, strings, high score table
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


byte arr[5] = {10, 20, 30, 40, 50}
byte data[256]
byte greeting[] = "Hello"
byte scores[] = {100, 85, 60}
byte i

proc initialize_array()
    for i = 0 to 255
        data[i] = i
    end
end

proc sum_array()
    byte sum = 0
    for i = 0 to 10
        sum = sum + data[i]
    end
end

proc add_score(byte new_score)
    if new_score > scores[0]
        scores[2] = scores[1]
        scores[1] = scores[0]
        scores[0] = new_score
    end
end

proc main()
    ; All locals declared first (ZAP rule)
    byte first = arr[0]            ; 10
    byte third = arr[2]            ; 30
    byte first_char = greeting[0]  ; 'H' = 72
    byte second_ch = greeting[1]   ; 'e' = 101

    ; Access array elements
    arr[1] = 99             ; Change second element

    initialize_array()
    sum_array()
    add_score(110)
end
