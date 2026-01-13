; p1.act
; basic tests 



byte a1
byte a2 = 10
byte a3 = $6500
byte a4 = 'A
byte a5 @$6500
byte a6, a7 = $7000, a8 @$6800
byte a9 = a3 + a2 * 2 
byte POINTER a10=$7800
byte ARRAY a11[10] = {1,2,3,4,5,6,7,8,9,10} 
byte ARRAY scrt[1200] @$6800
byte ARRAY text1 = "abcdefg"

word b1
word b2 = 10
word b3 = $6500
word b4 = 'A
word b5 @$6500
word b6, b7 = $7000, b8 @$6800
word b9 = b3 + b2 * 2 + a2
word POINTER b10 = $7800
word ARRAY b11[10] = {11,12,13,14,15,16,17,18,19,20} 
word ARRAY scrt[600] @$7000
word ARRAY text2 = "qwerty" 



TYPE mystruct=[BYTE a1,
               POINTER BYTE a2]

mystruct xstr
xstr.a1 = 0
xstr.s2^ = %11110110    ; light blue




a1 = a2 > b2
a1 = a2 < b2
a1 = a2 >= b2
a1 = a2 >= b2
a10  = $6801
a10^ = 'A
a10  = @b3

b1 = a2 > b2
b1 = a2 < b2
b1 = a2 >= b2
b1 = a2 >= b2

a1 = a2 > b2 || a2 = 10
a1 = a2 > b2 && a2 = 10
a1 = (a2 > b2) || a2 <= b5

text1[1]='X
text2[0]=$f00f

a1 = 0
IF s2>=1 THEN
    a1 = 1
ELSEIF money>=8 THEN
    a1 = 2
ELSEIF money>=6 THEN
    a1 = 3
ELSE
    a1 = 4
FI

PROC p1()
RETURN

PROC p2(byte v1, byte v2)
RETURN

PROC p2(byte v1, byte v2)
    byte local1

    local1 = v1 + v2
RETURN


byte FUNC f1(byte v1, byte v2)
    byte local1

    local1 = v1 + v2
RETURN (local1)


PROC PrintE(char array text)

RETURN


PROC p2()
    BYTE ctr ;counter used in FOR loop
    FOR ctr=1 TO S ;this FOR loop has no 'STEP', so
        ;an increment of 1 is assumed.
    FEND

    BYTE    num,
            guess=[200]

    PrintE("Welcome to the guessing game. I am")
    PrintE("thinking of a number from 0 to 100")
    num=Rand(101) ;gets the number to guess
    WHILE guess<>num
        ;start of WHILE loop
        Print("What is your guess? ")
        guess=InputB()
        ;get user's guess
        IF guess<num THEN
            ;guess too low
            PrintE("Too low, try again")
        ELSEIF guess>num THEN ;guess too high
            PrintE("Too high, try again")
        ELSE
            ;guess just right
            PrintE("Congratulations!!!!")
            PrintE("You got it")
        FI
        ;end of guess testing
    WEND
    ;end of WHILE loop

    ctr = 0
    REPEAT
        ctr = ctr + 1
    UNTIL ctr < 5
    
    a1 = f1(byte v1, byte v2)

;end of PROC
RETURN


PROC CLS() @$A58C



