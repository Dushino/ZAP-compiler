; p1.act
; Toto je komentář do konce řádku
/* Toto je
   komentář na více
   řádků
*/

; Globální proměnné bez inicializace
byte A          ; 1 byte, hodnota 0.255
word B          ; 2 byte, hodnota 0.65535

; globální proměnné s inicializací
byte C = 1
word D = $ff   ; HEX číslo

; globální proměnné s vynucemín adresy, na které se nachází
; vhodná pro práci s porty
byte D1 @$a000 = %00010101 ; s inicializací na binární hodnotu
word E @$a002 = 256        ; s inicializací dekadickou hodnotu

; ukazatele bez inicializace
byte ^ptr1                  ; ukazatel na Byte
word ^ptr2                  ; ukazatel na word

; ukazatele s uvedením adresy na které adrese se nachází
; byte ^ptr3 @560             ; ukazatel na BYTE se nachází na adrese 560 a 561
; word ^ptr4 @$81            ; ukazatel na WORD se nachází na adrese 0x81 a 0x82

; ukazatele s uvedením adresy na které adrese se nachází a inicializací
byte ^ptr3 @560 = 40000     ; ukazatel na BYTE se nachází na adrese 560 a 561 a je inicializován na adresu 40000
word ^ptr4 @$81 = $4000   ; ukazatel na WORD se nachází na adrese 0x81 a 0x82 a je inicializován na adresu 0x4000

; konstanty
const byte C1 = 1           ; musí být iniciován při deklaraci, pracuje se s ním jako zástupný symbol za číslo 1 byte
const word C2 = 2047        ; musí být iniciován při deklaraci, pracuje se s ním jako zástupný symbol za číslo 2 byte

; pole / řetězce
byte string[32]             ; bez inicializace, musí být určena délka
byte hello[] = "Hello world!"   ; s inicializací, délka pole je nepovinná, dopočítá se automaticky včetně 0 na konci řetězce
byte pole[5]  = {1, 2, 3, 4, 5} ; s inicializací, délka pole je nepovinná, dopočítá se


; Příklad použití v reálném programu ---------------------------------------
const byte^ scrstart = 40000    ; ATARI videoram při povoleném BASICu
const word scrstart1 = 40000    ; alternativní konstanta pro pozdější inicializaci ukazatele
byte XPOS = 0, YPOS = 0         ; počáteční pozice pro výpis
byte ^scradr                    ; aktuální adresa kurzoru

; Kurzor na začátek obrazovky
PROC Home()
    scradr = scrstart           ; inicializace z ukazatele
    ; nebo
    ; scradr = scrstart1          ; inicializace z WORD

    XPOS = 0
    YPOS = 0
END

; výmaz obrazovky a kurzor na začátek
PROC Cls()
    ; pro lokální proměnné platí stejná pravidla jako pro globální, jen mají omezenou platnost na PROC nebo FUNC
    word i      ; offset na obrazovce
    byte ^ptr = scrstart 

    ptr^ = 1

    ; vymaž znaky na obrazovce
    ;FOR i = 0 TO 40*24
    ;    ptr^ = 1        ; ulož 0 na místo, kam ukazuje ptr
    ;    ptr = ptr + 1    ; inkrementuj ptr
    ;NEXT i

    ; kurzor domů
    ;Home()
END

; vrať kód znaku na daných souřadnicích obrazovky
FUNC BYTE GetCh(byte x, byte y)
    BYTE zn
    byte ^ptr = scrstart

    ptr = ptr + 40*y + x
    zn = ptr^               ; vra+t hodnotu, na kterou ukayuje ptr  
RETURN zn

; Scroll screen up by one line
PROC Scroll()
    word i
    byte ^src = scrstart + 40   ; row 1
    byte ^dst = scrstart        ; row 0

    ; Copy rows 1-23 to rows 0-22 (920 bytes)
    FOR i = 0 TO 920
        dst^ = src^
        src = src + 1
        dst = dst + 1
    NEXT i

    ; Clear last line (row 23)
    dst = scrstart + 40*23
    FOR i = 0 TO 39
        dst^ = 0
        dst = dst + 1
    NEXT i
END

; zapiš znak na akt. pozici
PROC Putc(BYTE ch)
    byte ^ptr = scradr

    ptr^ = ch
    XPOS = XPOS + 1
    if XPOS > 39 THEN
        XPOS = 0
        YPOS = YPOS + 1
        if YPOS > 23 THEN
            YPOS = 23
            Scroll()
        endif
        scradr = scrstart + 40*YPOS + XPOS
    else
        scradr = scradr + 1
    endif
END


; vypiš řetězec
PROC Print(byte string[])
    byte zn, i = 0

    zn = string[i]
    while zn        ; není třeba psát zn != 0, protože výsledek vyhodnocení výrazu zn je hodnota zn a pokud je nenulová, je to TRUE
        putc(zn)
        i = i + 1
        zn = string[i]
    end
END

FUNC byte isOnScreen(byte x, byte y)
return (x < 40) && (y < 24)

; main -----------------------------------------
proc main()
    byte a @40000 = 'A'
    Cls()
    ;print(hello)
    
end

