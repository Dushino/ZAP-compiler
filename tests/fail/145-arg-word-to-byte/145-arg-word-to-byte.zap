; WORD argument to BYTE parameter must fail — use LOW() or HIGH()
proc take_byte(byte x)
end

word w = $1234

proc main()
    take_byte(w)
end
