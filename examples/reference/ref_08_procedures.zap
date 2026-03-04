; Example: ref_08_procedures.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "Procedures & Functions" (lines 1517-1752)
;
; Demonstrates: procedures, functions, parameters, return, deep copy

; --- Procedures ---
proc procedure_name()
    ; Procedure body
end

proc procedure_with_params(byte x, word y)
    ; Use parameters
end

; --- Functions ---
func byte add_one(byte x)
    return x + 1
end

func word multiply(byte a, byte b)
    return a * b
end

; --- Parameters with locals ---
proc three_params(byte x, word y, byte c)
    ; Use x, y, c
end

proc param_with_locals(byte value)
    byte temp = 0
    temp = value + 1
end

; --- Local Variables ---
proc with_locals()
    byte x = 0
    byte y = 10
    word counter2 = 0

    x = y + 1
    counter2 = counter2 + 1
end

; --- Return ---
proc early_exit(byte x)
    if x == 0
        return
    end
    ; More code
end

func byte get_value()
    byte x = 42
    return x
end

func word calculate(byte a, byte b)
    return a + b
end

; --- Parameter Passing (by value) ---
proc modify(byte x)
    x = 0           ; Modifies local copy only
end

; --- Deep Copy: Struct ---
struct Point
    byte x
    byte y
end

proc move_local(Point p)
    p.x = p.x + 1      ; Modifies local copy only
end

proc move_in_place(Point ^p)
    p^.x = p^.x + 1    ; Modifies caller's struct via pointer
end

; --- Struct Literals as Call Arguments ---
struct Pair
    byte x
    byte y
end

struct Nested
    byte tag
    Pair p
end

func byte add_pair(Pair p)
    return p.x + p.y
end

func byte nested_sum(Nested n)
    return n.tag + n.p.x + n.p.y
end

; --- Struct Function Return ---
func Point add_points(Point p1, Point p2)
    Point result = { p1.x + p2.x, p1.y + p2.y }
    return result
end

; --- Field access on function call result ---
func Point make_point(byte px, byte py)
    Point p = {0, 0}
    p.x = px
    p.y = py
    return p
end

proc main()
    ; All locals first (ZAP rule)
    byte value = 42
    byte result = 0
    word prod = 0
    byte gv = 0
    word calc = 0
    Point a = { 10, 20 }
    byte pa = 0
    byte ns = 0
    Point c = {0, 0}
    byte bx = 0
    byte by2 = 0

    procedure_name()
    procedure_with_params(5, 1000)
    result = add_one(10)           ; result = 11
    prod = multiply(5, 6)          ; prod = 30

    three_params(1, 2000, 3)
    param_with_locals(10)
    with_locals()

    early_exit(0)
    early_exit(5)
    gv = get_value()               ; 42
    calc = calculate(10, 20)       ; 30

    modify(value)                  ; value still 42

    ; Deep copy
    move_local(a)                  ; a still {10, 20}
    move_in_place(@a)              ; a now {11, 20}

    ; Struct literals
    pa = add_pair({10, 20})        ; 30
    ns = nested_sum({1, {10, 20}}) ; 31

    ; Struct return
    c = add_points({5, 10}, {15, 20})  ; c = {20, 30}

    ; Field access on return
    bx = make_point(10, 20).x     ; bx = 10
    by2 = make_point(10, 20).y    ; by2 = 20
end
