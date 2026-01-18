

byte str1[] = "0123456" @40000
byte str2[] = "abcdefg" @40008
byte str3[8]            @40016

proc main()
    str1[0] = 'A'
    str2[3] = '1'
    str3    = str2
    str3[0] = '\n'
    str3[1] = '\t'
    str3[2] = '\''
    str3[3] = '\\'
    str3[4] = '\r'

end
