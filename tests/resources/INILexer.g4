/*
 * Copyright (c) 2017 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

lexer grammar INILexer;


HEADER_OPEN
   : '[' -> pushMode(HEADER_MODE)
   ;

KEY
   : KEY_START_CHAR ( KEY_CHAR_WS* KEY_CHAR )?
   ;

fragment
KEY_START_CHAR
   : ~[[:=\r\n;# \t]
   ;

fragment
KEY_CHAR
   : KEY_START_CHAR
   | '['
   ;

fragment
KEY_CHAR_WS
   : KEY_CHAR
   | WS
   ;

EQUALS
   : [:=] -> pushMode(VALUE_MODE)
   ;

WS
   : [ \t]+
   ;

EOL
   : [\r\n]
   ;

COMMENT
   : COMMENT_START_CHAR ~[\r\n]*
   ;

fragment
COMMENT_START_CHAR
   : [;#]
   ;


mode HEADER_MODE;

HEADER
   : HEADER_CHAR ( HEADER_CHAR_WS* HEADER_CHAR )?
   ;

fragment
HEADER_CHAR
   : ~[[\]\r\n;# \t]
   ;

fragment
HEADER_CHAR_WS
   : HEADER_CHAR
   | HEADER_WS
   ;

HEADER_CLOSE
   : ']' -> popMode
   ;

HEADER_WS
   : [ \t]+
   ;


mode VALUE_MODE;

VALUE
   : VALUE_CHAR ( VALUE_CHAR_WS* VALUE_CHAR )? -> popMode
   ;

fragment
VALUE_CHAR
   : ~[\r\n\t;# ]
   ;

fragment
VALUE_CHAR_WS
   : VALUE_CHAR
   | VALUE_WS
   ;

VALUE_WS
   : [ \t]+
   ;
