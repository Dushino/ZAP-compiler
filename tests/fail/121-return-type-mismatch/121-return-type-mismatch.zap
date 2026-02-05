func byte bad()
    return $0100 ; 0x100 is word-sized, should trigger mismatch for BYTE return if not allowed
end

func word badw()
    return $10000 ; 0x10000 is too big for WORD (0-65535) and should trigger error
end

proc main()
  byte rv = bad()
  word rw = badw()
end
