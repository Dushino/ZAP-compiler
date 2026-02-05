proc main()
    byte ^dlstart @560
    byte ^dlptr
    byte ^vram

    dlptr = dlstart
    dlptr = dlptr + 4
    vram = dlptr^
end
