; Fail test: reading a local long variable before any assignment
; Expected: SemanticError "Use of uninitialized variable 'X'"

proc main()
    long x
    long result
    result = x      ; x was never assigned
end
