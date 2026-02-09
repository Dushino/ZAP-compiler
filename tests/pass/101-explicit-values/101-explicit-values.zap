enum byte E
    A = 1
    B
    C = 5
    D
END

const byte v = E.D

proc main()
    byte x @40000 = E.B
end
