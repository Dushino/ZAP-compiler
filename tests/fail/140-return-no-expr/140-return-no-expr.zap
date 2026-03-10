; Return without expression in function — must fail
func byte bad()
    return
end

proc main()
    byte r = bad()
end
