; Minimal test: struct field in LOR condition
byte result @$0200 = 0

struct Rec
    byte flag
end
Rec r

proc main()
    r.flag = 1
    if r.flag || 0
        result = 1
    end
end
