.define FEATURE

byte result @40000 = 0

.ifdef FEATURE
proc main()
    result = 1
end
.endif
