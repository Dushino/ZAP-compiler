
# The author of this software stands in solidarity with 🇺🇦 Ukraine. 
# We believe in a world where international borders are respected and human rights are upheld. 
# We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.



# token_types.py
TOK_LBRACE      = "LBRACE"      # (
TOK_RBRACE      = "RBRACE"      # )
TOK_IDENT       = "IDENT"       # identifier
TOK_NUMBER      = "NUMBER"      # number as a string with radix prefix
TOK_STRING      = "STRING"      # string
TOK_KEYWORD     = "KEYWORD"     # keyword
TOK_TYPE        = "TYPE"        # typedef
TOK_TYPEMOD     = "TYPEMOD"     # type modifier CONST
TOK_PTR         = "PTR"         # pointer / dereference idicator
TOK_DELIM       = "DELIM"       # ,:
TOK_EQU         = "EQU"         # =
TOK_OP          = "OP"          # operator
TOK_AT          = "AT"          # @
TOK_EOF         = "EOF"         # end of file indicator
TOK_SQB         = "SQB"         # []
TOK_LCURLY      = "LCURLY"      # {
TOK_RCURLY      = "RCURLY"      # }
TOK_PREPROC     = "PREPROC"     # preprocessor
TOK_ASM_BLOCK   = "ASM_BLOCK"   # inline assembly block
TOK_DECLMOD     = "DECLMOD"     # declaration modifier, e.g. #KEEP, #NOEXPORT, #EXPORT
TOK_COMPOUNDASSIGN = "COMPOUNDASSIGN"  # +=, -=, *=, /=, %=, &=, |=, ^=, <<=, >>=

