proc helper(byte a)
    if a > 10 then
        return
    endif
    
    if a > 5 then
        return
    endif
end

proc main()
    helper(15)
    helper(7)
    helper(3)
end
