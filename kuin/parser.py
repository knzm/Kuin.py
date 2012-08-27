# -*- coding: utf-8 -*-

import re
from pyparsing import *

from kuin.nodes import *

__all__ = ['parse_stmt', 'parse_expr']


# bnf punctuation
LPAREN  = Suppress("(")
RPAREN  = Suppress(")")
LBRACK  = Suppress("[")
RBRACK  = Suppress("]")
LABRACK = Suppress("<")
RABRACK = Suppress(">")
COMMA   = Suppress(",")
COLON   = Suppress(":")
DCOLON  = Suppress("::")

KEYWORDS = oneOf([
        "if", "elif", "else",
        "switch", "case", "default",
        "while", "for", "foreach",
        "try", "catch", "finally",
        "ifdef", "release", "debug",
        "block", "end",
        "break", "continue",
        "return", "do", "throw",
        "func", "class", "enum",
        "var", "const", "alias",
        "import", "assert",
        "true", "false",
        ])

# Forward definitions
Sentences = Forward()
Expr = Forward()

######################################################################
# 識別子
######################################################################

Name = (
    NotAny(KEYWORDS) + Regex(r'[A-Za-z_][0-9A-Za-z_]*')
    ).setName('Name').setParseAction(SymbolNode.parse)
SourceName = Regex(u'[^\x20\x09-\x0D]+') # ソースコード名
# 標準空白類文字([ \t\n\v\f\r])以外の文字の連続

# ブロック名
BlockName = Name.setName('BlockName')

# 定義時のクラス名
CName = Name.setName('CName')

# 定義時の関数名
FName = Name.setName('FName')

# 定義時の変数名
VName = Name.setName('VName')

# 定義時の列挙体名
EName = Name.setName('EName')

# 定義時の定数名
ConstName = Name.setName('ConstName')

# アクセス時のクラス名
ClassName = (
    Combine(Optional(SourceName + Literal("@")) +
            ZeroOrMore(CName + ".") + CName)
    ).setName('ClassName').setParseAction(SymbolNode.parse)

# アクセス時の関数名
FunctionName = (
    Combine(Optional(ClassName + Literal(".")) + FName)
    ).setName('FunctionName').setParseAction(SymbolNode.parse)

# アクセス時の変数名
VariableName = (
    Combine(Optional(ClassName + Literal(".")) + VName)
    ).setName('VariableName').setParseAction(SymbolNode.parse)

# アクセス時の列挙体名
EnumName = (
    Combine(Optional(ClassName + Literal("#")) + EName)
    ).setName('EnumName').setParseAction(SymbolNode.parse)

ConstantName = (
    Combine(Optional(ClassName + Literal(".")) + ConstName) |
    Combine(EnumName + Literal("#") + ConstName)
    ).setName('ConstantName').setParseAction(SymbolNode.parse)

######################################################################
# 型
######################################################################

PrimitiveType = (
    # 符号付整数型・浮動小数点型・文字型・論理型
    oneOf(["int", "float", "char", "bool"]) |
    # 符号なし整数型
    oneOf(["byte8", "byte16", "byte32", "byte64"]) |
    # 符号付整数型
    oneOf(["sbyte8", "sbyte16", "sbyte32", "sbyte64"])
    ).setParseAction(SymbolNode.parse)

Type = Forward()

# リスト構造
ListType = (
    Keyword("list") + LABRACK + Type.setResultsName('item_type') + RABRACK
    ).setParseAction(CollectionTypeNode.parse)

# スタック構造
StackType = (
    Keyword("stack") + LABRACK + Type.setResultsName('item_type') + RABRACK
    ).setParseAction(CollectionTypeNode.parse)

# キュー構造
QueueType = (
    Keyword("queue") + LABRACK + Type.setResultsName('item_type') + RABRACK
    ).setParseAction(CollectionTypeNode.parse)

# 辞書型
DictType = (
    Keyword("dict") + LABRACK + Type.setResultsName('keytype') + COMMA +
    Type.setResultsName('valtype') + RABRACK
    ).setParseAction(DictTypeNode.parse)

# 関数型
FuncType = (
    Keyword("func") + LABRACK + LPAREN +
    delimitedList(Type).setResultsName('argtype*') + RPAREN +
    COLON + Type.setResultsName('rettype') + RABRACK
    ).setParseAction(FuncTypeNode.parse)

def array_size_action(r):
    if len(r) == 0:
        return [None]
    else:
        assert len(r) == 1
        return [r[0]]

# 動的配列
ArrayType = (
    OneOrMore((LBRACK + Optional(Expr) + RBRACK) \
                  .setParseAction(array_size_action)) \
        .setResultsName('size') +
    Type.setResultsName('base_type')
    ).setParseAction(ArrayTypeNode.parse)

Type << (
    PrimitiveType | EnumName | ClassName | # Alias |
    ListType | StackType | QueueType | DictType |
    FuncType | ArrayType
    ).setName('Type')

# しばらく complex/money/ratio型 を仕様から外そうと思います。とのこと。
# Kuinでは型が厳密に扱われます。暗黙の型変換はできません。

######################################################################
# リテラル
######################################################################

def string_action(r):
    def repl(m):
        esc = m.group(1)
        return {
            "n": "\n", "r": "\r", "\\": "\\",
            "'": "'", '"': '"',
            }.get(esc, esc)
    return re.sub(r'\\(.)', repl, r[0][1:-1])

def char_action(r):
    return string_action(r)

# 文字列リテラル
String = Regex(r'"(\\.|[^"])*"').setParseAction(string_action)

# 文字リテラル
Char = Regex(r"'(\\.|[^'])'").setParseAction(char_action)

# EscapedCh = Regex(r"\\[0nr]")
# EscapedCh は \0 \n \' などのエスケープ文字を表す文字列
# Ch << ( "'" + (Regex(r"[^']") | EscapedCh) + "'" )

# Booleanリテラル
Boolean = (
    Keyword("true").setParseAction(lambda r: True) |
    Keyword("false").setParseAction(lambda r: False)
    )

# 数値リテラル

# Kuinでは、16進数はもちろん、2～36進数の浮動小数点まで記述できます。
# 2進数の表記は例えば、2#00101111.1101 のようになります。#の前が基数です。

def number_action(instring, loc, r):
    import math

    sign = r.get('sign', '')
    body = r['body']
    precision = r.get('precision', '')

    if "#" in body:
        radix, body = body.split("#", 1)
        if radix == "":
            radix = 16
        else:
            radix = int(radix)
            if not (2 <= radix <= 36) or radix in (10, 16):
                raise ParseFatalException(instring, loc)
    else:
        radix = 10

    if "." in body:
        parts = body.split(".", 1)
        try:
            i, f = (int(part, radix) for part in parts)
        except ValueError:
            raise ParseFatalException(instring, loc)
        num = i + float(f) / math.pow(radix, len(parts[1]))
    else:
        try:
            num = int(body, radix)
        except ValueError:
            raise ParseFatalException(instring, loc)

    if precision:
        num *= math.pow(radix, int(precision))

    if sign == '-':
        num = -num

    return num

# 2進数～36進数
BaseX = Regex(r"([1-9][0-9]?)#([0-9A-Z]+)(?:\.([0-9A-Z]+))?")

# 10進数
Base10 = Regex(r"([0-9]+)(?:\.([0-9]+))?")
# 10#99はコンパイルエラー？

# 16進数
Base16 = Regex(r"#([0-9A-F]+)(?:\.([0-9A-F]+))?")
# 16#FFはコンパイルエラー
# 16進数の基数は省略しなければなりません(誰が書いても同じになるように)。

NonNegativeNumber = ( BaseX | Base10 | Base16 )

Number = Forward()
Number << (
    Optional(Regex(r'[+-]').setResultsName('sign')) +
    NonNegativeNumber.setResultsName('body') +
    Optional("e" + Number.setResultsName('precision'))
    ).setParseAction(number_action)

# 値指定

def value_item_action(r):
    return (r[0]["start"], r[0].get("end"))

# switch文やtry文で用いる値の指定方法です。
Value = delimitedList(
    Group(Expr.setResultsName('start') +
          Optional(Keyword("@to").suppress() +
                   Expr.setResultsName('end'))) \
        .setParseAction(value_item_action)) \
        .setParseAction(ValueNode.parse)

# Exprの型はそれぞれの文で制限されています。

######################################################################
# 式
######################################################################

def make_unary_expr(lastExpr, opExpr, rightLeftAssoc):
    thisExpr = Forward()

    if rightLeftAssoc == opAssoc.LEFT:
        matchExpr = (
            FollowedBy(lastExpr + opExpr) +
            Group(lastExpr + OneOrMore(opExpr))
            )

    if rightLeftAssoc == opAssoc.RIGHT:
        # try to avoid LR with this extra test
        if not isinstance(opExpr, Optional):
            opExpr = Optional(opExpr)
        matchExpr = (
            FollowedBy(opExpr.expr + thisExpr) +
            Group(opExpr + thisExpr)
            )
    matchExpr.setParseAction(ExprNode.parse_as_unary)
    thisExpr << ( matchExpr | lastExpr )
    return thisExpr


def make_binary_expr(lastExpr, opExpr, rightLeftAssoc):
    thisExpr = Forward()

    if rightLeftAssoc == opAssoc.LEFT and opExpr is not None:
        matchExpr = (
            FollowedBy(lastExpr + opExpr + lastExpr) +
            Group(lastExpr + OneOrMore(opExpr + lastExpr))
            )

    if rightLeftAssoc == opAssoc.RIGHT and opExpr is not None:
        matchExpr = (
            FollowedBy(lastExpr + opExpr + thisExpr) +
            Group(lastExpr + OneOrMore(opExpr + thisExpr))
            )

    if rightLeftAssoc == opAssoc.LEFT and opExpr is None:
        matchExpr = (
            FollowedBy(lastExpr + lastExpr) +
            Group(lastExpr + OneOrMore(lastExpr))
            )

    if rightLeftAssoc == opAssoc.RIGHT and opExpr is None:
        matchExpr = (
            FollowedBy(lastExpr + thisExpr) +
            Group(lastExpr + OneOrMore(thisExpr))
            )

    matchExpr.setParseAction(ExprNode.parse_as_binary)
    thisExpr << ( matchExpr | lastExpr )
    return thisExpr

def make_ternary_expr(lastExpr, opExpr1, opExpr2, rightLeftAssoc):
    thisExpr = Forward()

    if rightLeftAssoc == opAssoc.LEFT:
        matchExpr = (
            FollowedBy(lastExpr + opExpr1 + lastExpr + opExpr2 + lastExpr) +
            Group(lastExpr + opExpr1 + lastExpr + opExpr2 + lastExpr)
            )

    if rightLeftAssoc == opAssoc.RIGHT:
        matchExpr = (
            FollowedBy(lastExpr + opExpr1 + thisExpr + opExpr2 + thisExpr) +
            Group(lastExpr + opExpr1 + thisExpr + opExpr2 + thisExpr)
            )

    thisExpr << ( matchExpr | lastExpr )
    return thisExpr

BaseExpr = (
    # リテラル
    String | Char | Boolean | # Number |
    # 変数・定数
    VariableName | ConstantName |
    # (Forなどの)ブロック名
    BlockName
    )

NestedExpr = (LPAREN + Expr + RPAREN)
tmp_expr = ( BaseExpr | NestedExpr )

# 2: 関数呼び出し
tmp_expr = (
    ( FollowedBy(FunctionName + LPAREN) +
      FunctionName.setResultsName('funcname') + LPAREN +
      Optional(delimitedList(Expr).setResultsName('args')) + RPAREN
      ).setParseAction(FuncNode.parse) |
    tmp_expr)

# 2: 配列アクセス
tmp_expr = (
    ( FollowedBy(VariableName + LBRACK) +
      VariableName.setResultsName('array') +
      LBRACK + Expr.setResultsName('index') + RBRACK
      ).setParseAction(ArrayNode.parse) |
    tmp_expr)

# 3: インスタンスの作成(@new)
tmp_expr = (
    ( FollowedBy(Literal("@new") + Type) +
      (Literal("@new").suppress() + Type.setResultsName('type'))
      ).setParseAction(NewNode.parse) |
    tmp_expr)

# 3: 単項演算
tmp_expr = Number | make_unary_expr(
    tmp_expr,
    oneOf("+ - !").setParseAction(SymbolNode.parse),
    opAssoc.RIGHT)

# 4: クラスチェック(@is、@nis)
class_check_op = oneOf("@is @nis").setParseAction(SymbolNode.parse)
tmp_expr = (
    ( FollowedBy(tmp_expr + class_check_op + ClassName) +
      Group(tmp_expr + OneOrMore(class_check_op + ClassName)) \
          .setParseAction(ExprNode.parse_as_binary) ) |
    tmp_expr)

# 4: アットマーク演算子
# tmp_expr = make_binary_expr(
#     tmp_expr,
#     oneOf("@in @nin").setParseAction(SymbolNode.parse),
#     opAssoc.LEFT)

# 5: キャスト演算($)
cast_op = Literal("$").setParseAction(SymbolNode.parse)
tmp_expr = (
    ( FollowedBy(tmp_expr + cast_op + Type) +
      Group(tmp_expr + cast_op + Type) \
          .setParseAction(ExprNode.parse_as_binary) ) |
    tmp_expr)

# 6: 累乗
# tmp_expr = make_binary_expr(
#     tmp_expr,
#     Literal("^").setParseAction(SymbolNode.parse),
#     opAssoc.RIGHT)

# 7: 乗算、除算、剰余
tmp_expr = make_binary_expr(
    tmp_expr,
    oneOf("* / %").setParseAction(SymbolNode.parse),
    opAssoc.LEFT)

# 8: 加算、減算
tmp_expr = make_binary_expr(
    tmp_expr,
    oneOf("+ -").setParseAction(SymbolNode.parse),
    opAssoc.LEFT)

# 9: 配列連結
tmp_expr = make_binary_expr(
    tmp_expr,
    Literal("~").setParseAction(SymbolNode.parse),
    opAssoc.LEFT)

# 10: 等価、不等価、比較
tmp_expr = make_binary_expr(
    tmp_expr,
    oneOf("= <> < > <= >=").setParseAction(SymbolNode.parse),
    opAssoc.LEFT)

# 11: 論理積
# 12: 論理和
tmp_expr = make_binary_expr(
    tmp_expr,
    oneOf("& |").setParseAction(SymbolNode.parse),
    opAssoc.LEFT)

# 13: 条件演算
tmp_expr = (
    ( FollowedBy(tmp_expr + Combine(Literal("?") + LPAREN) +
                 tmp_expr + COMMA + tmp_expr + RPAREN) +
      Group(tmp_expr + Combine(Literal("?") + LPAREN).suppress() +
            tmp_expr + COMMA + tmp_expr + RPAREN) \
          .setParseAction(ExprNode.parse_as_ternary) ) |
    tmp_expr)
# 条件演算の ? と ( の間にスペースを入れてはいけません。

# 14: 代入演算子
tmp_expr = make_binary_expr(
    tmp_expr,
    oneOf(":: :+ :- :* :/ :% :^ :~").setParseAction(SymbolNode.parse),
    opAssoc.RIGHT)

Expr << tmp_expr
Expr.setName('Expr')

# 代入演算子が = ではなく、::なのが特徴的です。
# C言語の ==, !=, &&, || は、Kuinではそれぞれ、=, <>, &, | に対応します。
# インクリメント演算子はありません。i :+ 1 で代用してください。

######################################################################
# ブロック文
######################################################################

# 全てのブロック文が breakできます。
# ブロック内で定義したローカル変数は、そのブロック内でのみ参照できます。

# if文
If = (
    Keyword("if").suppress() +
    Optional(BlockName.setResultsName('block_name')) +
    LPAREN + Expr.setResultsName('then_cond') + RPAREN +
    Optional(Group(Sentences).setResultsName('then_body')) +
    ZeroOrMore(Keyword("elif").suppress() +
               LPAREN + Expr.setResultsName('elif_cond*') + RPAREN +
               Optional(Group(Sentences).setResultsName('elif_body*'))) +
    Optional(Keyword("else").suppress() +
             Optional(Group(Sentences).setResultsName('else_body'))) +
    (Keyword("end") + Keyword("if")).suppress()
    ).setName('If').setParseAction(IfNode.parse)

# 条件式 (()の中身)は、bool型でなければなりません。
# C言語のように int型にすると、コンパイルエラーとなります。

# switch文
SwitchCase = (
    Keyword("case").suppress() + Value.setResultsName('value') +
    Optional(Group(Sentences).setResultsName('body'))
    ).setParseAction(lambda r: (r["value"], r.get("body")))
SwitchDefault = (
    Keyword("default").suppress() +
    Optional(Group(Sentences).setResultsName('body'))
    ).setParseAction(lambda r: (None, r.get('body')))

Switch = (
    Keyword("switch").suppress() +
    Optional(BlockName.setResultsName('block_name')) +
    LPAREN + Expr.setResultsName('target') + RPAREN +
    ZeroOrMore(Group(SwitchCase).setResultsName('case*')) +
    Optional(Group(SwitchDefault).setResultsName('case*')) +
    (Keyword("end") + Keyword("switch")).suppress()
    ).setName('Switch').setParseAction(SwitchNode.parse)

# フォールスルーできません。case の最後に達した段階で自動でブロックを抜けます。
# case の値は、カンマ区切りで複数指定できます。また、@to 演算子により、範囲指定もできます。
# 上記のExprの型とValueの定義中のExprの型は一致しなければなりません。
# Exprに指定できる型： int、byte、char、enum、[]char
# case の値は、コンパイル時に定数とならなくても構いません。
# 複数の case条件に合致するとき、最初(最も上)に書かれた caseに捕捉されます。

# while文
While = (
    Keyword("while").suppress() +
    Optional(BlockName.setResultsName('block_name')) +
    LPAREN + Expr.setResultsName('cond') +
    Optional(COMMA + Expr.setResultsName('skip')) + RPAREN +
    Optional(Group(Sentences).setResultsName('body')) +
    (Keyword("end") + Keyword("while")).suppress()
    ).setName('While').setParseAction(WhileNode.parse)

# 条件式は bool型でなくてはなりません。
# skipを指定すると、初回の条件比較をスキップします (C言語のdo-whileの代替)。

# for文
For = (
    Keyword("for").suppress() +
    Optional(BlockName.setResultsName('block_name')) +
    LPAREN + Expr.setResultsName('start') + COMMA + Expr.setResultsName('end') +
    Optional(COMMA + Expr.setResultsName('step')) + RPAREN +
    Optional(Group(Sentences).setResultsName('body')) +
    (Keyword("end") + Keyword("for")).suppress()
    ).setName('For').setParseAction(ForNode.parse)

# 括弧内は順に、初期値、終値、増減値です。
# 省略すると増減値は 1 となります。
# 増減値が正の数ならば i <= 終値 がループ続行の条件となります。
# 増減値が負の数ならば i >= 終値 がループ続行の条件となります。
# 増減値が0の場合はコンパイルエラーになります。
# 増減値はコンパイル時に定数になる値でなければなりません。

# foreach文
Foreach = (
    Keyword("foreach").suppress() +
    Optional(BlockName.setResultsName('block_name')) +
    LPAREN + Expr.setResultsName('items') + RPAREN +
    Optional(Group(Sentences).setResultsName('body')) +
    (Keyword("end") + Keyword("foreach")).suppress()
    ).setName('Foreach').setParseAction(ForeachNode.parse)

# foreach で使えるのは、配列(文字列含む)、list、stack、queue、dict型だけです。
# dict型からforeachで要素を取り出すと、KeyとValueのペアを持ったdictpair型になります。
# enumも使えるようになるかも？ [出典: 10000favs]

# try文
Try = (
    Keyword("try").suppress() +
    Optional(BlockName.setResultsName('block_name')) +
    LPAREN + Optional(Value.setResultsName('ignore_value')) + RPAREN +
    Optional(Group(Sentences).setResultsName('body')) +
    Optional(Keyword("catch").suppress() +
             Optional(Value.setResultsName('catch_value')) +
             Optional(Group(Sentences).setResultsName('catch_body'))) +
    Optional(Keyword("finally").suppress() +
             Optional(Group(Sentences).setResultsName('finally_body'))) +
    (Keyword("end") + Keyword("try")).suppress()
    ).setName('Try').setParseAction(TryNode.parse)

# tryの括弧内に値を記述すると、その例外コードの例外の発生を抑制します。
# 上記のValueで例外コードを指定します（複数指定可能）。
# 例外コードに指定できる値の型：int型 のみ

IfdefMode = (
    Keyword("release").setParseAction(lambda r: IfdefNode.release) |
    Keyword("debug").setParseAction(lambda r: IfdefNode.debug)
    )

# ifdef文
Ifdef = (
    Keyword("ifdef").suppress() +
    Optional(BlockName.setResultsName('block_name')) +
    LPAREN + IfdefMode.setResultsName('mode') + RPAREN +
    Optional(Group(Sentences).setResultsName('body')) +
    (Keyword("end") + Keyword("ifdef")).suppress()
    ).setName('Ifdef').setParseAction(IfdefNode.parse)

# debug を指定するとデバッグコンパイル時のみ中身がコンパイルされます。

# block文
Block = (
    Keyword("block").suppress() +
    Optional(BlockName.setResultsName('block_name')) +
    Optional(Group(Sentences).setResultsName('body')) +
    (Keyword("end") + Keyword("block")).suppress()
    ).setName('Block').setParseAction(BlockNode.parse)

# 単純に、ブロック構造を作りたいときに有効です。
# 他のブロック文と同様、breakできます。

######################################################################
# 単文
######################################################################

# do文
Do = (
    Keyword("do").suppress() + Expr.setResultsName('expr')
    ).setName('Do').setParseAction(DoNode.parse)

# :: 演算子は、演算子の左側の変数に、右側の値を代入します。
# 代入文では、両辺が参照型の場合、値ではなくアドレスが代入されます。

# import構文
Import = ( Keyword("import").suppress() + SourceName )

# break文
Break = (
    Keyword("break").suppress() +
    Optional(BlockName.setResultsName('block_name'))
    ).setName('Break').setParseAction(BreakNode.parse)

# BlockNameで指定したブロックを抜けます。
# BlockNameを省略した場合は一番内側のブロックを抜けます。

# continue文
Continue = (
    Keyword("continue").suppress() +
    Optional(BlockName.setResultsName('block_name'))
    ).setName('Continue').setParseAction(ContinueNode.parse)

# BlockNameという名前を持つブロックの終端(end)直前にジャンプします。
# ブロック名は省略可能。省略した場合は一番内側のブロックと解釈されます。
# continue可能なブロックは、while、for、foreachです。

# return文
Return = (
    Keyword("return").suppress() +
    Optional(Expr.setResultsName('value'))
    ).setName('Return').setParseAction(ReturnNode.parse)

# assert文
Assert = (
    Keyword("assert").suppress() +
    Expr.setResultsName('expr')
    ).setName('Assert').setParseAction(AssertNode.parse)

# 上記のExprはbool型でなければなりません。[要出典]

# throw文
Throw = (
    Keyword("throw").suppress() +
    Expr.setResultsName('code') +
    COMMA + Expr.setResultsName('message')
    ).setName('Throw').setParseAction(ThrowNode.parse)

# 1つ目のExprは例外コード( int型 )
# 2つ目のExprは例外メッセージ( []char型 )
# 例外メッセージを省略すると、例外メッセージに null が入ります。

######################################################################
# 定義文
######################################################################

# func構文 (関数定義)
Func = (
    Keyword("func").suppress() + FName +
    LPAREN + Optional(VName + COLON + Type +
                      ZeroOrMore(COMMA + VName + COLON + Type)) + RPAREN +
    Optional(COLON + Type) +
    Optional(Group(Sentences)) +
    (Keyword("end") + Keyword("func")).suppress() )

# var構文 (変数定義)
Var = (
    Keyword("var").suppress() + VName.setResultsName('varname') +
    COLON + Type.setResultsName('typename') +
    Optional(DCOLON + Expr.setResultsName('value'))
    ).setName('Var').setParseAction(VarNode.parse)

# :: Exprを省略した場合、すべて0で初期化されます。
# グローバル変数・メンバ変数では、定義時には値を代入できません。
# 定義と同時に値を代入できるのは、ローカル変数のみです。

# const構文 (定数定義)
Const = (
    Keyword("const").suppress() + VName.setResultsName('varname') +
    COLON + Type.setResultsName('typename') +
    DCOLON + Expr.setResultsName('value')
    ).setName('Const').setParseAction(ConstNode.parse)

# 定数の代入式の右辺(Expr)は、コンパイル時に決定できる値でなくてはなりません。

# alias構文 (別名定義)
Alias = (
    Keyword("alias").suppress() + Name.setResultsName('alias') +
    COLON + Type.setResultsName('typename')
    ).setName('Alias').setParseAction(AliasNode.parse)

# []char を string などの別名にするのは推奨されません。
# ( Kuin の文字列型が []char であることに慣れるのが望ましい )

# enum構文 (列挙体定義)
EnumMember = (
    ConstName.setResultsName('key') +
    Optional(DCOLON + Expr.setResultsName('value'))
    ).setParseAction(lambda r: (r["key"], r.get("value")))

Enum = (
    Keyword("enum").suppress() + EName.setResultsName('name') +
    OneOrMore(EnumMember).setResultsName('member') +
    (Keyword("end") + Keyword("enum")).suppress()
    ).setName('Enum').setParseAction(EnumNode.parse)

# :: Exprを指定しなかったときのデフォルト値は 0 から始まります。
# 値は自動的に 1 ずつ足されて設定されます。
# 下記の例では、Red は 0、Blue は 1、Yellow は 6に設定されます。
# enum EColor
#     Red
#     Blue
#     Green :: 5
#     Yellow
# end enum
# 他の要素と値が重複した場合は、コンパイルエラーとなります。
# 値の指定は、コンパイル時に int に決定される定数でなくてはなりません。

# class構文 (クラス定義)

Class = Forward()

ClassMember = ( Func | Var | Const | Alias | Class | Enum )

Class << (
    Keyword("class").suppress() + CName.setResultsName('name') +
    Optional(COLON + ClassName.setResultsName('parent')) +
    ZeroOrMore(Optional(oneOf("+ -").setResultsName('visibility*')) +
               Optional(Literal("*").setResultsName('override*')) +
               ClassMember.setResultsName('member*')) +
    (Keyword("end") + Keyword("class")).suppress()
    ).setName('Class').setParseAction(ClassNode.parse)

# 継承元( : ClassName )を省略すると、Kuin@CClass が継承されます。
# 全てのクラスは、ルートクラスである Kuin@CClass が継承されていると言えます。
# 例： class CCat : CAnimalとすると、Kuin@CClass → CAnimal → CCat
#
# - ⇒ private なメンバ。
# + ⇒ protected なメンバ。
# * ⇒ 親クラスのメンバのオーバーライドを許可。
# * は、- や + の後に記述しなければエラーとなります。
# (誰が書いても同じようなコードにするため)

######################################################################
# コメント
######################################################################

Comment = Forward()
Comment << (
    Literal("{") +
    ZeroOrMore(String | Char | Comment | Regex(r"[^\"'{}]+")) +
    Literal("}")
    ).setName('Comment')

# 複数行コメント可能です。一行コメントに特化したコメント記法はありません。
# Kuinでは、コメントがネストできます。
# また、コメント内部に文字列リテラル、文字リテラルを含み得ます。
# 例えば、{ " }" {  } }は全体がコメント扱いされます。

######################################################################
# 文
######################################################################

# ブロック文、単文、定義文

BlockStatement = ( If | Switch |
                   While | For | Foreach |
                   Try | Ifdef | Block )

SimpleSentence = ( Do | Import |
                   Break | Continue | Return |
                   Assert | Throw )

Definition = ( Func | Var | Const | Alias | Class | Enum )

Sentence = ( BlockStatement | SimpleSentence | Definition )

Sentences << ZeroOrMore(Sentence).ignore(Comment)

######################################################################

def parse_expr(text, debug=False):
    """
    booleans:

    >>> parse_expr("true")
    True
    >>> parse_expr("false")
    False

    strings/chars:

    >>> parse_expr('"abc"')
    'abc'
    >>> parse_expr("'a'")
    'a'

    numbers:

    >>> parse_expr("10")
    10
    >>> parse_expr("-0.999")
    -0.999
    >>> parse_expr("2#1000")
    8
    >>> parse_expr("8#777")
    511
    >>> parse_expr("#FFF")
    4095
    >>> parse_expr("6.02e+23")
    6.019999999999999e+23
    >>> parse_expr("36#Z")
    35

    # Hexdecimal/decimal should not have prefix.

    >>> parse_expr("16#FFF") # doctest:+ELLIPSIS
    Traceback (most recent call last):
      ...
    ParseFatalException: ...
    >>> parse_expr("10#123") # doctest:+ELLIPSIS
    Traceback (most recent call last):
      ...
    ParseFatalException: ...

    # Alphabetical digits should be capital.

    >>> parse_expr("#fff") # doctest:+ELLIPSIS
    Traceback (most recent call last):
      ...
    ParseException: ...

    # Invalid format for given radix

    >>> parse_expr("8#9") # doctest:+ELLIPSIS
    Traceback (most recent call last):
      ...
    ParseFatalException: ...

    # Edge cases

    >>> parse_expr("#1")
    1
    >>> parse_expr("2#") # doctest:+ELLIPSIS
    Traceback (most recent call last):
      ...
    ParseException: ...
    >>> parse_expr("1#0") # doctest:+ELLIPSIS
    Traceback (most recent call last):
      ...
    ParseFatalException: ...

    numerical

    >>> parse_expr("1 + 1")
    <Expr `+`(1, 1)>
    >>> parse_expr("2 * 3")
    <Expr `*`(2, 3)>
    >>> parse_expr("a > b")
    <Expr `>`(`a`, `b`)>

    logical

    >>> parse_expr("4 <= n & n <= 10")
    <Expr `&`(<Expr `<=`(4, `n`)>, <Expr `<=`(`n`, 10)>)>
    >>> parse_expr("!a")
    <Expr `!`(`a`)>

    function call

    >>> parse_expr("f()")
    <Func `f`()>
    >>> parse_expr("f(1)")
    <Func `f`(1)>
    >>> parse_expr("f(1, 2)")
    <Func `f`(1, 2)>
    >>> parse_expr("f(g(1))")
    <Func `f`(<Func `g`(1)>)>

    >> b ?(2, 3)

    """
    return Expr.setDebug(debug).parseString(text, parseAll=True)[0]

def parse_stmt(text, debug=False):
    return Sentences.setDebug(debug).parseString(text, parseAll=True)

if __name__ == '__main__':
    import doctest
    doctest.testmod()
