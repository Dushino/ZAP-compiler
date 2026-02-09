enum word Big
    A = 300
    B
    C = 65535
END

const word w1 = Big.A
const word w2 = Big.C
const word w3 = Big.A
const word w4 = Big.A

proc main()
    word x @40000 = Big.B
    word y @40002 = Big.A
    word z @40004 = Big.C
end
