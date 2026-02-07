

byte ^vlstart[24]     ; array of pointers to the start of each line on the screen

proc main() 
    word dlstart @560      ; system storage for DL address
    byte dldata[8] @$1000 = {$70, $70, $70, $71, $40, $9C, 2, 2} ; data for the DL
    word ^vram
    byte ^data
    byte i
    

    dlstart = $1000

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
