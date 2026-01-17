# Random notes about ZAP! language


## Identifiers

### Uppercase

- All identifiers are internally translated to its uppercase version. 
- Procedure, function name, variable name are all the same group of idfentifiers co can not have duplicates.

### Identifier naming rules

- Identifier name can not start with _
- Rest of identifier name can be alphanumeric characters and underscores


## Variables

### How variables use memory

There is an order in which ZAP! compiler places variables into memory. No variables are placed in CPU stack. It means that every variable (global or local) have its fixed RAM address. Addressed are reserved in this order:

1. Pointers
Pointers must fit into zero page. If not, error is issued and compilation is terminated

2. BYTE variables
Byte sized variables goes after pointers into zero page. If does not fit, they are placed in BSS segment (uninitialized RAM, address span is specified by ld65 linker configuration file).

3. WORD variables
Byte sized variables goes after pointers into zero page. If does not fit, they are placed in BSS segment.

4. Arrays and strings
All arrays and strings are allways placed into BSS segment.


### How variable declarations affect memory placement

Consider this example:

```
byte var1                       ; 1st line
byte var2 = 123                 ; 2nd line
byte var3 @$a000                ; 3rd line
byte var3 @$a000 = 123          ; 4th line
byte ^ptr1                      ; 5th line
byte ^ptr2 = $1234              ; 6th line
byte ^ptr3 @$0600               ; 7th line
byte ^ptr3 @$0600 = 254         ; 8th line
word ^ptr4                      ; 9th line
word ^ptr5 = $2345              ; 10th line
word ^ptr6 @560                 ; 11th line
word ^ptr7 @560 = MyDLIST       ; 12th line
```
- 1st line - variable consumes 1 byte and its address is automatically assigned from variables memory pool.
- 2st line - variable consumes 1 byte, its address is automatically assigned from variables memory pool and is initialized before use. If it is global variable, initialization is done before reaching main procedure. If it is local variable, initialization id done before executing code from procedure or function.
- 3rd line - variable is placed at memory address specified. It does not consume any byte from variables pool.
- 4th line - during initialization time (see comment for 2nd line) value is written to the address
- 5th line - declaration means pointer to BYTE. It means it consumes two bytes for address from variables pool in 0. page
- 6th line - pointer is initialized po point to address specified.
- 7th line - pointer does not consume space from variables pool and is placed in address specified. It is not possible to dereference such pointer. Only assignment to WORD or regular (from zero page pointers) is possible.
- 8th line - pointer at given address is initialized to a value.
- 9th line - pointer to word consumes two bytes from pointer variables pool to keep address it points to and points to word data type. As one unit pointer is pointing to is two bytes long, this:
```
ptr4 = pre4 + 1
```
increments address pointer is pointing to by 2 bytes (WORD data type size).
- 10th line - you already know that, it is usual initialization before use. 
- 11th line - the same as line 7, but points to WORD istead of BYTE.
- 12th line - the same as 8th line, but working with WORD instead of BYTE.

*Warnings*
- If you specify address to place variable at, you might collide with other variable from memory pool. Main motivation for declaration with address is to allow direct access to hardware ports.



### Global variables are used when name duplicates global variable

Consider following example:

```
byte var1


proc test1()
    byte var1

end
```

Inside the procedure or function there is no way how to reach global variable var1 from ZAP! language. Local variable will be used.

### Procedure parameter is procedure's local varible

Consider following example:

```
proc test1(byte var1)
    byte var1

end
```

This leads to compilation error, because var1 as parameter is the same as locally defined var1 meaning second declaration tries to use variable name allready taken (by parameter).

### Local variables are (almost) static

Consider following example:

```
proc test1()
    byte var1

    var1 = var1 + 1
end

proc main()
    test1()
    test1()
end
```

Local variable is declared on dedicated memory space and there is no ZAP! way how to reach it.It means it will keep its value between calls.
However, there is no ZAP! language built-in system how to initialize them when upon first procedure call. So you need global variable or
procedure parameter saying it is first call:

```
; One possibility to initialize on 1st run:
byte first = 1

proc test1()
    byte var1

    if first then
        var1 = 0
    end

    var1 = var1 + 1
end

; second possibitily to initialize on 1. run
proc test2(byte first)
    byte var1

    if first then
        var1 = 0
    end

    var1 = var1 + 1
end

proc main()

    ; run with initialization
    first = 1
    test1()
    test2(first)
    ; or simply:
    test2(1)

    ; run without initialization
    first = 0
    test1()
    test2(first)
    ; or simply
    test2(0)
end
```

### Internal identifiers naming

- All identifiers are internally translated to its upcase variant. 
- All references to indentifiers (calling procedureas or functions, using variables) are internally translated to its upcase as well.
- It all means that identifiers are not case sensitive. 
- Case is preserved only in strings in "" or characters in ''. Everything else is not case sensitive.

You might find useful knowledge about internal naming system. It is good to know when using inline assembly language:

- All function and procudure names are being used as labels in generated code. You can safely use A,X,Y in your ZAP! program and assembler will be happy with its _A, _X, _Y representation.

- Global variables are prefixed with _. However, there is one exeption for internal system varibles named TMP<number>. You can use TMP<number> in your code and it will not inerefere with internal TMP<number> variables.
- Local variable names is structure this way:

```
internal_name = _<PROC_name>_<declared_local_variable_name>
```

For example:

```
proc Test1()
    byte a1
end
````
Procedure Test1 is internally named as TEST1.
Local variable a1 is internally named as _TEST1_A1.


### ASM gotchas

- Everything between ASM and END is taken as it is and emited into resulting source code.
- It means it is your responsibility to properly use labels not to collide with other identifiers (see above).
- You can not use END in your assembler code for anything as it is understood as END for ASM in ZAP! language.
- If you change segment (see .segment directive in ca65 documentation), it is your responsibility to properly change segment back into 

```
.segment "CODE"
```

before you leave ASM block.

For example:
```
proc pgm_init()
    ASM
        .segment "FONT"         ; properly aligned in ld65 configuration file
        .incbin "my_font.fnt"
        .segment "PGM"          ; properly aligned in ld65 configuration file
        ; data you need here
        .segment "CODE"         ; switch back into "CODE" segment
    END
end
```

*Warning!*
Do not forget to call pgm_init from other procedure. Otherwise it will be optimized and not included. In fact, there is no code inside the procedure, just RTS generated in "CODE" segment in the example above.


