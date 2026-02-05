byte result @40000 = 0
byte x @40001 = 1 ; global x

proc main()
    byte x = 5 @40002; local shadows global
    result = x ; expect 5 (local)
end
