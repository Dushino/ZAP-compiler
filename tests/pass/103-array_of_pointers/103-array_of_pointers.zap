

byte ^vlstart[24]     ; array of pointers to the start of each line on the screen

proc main() 
    word dlstart @560      ; system storage for DL address
    word ^vram
    byte ^data
    byte i
    
    vram = dlstart + 4
    data = vram^
    ; data^ = 1
    ; vlstart[0] = data
    for i = 1 to 24
        vlstart[i] = data
        data = data + 40
    end
    vlstart[0]^ = 1
    vlstart[1]^ = 2
end
