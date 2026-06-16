; Test: byte global variable in LOR condition (no struct)
byte result @$0200 = 0
byte flag

proc main()
    flag = 1
    if flag || 0
        result = 1
    end
end
