proc main()
    byte x = 5
    word ^p = @x      ; Type mismatch: WORD pointer to BYTE variable
    byte y = p^
end
