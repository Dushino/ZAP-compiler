; Example: gs_03_variables.zap
; Source: GETTING_STARTED.md, section "Working with Variables" (lines 206-346)
;
; Demonstrates: variable types, initialization, global/local, static, score tracker

; --- Variable types ---
byte health = 100       ; Character health (0-255)
word high_score = 5000  ; High score (can be > 255)
long population = 65536 ; 32-bit value (cannot fit in word)

; --- Global vs Local ---
byte game_over = 0

; --- Score tracker example ---
byte current_score = 0
byte best_score = 0

proc add_points(byte points)
    current_score = current_score + points
    if current_score > best_score
        best_score = current_score
    end
end

; --- Static variable example ---
proc counter()
    static byte count = 0
    count = count + 1
end

proc main()
    ; All locals declared first (ZAP rule)
    byte x = 10
    byte y = 20
    byte sum = x + y        ; sum = 30
    byte z = 0
    byte w = z + 10
    byte local_var = 10

    x = x + 1               ; x = 11
    y = y - 5               ; y = 15

    ; Access global
    game_over = 1

    ; Score tracker
    add_points(10)
    add_points(25)
    add_points(15)

    ; Static counter
    counter()   ; count becomes 1
    counter()   ; count becomes 2
    counter()   ; count becomes 3
end
