enum word Big {
    A = 300,
    B,
    C = 65535
}

const word w1 = A
const word w2 = C

proc main()
    word x @40000 = B
end
