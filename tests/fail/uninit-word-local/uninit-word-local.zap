; Fail test: reading a local word variable before any assignment
; Expected: SemanticError "Use of uninitialized variable 'X'"

proc main()
    word x
    word result
    result = x      ; x was never assigned
end
