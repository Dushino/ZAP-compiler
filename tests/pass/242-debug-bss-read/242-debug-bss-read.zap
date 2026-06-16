; Minimal test: write then read a BSS variable at ~$402B
byte result @$0200 = 0
byte bssvar  ; this goes to BSS

proc main()
    bssvar = 7
    result = bssvar
end
