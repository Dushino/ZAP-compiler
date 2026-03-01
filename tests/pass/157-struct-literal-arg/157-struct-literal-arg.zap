byte result @40000 = 0

; --- struct definitions ---

struct Pair          ; two bytes
    byte x
    byte y
end

struct WPair         ; two words
    word wx
    word wy
end

struct BW            ; mixed byte + word
    byte b
    word w
end

struct Nested        ; struct containing a Pair
    byte tag
    Pair p
end

; --- functions accepting struct parameters ---

func byte add_pair(Pair p)
    return p.x + p.y
end

func word add_wpair(WPair p)
    return p.wx + p.wy
end

func word add_bw(BW bw)
    return bw.b + bw.w
end

func byte nested_sum(Nested n)
    return n.tag + n.p.x + n.p.y
end

proc main()
    byte ba = 0
    word wa = 0

    ; --- check 1: byte struct literal as function argument ---
    ba = add_pair({10, 20})
    if ba == 30
        result = result + 1     ; 1
    end

    ; --- check 2: different values, same function ---
    ba = add_pair({100, 56})
    if ba == 156
        result = result + 1     ; 2
    end

    ; --- check 3: word struct literal as function argument ---
    wa = add_wpair({300, 400})
    if wa == 700
        result = result + 1     ; 3
    end

    ; --- check 4: mixed byte+word struct literal ---
    wa = add_bw({50, 250})
    if wa == 300
        result = result + 1     ; 4
    end

    ; --- check 5: struct literal with a zero field ---
    ba = add_pair({0, 42})
    if ba == 42
        result = result + 1     ; 5
    end

    ; --- check 6: struct literal used inline in a condition (no temp variable) ---
    if add_pair({3, 4}) == 7
        result = result + 1     ; 6
    end

    ; --- check 7: nested struct literal ({tag, {x, y}}) ---
    ba = nested_sum({1, {10, 20}})
    if ba == 31
        result = result + 1     ; 7: 1 + 10 + 20 = 31
    end
end
