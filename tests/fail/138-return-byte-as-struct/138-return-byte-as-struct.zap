; Return scalar where struct expected — must fail
struct Point
    byte x
    byte y
end

func Point bad()
    return 42
end

proc main()
    Point p = bad()
end
