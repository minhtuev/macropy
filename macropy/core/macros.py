import sys
import imp
import ast
from ast import *
from macropy.core.core import *
from util import *


class Placeholder(AST):
    def __repr__(self):
        return "Placeholder()"


def expr_macro(func):
    Macros.expr_registry[func.func_name] = func


def block_macro(func):
    Macros.block_registry[func.func_name] = func


expr.__repr__ = lambda self: ast.dump(self, annotate_fields=False)
stmt.__repr__ = lambda self: ast.dump(self, annotate_fields=False)
comprehension.__repr__ = lambda self: ast.dump(self, annotate_fields=False)


def interp_ast(node, values):
    def v(): return values

    @Walker
    def func(node):
        if type(node) is Placeholder:
            val = v().pop(0)
            if isinstance(val, AST):
                return val
            else:
                x = ast_repr(val)
                return x
        else:
            return node

    x = func.recurse(node)
    return x

class Walker(object):
    def __init__(self, func, autorecurse=True):
        self.func = func
        self.autorecurse = autorecurse

    def walk_children(self, node):
        for field, old_value in list(iter_fields(node)):
            old_value = getattr(node, field, None)
            new_value = self.recurse(old_value)
            setattr(node, field, new_value)

    def recurse(self, node):
        if type(node) is list:
            return flatten([
                self.recurse(x)
                for x in node
            ])

        elif type(node) is comprehension:
            self.walk_children(node)
            return node
        elif isinstance(node, AST):
            node = self.func(node)
            if self.autorecurse:
                if type(node) is list:
                    return self.recurse(node)
                else:
                    self.walk_children(node)
                    return node
            else:
                return node
        else:
            return node

@singleton
class Macros(object):
    expr_registry = {}
    block_registry = {}


class MacroLoader(object):
    def __init__(self, module_name, txt, file_name):
        self.module_name = module_name
        self.txt = txt
        self.file_name = file_name

    def load_module(self, fullname):
        a = expand_ast(ast.parse(self.txt))
        code = unparse(a)
        ispkg = False
        mod = sys.modules.setdefault(fullname, imp.new_module(fullname))
        mod.__loader__ = self
        if ispkg:
            mod.__path__ = []
            mod.__package__ = fullname
        else:
            mod.__package__ = fullname.rpartition('.')[0]
        exec(compile(code, self.file_name, "exec"), mod.__dict__)
        return mod


def expand_ast(node):
    @Walker
    def macro_search(node):

        if (isinstance(node, With)
            and type(node.context_expr) is Name 
            and node.context_expr.id in Macros.block_registry):

            return Macros.block_registry[node.context_expr.id](node)

        if      isinstance(node, BinOp) \
                and type(node.left) is Name \
                and type(node.op) is Mod \
                and node.left.id in Macros.expr_registry:

            return Macros.expr_registry[node.left.id](node.right)

        return node
    node = macro_search.recurse(node)

    return node

@singleton
class MacroFinder(object):
    def find_module(self, module_name, package_path):
        if module_name in sys.modules:
            return None

        if "macropy" in str(package_path):
            try:
                (file, pathname, description) = imp.find_module(module_name.split('.')[-1], package_path)
                txt = file.read()

                return MacroLoader(module_name, txt, file.name)
            except Exception, e:
                pass


sys.meta_path.append(MacroFinder)
