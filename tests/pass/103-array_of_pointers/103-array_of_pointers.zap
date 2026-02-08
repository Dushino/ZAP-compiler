

byte ^vlstart[24]     ; array of pointers to the start of each line on the screen

proc main() 
    word dlstart @560 = $1000     ; system storage for DL address
    byte dldata[8] @$1000 = {$70, $70, $70, $71, $40, $9C, 2, 2} ; data for the DL
    byte ^data
    word ^vram
    byte i
    
    dlstart = $1000

    vram = dlstart + 4
    data = vram^
    for i = 1 to 24
        vlstart[i] = data
        data = data + 40
    end
    
    vram = dlstart + 4
    data = vram^

    for i = 0 to 23
        vlstart[i] = data
        data = data + 40
        vlstart[i]^ = i
    end
    vlstart[0]^ = 129
    vlstart[1]^ = 130    

end
