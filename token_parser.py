
""".
"""
from pycparser import c_parser, c_ast
""".
"""

def assert_eq(in_str, chk_str, msg=None):
    """.
    """
    if in_str != chk_str:
        print in_str, "!=", chk_str

        if msg:
            print "msg:", msg

        raise

def process():
    """.
    """
    data = ""
    lines = open("token.cps").readlines()
    for line in lines:
        if not line.strip(" ").startswith("//"):
            data += line + "\n"
    chunks = data.split("END_STATE()")[:-1]

    return process_chunks(chunks)

def process_chunks(chunks):
    """.
    """
    transfer = {}

    for chunk in chunks:
        start = 0
        while chunk[start] != '(':
            start += 1
        end = start + 1
        while chunk[end] != ')':
            end += 1
        name = chunk[start+1:end]

        source = add_decl(chunk[end+1:])
        syntax_tree = build_tree(source)

        transfer[name] = analysis(name, syntax_tree)

    return transfer

def analysis(name, tree):
    """.
    """

    aly = Analysis(name, tree)
    aly.start()
    result = aly.result()

    return result

def build_tree(source):
    """.
    """
    parser = c_parser.CParser()
    ast = parser.parse(source)
    return ast.ext[-1].body

def add_decl(source):
    """.
    """
    prefix = """
                typedef int bool;
                typedef int StringBuilder;
                void func() {
             """
    suffix = "}"
    source = source.replace("auto ", "")
    source = source.replace("::", ".")
    return prefix + source + suffix


class Analysis(object):
    """.
    """
    def __init__(self, name, tree):
        """.
        """
        self.name = name
        self.tree = tree
        self.exprs = (c_ast.Compound,
                      c_ast.If,
                      c_ast.Return,
                      c_ast.FuncCall,
                      c_ast.For,
                      c_ast.UnaryOp,
                      c_ast.BinaryOp,
                      c_ast.Decl)
        self.next_steps = set()
        self.transfer = {}


    def f_decl(self, decl_t):
        """.
        """
        if type(decl_t) != c_ast.Decl:
            raise
        return self.init_returns()

    def f_assignment(self, assign_t):
        """.
        """
        if type(assign_t) != c_ast.Assignment:
            raise
        return self.init_returns()


    def f_return(self, op_r):
        """.
        """
        result = self.init_returns()
        if type(op_r.expr) == c_ast.ID:
            return result

        return self.call_for_expr(op_r.expr)

    def f_binaryop(self, op_t):
        """.
        """
        result = self.init_returns()

        def get_part(part):
            if type(part) == c_ast.StructRef:
                return ["true", [part.field.name]]
            if type(part) == c_ast.ID:
                return ["true", [part.name]]

            r_part = self.call_for_expr(part)
            assert_eq(r_part["is_cond"], True)
            return r_part["cond"]

        if op_t.op == "==":
            result["is_cond"] = True

            add = False
            if op_t.left.name in ["m_additionalAllowedCharacter", "result"]:
                add = True

            value = None
            if type(op_t.right) == c_ast.ID:
                value = op_t.right.name
            elif type(op_t.right) == c_ast.StructRef:
                value = op_t.right.field.name
            else:
                value = self.dequote(op_t.right.value)
                assert_eq(len(value), 1)

            if add:
                value = op_t.left.name + " equals " + value

            result["cond"] = ["true", [value]]

        elif op_t.op == "&&" or op_t.op == "||":
            result["is_cond"] = True

            left = get_part(op_t.left)
            right = get_part(op_t.right)

            result["cond"] = ["true", [self.add_cond(left, right, op_t.op)]]

        else:
            print op_t.op, "out of known op"
            raise


        return result

    def f_unaryop(self, op_t):
        """.
        """
        result = self.init_returns()

        if op_t.op == "!":
            result["is_cond"] = True

            assert_eq(type(op_t.expr), c_ast.FuncCall)
            r_expr = self.call_for_expr(op_t.expr)
            assert_eq(r_expr["is_cond"], True)
            result["cond"] = ["true", r_expr["cond"][1]]

        elif op_t.op == "+":
            return result

        else:
            print op_t.op, "out of known op"
            raise

        return result

    def f_funccall(self, func_t):
        """.
        """
        name = func_t.name
        if type(name) == c_ast.StructRef:
            name = name.field.name
        elif type(name) == c_ast.ID:
            name = name.name
        else:
            print "function name's type not kwown", type(name)
            raise

        args = None
        if func_t.args:
            args = func_t.args.exprs

        result = self.init_returns()

        # transfer
        if name in ["ADVANCE_TO", "SWITCH_TO", "RECONSUME_IN"]:
            assert_eq(len(args), 1)
            assert_eq(type(args[0]), c_ast.ID, name)
            result["is_transfer"] = True
            result["transfer"] = ["full", [], [args[0].name]]

        elif name == "emitEndOfFile":
            result["is_transfer"] = True
            result["transfer"] = ["full", [], ["ENDState"]]

        elif name in ["emitAndResumeInDataState",
                      "emitAndReconsumeInDataState",
                      "commitToCompleteEndTag"]:
            result["is_transfer"] = True
            result["transfer"] = ["full", [], ["DataState"]]
        elif name == "RETURN_IN_CURRENT_STATE":
            result["is_transfer"] = True
            result["transfer"] = ["full", [], [self.name]]

        # bool check
        elif name == "isASCIIAlphaCaselessEqual":
            result["is_cond"] = True
            result["cond"] = ["true", ["caseless equals " + args[1].value]]
        elif name == "haveBufferedCharacterToken":
            result["is_cond"] = True
            result["cond"] = ["true", ["if in chars mode(\"xxx\")"]]
        elif name == "isTokenizerWhitespace":
            result["is_cond"] = True
            result["cond"] = ["true", ["\\s \\xA \\x09 \\x0C"]]
        elif name == "isASCIIAlpha":
            result["is_cond"] = True
            result["cond"] = ["true", ["[a-zA-Z]"]]
        elif name == "processEntity":
            result["is_cond"] = True
            result["cond"] = ["true", ["if can decodedEntity, &(#123;)"]]
        elif name == "shouldAllowCDATA":
            result["is_cond"] = True
            result["cond"] = ["true", ["if allow CDATA"]]
        elif name == "isAppropriateEndTag":
            result["is_cond"] = True
            result["cond"] = ["true", ["if is AppropriateEndTag"]]
        elif name == "commitToPartialEndTag":
            result["is_cond"] = True
            result["cond"] = ["true", ["if can commitToPartialEndTag"]]
        elif name == "temporaryBufferIs":
            result["is_cond"] = True
            result["cond"] = ["true", ["if buffer str is script"]]

        #else

        #do nothing
        elif name in ["bufferCharacter", "bufferASCIICharacter",
                      "appendToTemporaryBuffer"]:
            pass
        elif name in ["beginEndTag", "clear", "beginEndTag",
                      "beginEndTag", "beginEndTag", "beginStartTag",
                      "parseError", "appendToName", "ASSERT",
                      "appendToPossibleEndTag", "appendToCharacter",
                      'beginAttribute', "appendToAttributeName",
                      "appendToAttributeValue", "toASCIILower",
                      "endAttribute", "setSelfClosing", "beginComment",
                      "appendToComment", "beginDOCTYPE", "setForceQuirks",
                      "setPublicIdentifierToEmptyString",
                      "appendToPublicIdentifier",
                      "setSystemIdentifierToEmptyString",
                      "appendToSystemIdentifier"]:
            pass

        else:
            print name, ", function name not in control"
            raise

        return result

    def f_if(self, if_t):
        """.
        """
        result = self.init_returns()
        result["is_transfer"] = True
        result["transfer"] = [None] * 3
        result["transfer"][0] = "full"
        result["transfer"][1] = []
        result["transfer"][2] = []
        true_chars = None

        cond = if_t.cond

        # hack for (!success)
        if type(cond) == c_ast.UnaryOp and type(cond.expr) == c_ast.ID:
            result["is_transfer"] = False
            return result

        if type(cond) == c_ast.ID:
            true_chars = ["true", [cond.name]]
        elif type(cond) in (c_ast.FuncCall, c_ast.BinaryOp, c_ast.UnaryOp):
            r_expr = self.call_for_expr(cond)
            assert_eq(r_expr["is_cond"], True, msg=cond)
            true_chars = r_expr["cond"]
        else:
            print "cond not allowed:", type(cond)
            print cond.show()
            raise

        r_t_expr = self.call_for_expr(if_t.iftrue)
        if r_t_expr["is_transfer"]:
            result["transfer"][2].append([true_chars[0], true_chars[1],
                                       self.get_transfer(r_t_expr)])


        if if_t.iffalse:
            r_f_expr = self.call_for_expr(if_t.iffalse)
            result["transfer"][2].append([
                self.type_not(true_chars[0]),
                true_chars[1], self.get_transfer(r_f_expr)])

        return result

    def f_compound(self, compound_t):
        """.
        """
        result = self.init_returns()

        items = compound_t.block_items
        for item in items:
            r_expr = self.call_for_expr(item)
            if r_expr["is_transfer"]:
                result["is_transfer"] = True
                if not result["transfer"]:
                    result["transfer"] = [None] * 3
                    result["transfer"][0] = "full"
                    result["transfer"][1] = []
                    result["transfer"][2] = []
                result["transfer"][2].append(
                    ["full", [], self.get_transfer(r_expr)])

        return result

    def start(self):
        """.
        """
        if type(self.tree) != c_ast.Compound:
            print self.tree.show()
            print "not in exprs"
            raise

        self.transfer = self.f_compound(self.tree)

    @staticmethod
    def dequote(chars):
        """.
        """
        if chars[0] != chars[-1] or len(chars) < 3:
            return chars
        if chars[0] in "\"'":
            chars = chars[1:-1]
            return chars.replace("\\", "")
        return chars


    @staticmethod
    def type_not(type_name):
        """.
        """
        if type_name == "true":
            return "false"
        else:
            return "true"

    @staticmethod
    def add_cond(one, other, opt):
        """.
        """
        one_str = ", ".join(one[1])
        if not one[0]:
            one_str = "not [ " + one_str
        other_str = ", ".join(other[1])
        if not other[0]:
            other_str = "not [ " + other_str

        return "( %s ) %s ( %s )" % (one_str, opt, other_str)

    @staticmethod
    def get_transfer(result):
        """.
        """
        assert_eq(result["is_transfer"], True)
        if result["transfer"][0] == "full":
            return result["transfer"][2]
        else:
            return result["transfer"]

    @staticmethod
    def init_returns():
        """
        transfer -->
            [type, [char, ...], next_transfer]
            [type, ["..."], next_transfer]

            type:   "full"
                    "true"
                   "false"
            full then chars is empty
        """
        result = {"is_transfer": False,
                  "transfer": [],
                  "is_cond": False,
                  "cond": [] \
                  }

        return result

    def call_for_expr(self, expr):
        """.
        """
        s_expr_type = str(type(expr))
        index = s_expr_type.find("c_ast.")
        class_attr = 'f_' + s_expr_type[index+6:-2].lower()
        c_method = getattr(self, class_attr)

        return c_method(expr)


    def result(self):
        """.
        """
        return self.transfer


if __name__ == "__main__":
    print process()
    #item = trees["TagOpenState"].block_items[0]
