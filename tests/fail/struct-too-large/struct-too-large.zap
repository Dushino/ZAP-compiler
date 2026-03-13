; Test: struct larger than 255 bytes must be rejected
; A struct with 256 bytes total size cannot use LDY #offset for all fields
struct BigStruct
    byte data[256]
end

proc main()
end
