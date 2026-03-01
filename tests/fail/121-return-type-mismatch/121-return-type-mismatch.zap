func byte bad()
    return $0100 ; 0x100 is word-sized, should trigger mismatch for BYTE return type
end

proc main()
    byte rv = bad()
end
