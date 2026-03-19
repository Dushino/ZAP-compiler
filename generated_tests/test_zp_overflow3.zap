; Test: overflow zero page - compiler temps alone exceed budget
; Using many operations to force MATH temps into use
proc main()
    word a, b, c
    a = 1
    b = a * 2
    c = b * 3
    a = c / 4
end
