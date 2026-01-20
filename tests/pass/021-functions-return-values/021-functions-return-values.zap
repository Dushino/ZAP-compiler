func byte lo(word w)
return w
end

func word widen(byte b)
return b
end

byte result @40000 = 0

proc main()
    byte r1 = lo($12ab)       ; low byte expected $ab
    word w1 = widen(1)
    result = r1 + w1          ; $ab + 1 -> $ac
end
