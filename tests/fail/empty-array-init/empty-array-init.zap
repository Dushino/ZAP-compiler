; Test: empty array initializer must be rejected.
; byte arr[] = {} has zero elements - should raise a semantic error.

proc main()
    byte arr[] = {}
end
