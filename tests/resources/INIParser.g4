/*
 * Copyright (c) 2017 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

parser grammar INIParser;

options { tokenVocab=INILexer; }


ini
   : comment* section* EOF
   ;

comment
   : WS? COMMENT EOL
   ;

section
   : header ( comment | line )*
   ;

header
   : WS? HEADER_OPEN HEADER_WS? HEADER HEADER_WS? HEADER_CLOSE WS? EOL
   ;

// Multiline values are not handled properly by this approach, the continuation
// lines will be recognized as keys, probably with no value.
line
   : WS? ( KEY WS? ( EQUALS VALUE_WS? ( VALUE WS? )? )? )? EOL
   ;
