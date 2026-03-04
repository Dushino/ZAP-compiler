; Example: gs_02_basic_concepts.zap
; Source: GETTING_STARTED.md, section "Basic Concepts" (lines 156-202)
;
; Demonstrates: procedures, functions, variables, control flow overview

byte health = 100       ; 8-bit number (0-255)
word score = 0          ; 16-bit number (0-65535)

proc greet()
    ; Do something
end

func byte add(byte a, byte b)
    return a + b
end

proc main()
    byte x = 5
    byte result = add(x, 10)

    if health > 0
        score = score + 1
    end

    while score < 10
        score = score + 1
    end
end
