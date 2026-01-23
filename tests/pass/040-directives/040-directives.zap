byte result @40000 = 0

proc setfont()
    .segment "FONT"
    .incbin "default.fnt"
    .segment "CODE"
end


proc main()
    byte str[4] = "\n\t\\"
    result = str[2]
end
