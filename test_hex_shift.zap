proc put_hex(byte value)
    ; Extract and return the high nibble
    byte result
    result = (value >> 4) & 0xF
end

proc main()
    put_hex(42)
end
