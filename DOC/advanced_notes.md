# Random notes about ZAP language


## Identifiers

### Uppercase

- All identifiers are internally translated to its uppercase version. 
- Procedure, function name, variable name are all the same group of idfentifiers co can not have duplicates.

### Identifier naming rules

- Identifier name can not start with _
- Rest of identifier name can be alphanumeric characters and underscores


## Variables

### Global variables are used when name duplicates global variable

Consider following example:

```
byte var1


proc test1()
    byte var1

end
```

Inside the procedure there is no way how to reach global variable var1. Local variable will be used.

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

Local variable is declared on dedicated memory space and there is no ZAP way how to reach it.It means it will keep its value between calls.
However, there is no ZAP language built-in system how to initialize them when upon first procedure call. So you need global variable or
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
- In fact, case is preserved only in strings in "" or characters in ''. EVerything else is not case sensitive.

You might find useful knowledge about internal naming system. It is good to know when using inline assembly language:

- All function and procudure names are being used as labels in generated code.
- Global variables are prefixed with _. However, there is one exeption for internal system varibles named TMP<number>. It means:
  - You can safely use A,X,Y in your ZAP program and assembler will be happy with its _A, _X, _Y representation.
  - You can use TMP<number> in your code and it will not inerefere with internal TMP<number> variables.
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
- You can not use END in your assembler code for anything as it is understood as END for ASM in ZAP language.
- If you change segment (see .segment directive in ca65 documentation), it is your responsibility to properly change segment back into 

```
.segment "CODE"
```

before you leade ASM block.

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


### ToDo
- Describe how to share identifiers declard in ZAP in ASM blocks
- Describe how to use labels from ASM blocks in ZAP code
- Export and import symbols from/to whole ZAP program. Use case: ZAP program is part of bigger package.
- Introduce ZAP to github:
Add to GitHub Linguist (Recommended for long-term)
You could submit your ZAP language definition to the GitHub Linguist project. This would get ZAP officially recognized and syntax-highlighted on GitHub. You already have a good start with the zap.tmLanguage.json file in your repo.

Steps:
- Format your language definition according to Linguist's requirements
- Submit a PR to the Linguist repository with your language definition
- Once merged, GitHub will automatically highlight ZAP code blocks








