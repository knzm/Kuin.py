from unittest import TestCase, main

from kuin.parser import parse_stmt, parse_expr


class TestParser(TestCase):

    def test_literal(self):
        self.assertEquals(parse_expr('"abc"'), "abc")
        self.assertEquals(parse_expr("'a'"), 'a')
        self.assertEquals(parse_expr(r'"a\"b\\c\n"'), 'a"b\\c\n')
        self.assertEquals(parse_expr(r"'\\'"), '\\')
        self.assertEquals(parse_expr(r"'\''"), "'")
        self.assertEquals(parse_expr(r"'\n'"), '\n')

    def test_empty(self):
        r = parse_stmt("")
        self.assertEquals(list(r), [])

    def test_if(self):
        r = parse_stmt("""\
if a(4 > 5)
  break a
end if

if a(4 > 5)
  break a
else
  break a
end if

if a(4 > 5)
  break a
elif (3 = 2)
  break
else
  break a
end if
""")
        print r

    def test_var(self):
        r = parse_stmt("""\
var i : int :: 5
var i : int
""")
        print r

    def test_const(self):
        r = parse_stmt("""\
const a : int :: 5
""")
        print r

    def test_alias(self):
        r = parse_stmt("""\
alias t : []int
""")
        print r

    def test_class(self):
        r = parse_stmt("""\
class CCat : CAnimal
  -var A : int
end class
""")
        print r

    def test_enum(self):
        r = parse_stmt("""\
enum EColor
  Red
  Blue
  Green :: 5
  Yellow
end enum
""")
        print r

    def test_switch(self):
        r = parse_stmt("""\
switch s(n)
case 0
  var a: int
  var a: int
case 1, 2, 5 @to 8, a
  const a: int :: 2
default
  break s
end switch
""")
        print r

    def test_while(self):
        r = parse_stmt("""\
while(a = 0, True)
  continue
end while
""")
        print r

    def test_for(self):
        r = parse_stmt("""\
for i(1, 10)
  break i
end for

for i(10, 1, -3)
  break i
end for
""")
        print r

    def test_foreach(self):
        r = parse_stmt("""\
foreach item(items)
  continue
end foreach
""")
        print r

    def test_ifdef(self):
        r = parse_stmt("""\
ifdef(debug)
  break
end ifdef
""")
        print r

    def test_block(self):
        r = parse_stmt("""\
block a
  break
end block
""")
        print r

    def test_return(self):
        r = parse_stmt("""\
return 5
return
""")
        print r

    def test_do(self):
        r = parse_stmt("""\
do a :: 4 + 5
do a :: f(1) + 2
do b :: !a
""")
        print r

    def test_throw(self):
        r = parse_stmt("""\
throw 5, "hoge"
""")
        print r

    def test_try(self):
        r = parse_stmt("""\
try e(1, 2, 5 @to 7)
  break e
catch 10, 11, 13 @to 15
  break
end try
""")
        print r

    def test_assert(self):
        r = parse_stmt("""\
assert a >= 2
""")
        print r

    def test_array(self):
        r = parse_stmt("""\
var p : [2][3]int
var q : [][]float
var s : []char :: "abc" ~ "def"
var c : char :: s[4]
""")
        print r

    def test_ternary(self):
        r = parse_stmt("""\
do a :: b ?(2, 3)
""")
        print r

    def test_assign(self):
        r = parse_stmt("""\
do a :+ 2
""")
        print r

    def test_at(self):
        r = parse_expr("@new [5]int")
        print r
        r = parse_stmt("""\
var a : []int :: @new [5]int
var b : CB :: @new CB
var c : bool :: b @is CB
""")
        print r

    def test_cast(self):
        r = parse_stmt("""\
var a : int :: 3.5 $ int
""")
        print r


if __name__ == '__main__':
    main()
