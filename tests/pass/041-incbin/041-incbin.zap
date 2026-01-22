byte result @40000 = 0

proc setfont()
    .segment "FONT"
    .incbin "font.fnt"
    .segment "CODE"
end

proc main()
    setfont()
    result = 42
end
