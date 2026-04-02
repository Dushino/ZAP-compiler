; The author of this software stands in solidarity with 🇺🇦 Ukraine. We believe in a world where international borders are respected and human rights are upheld. We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


; https://github.com/pedromagician/Atari800-benchmarks/blob/main/a.act

.ifndef ATARI
    .define ATARI
.endif


.include "../work/lib/stdio.zap"
.include "../work/lib/types.zap"
.include "../work/lib/string.zap"
.include "../work/lib/atari/atari_gtia.zap"


; ---------------------------------------------------
byte time[3] @18    ; Atari timer
byte SDMCTL @559


; ---------------------------------------------------
proc start()
    
    time[0] = 0
    time[1] = 0
    time[2] = 0
end


; ---------------------------------------------------
proc finish(byte id)
    byte t1, t2, t3

    t1 = time[0]
    t2 = time[1]
    t3 = time[2]

    puts("\n")
    putchar(id)
    putchar(':')

    putx(t1)    
    putx(t2)
    putx(t3)
    puts("\n")

    getc()
end


; ---------------------------------------------------
; https://github.com/pedromagician/Atari800-benchmarks/blob/main/a.act
; Action!:     522      = 10.44s
; Zap! $0152 = 338 / 50 =  6.76s
proc test_a()
  word I

  start()
  FOR I=1 TO 501
    puts("HELLO\n")
  end
  finish('A')
end


; ---------------------------------------------------
; https://github.com/pedromagician/Atari800-benchmarks/blob/main/b.act
; Action!: 5 = 0.1s
; Zap! $0004 = 4 / 50 = 0.08s
proc test_b()
    word i,x

    start()
    FOR I=1 TO 3001 
        x=45
    end    
    finish('B')
end


; ---------------------------------------------------
; https://github.com/pedromagician/Atari800-benchmarks/blob/main/c.act
; Action!: 5 = 0.1s
; Zap! $0004 = 3 / 50 = 0.06s
proc test_c()
    word i,x = 0

    start()
    FOR I=1 TO 3001
        X=X+1
    end
    finish('C')
end


; ---------------------------------------------------
; https://github.com/pedromagician/Atari800-benchmarks/blob/main/d.act
; Action!: 167 = 3.34s; 
; Zap! $0022 = 34 / 50 = 0.68s
proc test_d()
    word a,b,x,c 

    start()
    FOR A=1 TO 16
        X=0 
        C=0
        FOR B=1 TO 201
          C=B+2*B
          X=X+B*2
          C=(C-B)/2
        end
    end    
    finish('D')
end


; ---------------------------------------------------
; https://github.com/pedromagician/Atari800-benchmarks/blob/main/e.act
; Action!: 76 = 1.52s
; Zap! $0029 =  41 / 50 = 0.82s
proc test_e()
    const word max = 8192
    byte flags[max]
    word count = 0
    word i, prime, k

    SDMCTL = 0
    start()
    for i=0 to max
        flags[i] = 1
    end

    for i=0 to max
        if flags[i]
            prime = i*2+3
            k = i + prime
    
            while k <= max-1
                flags[k] = 0
                k += prime
            end
            count += 1
        end
    end
    SDMCTL = 34
    finish('E')    
end


; ---------------------------------------------------
; https://github.com/pedromagician/Atari800-benchmarks/blob/main/f.act
; Action!: 26 = 0.52s
; Zap! $001D =  29 / 50 = 0.58s
proc test_f()
    byte I,J
    word scrstart @88
    word scr

    GRAPHICS(24)
    scr = scrstart
    start()    
    FOR I=0 TO 32
        FOR J=0 TO 240
            POKE(scr + j, 255)
        end
        scr += 240
    end
    GRAPHICS(0)
    finish('F')      
end


; ---------------------------------------------------
proc main()

    test_a()
    test_b()
    test_c()
    test_d()
    test_e()
    test_f()
    puts("Done")
end
