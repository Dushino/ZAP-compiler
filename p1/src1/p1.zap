; p1.act

const byte^ scrstart = 40000    ; ATARI videoram při povoleném BASICu
byte XPOS = 0, YPOS = 0         ; počáteční pozice pro výpis
byte ^scradr                    ; aktuální adresa kurzoru

; výmaz obrazovky a kurzor na začátek
PROC Cls()
    ; pro lokální proměnné platí stejná pravidla jako pro globální, jen mají omezenou platnost na PROC nebo FUNC
    word i      ; offset na obrazovce
    const byte len = 2
    byte ^ptr = scrstart 

    ; vymaž znaky na obrazovce
    i = 1 + 2 * len
    while i < 40*23
        ptr^ = 1
        i = i + 1
        ptr = ptr + 1    ; inkrementuj ptr        
    end
    ; kurzor domů
    ;Home()
END


; main -----------------------------------------
proc main()
    byte bkgcolor @712
    Cls()    
    bkgcolor = $74
end

