import re
from collections import OrderedDict

__all__ = [
    "IfNode", "SwitchNode", "WhileNode", "ForNode", "ForeachNode", "TryNode",
    "IfdefNode", "BlockNode", "DoNode", "ImportNode", "BreakNode",
    "ContinueNode", "ReturnNode", "AssertNode", "ThrowNode", "FuncNode",
    "VarNode", "ConstNode", "AliasNode", "CollectionTypeNode",
    "DictTypeNode", "FuncTypeNode", "ArrayTypeNode", "ClassNode", "EnumNode",
    "ExprNode", "SymbolNode", "ValueNode", "ArrayNode", "NewNode",
]

def _to_string(nodes):
    return "{ " + ", ".join([repr(node) for node in nodes]) + " }"

def symbol(name):
    return SymbolNode(name)

def assert_symbol(obj):
    assert (obj is None or isinstance(obj, SymbolNode))

class Node(object):
    @classmethod
    def parse(cls, instring, loc, r):
        try:
            return cls(**r)
        except TypeError:
            assert False

    def get_node_args(self):
        return None

    def __repr__(self):
        node_args = self.get_node_args()
        node_name = re.sub(r'Node$', '', self.__class__.__name__)
        s = ["<", node_name]
        if node_args:
            s += [" ", node_args]
        s += [">"]
        return "".join(s)

class SymbolNode(Node):
    @classmethod
    def parse(cls, instring, loc, r):
        if isinstance(r[0], cls):
            return r[0]
        try:
            return cls(r[0])
        except TypeError:
            assert False

    def __init__(self, symbol):
        assert isinstance(symbol, str)
        self.symbol = symbol

    def __repr__(self):
        return "`%s`" % self.symbol

class ExprNode(Node):
    ternary_op = symbol('?()')

    @classmethod
    def parse_as_unary(cls, instring, loc, r):
        try:
            op, expr = r[0]
            return cls(op, expr)
        except TypeError:
            assert False

    @classmethod
    def parse_as_binary(cls, instring, loc, r):
        try:
            left, op, right = r[0]
            return cls(op, left, right)
        except TypeError:
            assert False

    @classmethod
    def parse_as_ternary(cls, instring, loc, r):
        try:
            cond, true_body, false_body = r[0]
            return cls(cls.ternary_op, cond, true_body, false_body)
        except TypeError:
            assert False

    def __init__(self, operator, *operands):
        self.operator = operator
        self.operands = operands or []

    def get_node_args(self):
        return "%r(%s)" % (
            self.operator,
            ", ".join([repr(op) for op in self.operands]))

class ValueNode(Node):
    @classmethod
    def parse(cls, instring, loc, r):
        try:
            return cls(r)
        except TypeError:
            assert False

    def __init__(self, range):
        self.range = tuple(range)

    def __repr__(self):
        buf = []
        for s, e in self.range:
            if e is None:
                buf.append(repr(s))
            else:
                buf.append("%r-%r" % (s, e))
        return "[" + ", ".join(buf) + "]"

class ArrayNode(Node):
    def __init__(self, array, index):
        self.array = array
        self.index = index

    def __repr__(self):
        return "%r[%r]" % (self.array, self.index)

class NewNode(Node):
    def __init__(self, type):
        self.type = type

    def __repr__(self):
        return "@new %r" % self.type

class IfNode(Node):
    def __init__(self, then_cond, then_body=None, elif_cond=None,
                 elif_body=None, else_body=None, block_name=None):
        assert_symbol(block_name)
        clauses = [(then_cond, tuple(then_body or []))]
        if elif_cond and elif_body:
            assert len(elif_cond) == len(elif_body)
            clauses += zip(elif_cond, elif_body)
        else:
            assert (elif_cond is None and elif_body is None)
        if else_body:
            clauses += [(None, tuple(else_body))]
        self.clauses = clauses
        self.block_name = block_name

    def get_node_args(self):
        if self.block_name:
            block_name = repr(self.block_name)
        else:
            block_name = ""
        args = []
        for cond, body in self.clauses:
            if cond:
                args += ["(%r)" % cond]
            args += [_to_string(body)]
        return block_name + " ".join(args)

class SwitchNode(Node):
    def __init__(self, target, case=None, block_name=None):
        assert_symbol(block_name)
        self.target = target
        self.case = tuple([(c[0][0], tuple(c[0][1])) for c in case])
        self.block_name = block_name

    def get_node_args(self):
        if self.block_name:
            block_name = repr(self.block_name)
        else:
            block_name = ""
        clauses = []
        for value, body in self.case:
            if value:
                clause = repr(value) + _to_string(body)
            else:
                clause = _to_string(body)
            clauses.append(clause)
        args = [block_name]
        args += ["(%s)" % self.target]
        args += [", ".join(clauses)]
        return "".join(args)

class WhileNode(Node):
    def __init__(self, cond, skip=None, body=None):
        self.cond = cond
        self.skip = skip
        self.body = tuple(body or [])

    def get_node_args(self):
        return " ".join([
                "(%r %r)" % (self.cond, self.skip),
                _to_string(self.body)])

class ForNode(Node):
    def __init__(self, start, end, step=None, block_name=None, body=None):
        assert_symbol(block_name)
        self.start = start
        self.end = end
        self.step = step
        self.block_name = block_name
        self.body = tuple(body or [])

    def get_node_args(self):
        if self.block_name:
            block_name = repr(self.block_name)
        else:
            block_name = ""
        args = block_name
        if self.step:
            args += "(%r, %r, %r)" % (self.start, self.end, self.step)
        else:
            args += "(%r, %r)" % (self.start, self.end)
        args += " " + _to_string(self.body)
        return args

class ForeachNode(Node):
    def __init__(self, items, block_name=None, body=None):
        assert_symbol(block_name)
        self.items = items
        self.block_name = block_name
        self.body = tuple(body or [])

    def get_node_args(self):
        if self.block_name:
            args = repr(self.block_name)
        else:
            args = ""
        args += "(%r)" % self.items
        args += " " + _to_string(self.body)
        return args

class TryNode(Node):
    def __init__(self, block_name=None, ignore_value=None, body=None,
                 catch_value=None, catch_body=None, finally_body=None):
        assert_symbol(block_name)
        self.block_name = block_name
        self.ignore_value = ignore_value
        self.body = tuple(body or [])
        self.catch_value = catch_value
        self.catch_body = tuple(catch_body or [])
        self.finally_body = tuple(finally_body or [])

    def get_node_args(self):
        args = ["%s(%s)" % (
                repr(self.block_name) if self.block_name else "",
                repr(self.ignore_value) if self.ignore_value else ""),
                _to_string(self.body)]
        if self.catch_value or self.catch_body:
            args += ["catch", "(%r)" % self.catch_value]
            args += [_to_string(self.catch_body)]
        if self.finally_body:
            args += [_to_string(self.finally_body)]
        return " ".join(args)

class IfdefNode(Node):
    release = symbol('release')
    debug = symbol('debug')

    def __init__(self, mode, block_name=None, body=None):
        assert_symbol(block_name)
        self.mode = mode
        self.block_name = block_name
        self.body = tuple(body or [])

    def get_node_args(self):
        if self.block_name:
            block_name = repr(self.block_name)
        else:
            block_name = ""
        args = block_name
        args += "(%r)" % self.mode
        args += " " + _to_string(self.body)
        return args

class BlockNode(Node):
    def __init__(self, block_name=None, body=None):
        assert_symbol(block_name)
        self.block_name = block_name
        self.body = tuple(body or [])

    def get_node_args(self):
        if self.block_name:
            block_name = repr(self.block_name)
        else:
            block_name = ""
        args = block_name
        args += " " + _to_string(self.body)
        return args

class DoNode(Node):
    def __init__(self, expr):
        self.expr = expr

    def get_node_args(self):
        return repr(self.expr)

class ImportNode(Node):
    pass

class BreakNode(Node):
    def __init__(self, block_name=None):
        assert_symbol(block_name)
        self.block_name = block_name

    def get_node_args(self):
        if self.block_name:
            return repr(self.block_name)
        else:
            return ""

class ContinueNode(Node):
    def __init__(self, block_name=None):
        assert_symbol(block_name)
        self.block_name = block_name

    def get_node_args(self):
        if self.block_name:
            return repr(self.block_name)
        else:
            return ""

class ReturnNode(Node):
    def __init__(self, value=None):
        self.value = value

    def get_node_args(self):
        if self.value:
            return repr(self.value)
        else:
            return ""

class AssertNode(Node):
    def __init__(self, expr):
        self.expr = expr

    def get_node_args(self):
        return repr(self.expr)

class ThrowNode(Node):
    def __init__(self, code, message=None):
        self.code = code
        self.message = message

    def get_node_args(self):
        if self.message is None:
            return "%r" % self.code
        else:
            return "%r, %r" % (self.code, self.message)

class FuncNode(Node):
    def __init__(self, funcname, args=None):
        self.funcname = funcname
        self.args = tuple(args or [])

    def get_node_args(self):
        return "%r(%s)" % (
            self.funcname,
            ", ".join([repr(arg) for arg in self.args]))

class VarNode(Node):
    def __init__(self, varname, typename, value=None):
        assert_symbol(varname)
        self.varname = varname
        self.typename = typename
        self.value = value

    def get_node_args(self):
        return "(%s, %s, %r)" % (self.varname, self.typename, self.value)

class ConstNode(Node):
    def __init__(self, varname, typename, value):
        self.varname = varname
        self.typename = typename
        self.value = value

    def get_node_args(self):
        return "(%s, %s, %r)" % (self.varname, self.typename, self.value)

class AliasNode(Node):
    def __init__(self, alias, typename):
        self.alias = alias
        self.typename = typename

    def get_node_args(self):
        return "(%s, %s)" % (self.alias, self.typename)

class CollectionTypeNode(Node):
    def __init__(self, **kw):
        pass

class DictTypeNode(Node):
    def __init__(self, **kw):
        pass

class FuncTypeNode(Node):
    def __init__(self, **kw):
        pass

class ArrayTypeNode(Node):
    def __init__(self, base_type, size):
        self.base_type = base_type
        self.size = tuple(size)

    def __repr__(self):
        return "".join(["[%s]" % (size and str(size) or "")
                        for size in self.size]) + repr(self.base_type)

class ClassNode(Node):
    class Member(object):
        def __init__(self, member, visibility, override):
            self.member = member
            self.visibility = visibility or ""
            self.override = override is not None

        def __repr__(self):
            return "".join([self.visibility,
                            "*" if self.override else "",
                            repr(self.member)])

    def __init__(self, name, parent=None, member=None, visibility=None, override=None):
        self.name = name
        self.parent = parent
        if member:
            if visibility is None:
                visibility = [None] * len(member)
            if override is None:
                override = [None] * len(member)
            members = [ClassNode.Member(m, v, o)
                       for m, v, o in zip(member, visibility, override)]
        else:
            members = []
        self.members = members

    def get_node_args(self):
        attrs = [repr(self.name)]
        if self.parent:
            attrs += [" : " + repr(self.parent)]
        members = [repr(member) for member in self.members]
        attrs += [" { ", ", ".join(members), " }"]
        return "".join(attrs)

class EnumNode(Node):
    def __init__(self, name, member):
        self.name = name
        self.member = OrderedDict()
        current_value = 0
        for i, (key, value) in enumerate(member):
            if value is None:
                value = current_value
            else:
                current_value = value
            self.member[key] = value
            current_value += 1

    def get_node_args(self):
        return "%r %r" % (self.name, self.member.items())
