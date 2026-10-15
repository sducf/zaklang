"""Private Python AST lowering for the checked Zak subset."""

from __future__ import annotations

import ast as py
from dataclasses import dataclass

from . import ast as zak
from .semantic import AnalysisResult

# Uppercase identifiers cannot be spelled by Zak's lowercase-only NAME token.
_BUILTINS = '_ZAK_builtins'


def _name(identifier: str, *, store: bool = False) -> py.Name:
    """Build a variable read, or an assignment binding when ``store`` is true."""
    return py.Name(id=identifier, ctx=py.Store() if store else py.Load())


def _attribute(value: py.expr, name: str) -> py.Attribute:
    return py.Attribute(value=value, attr=name, ctx=py.Load())


def _call(function: py.expr, *arguments: py.expr) -> py.Call:
    return py.Call(func=function, args=list(arguments), keywords=[])


def _builtin(name: str, *arguments: py.expr) -> py.Call:
    """Qualify a Python builtin so user-defined Zak names cannot shadow it."""
    return _call(_attribute(_name(_BUILTINS), name), *arguments)


@dataclass(frozen=True)
class _Binding:
    """Connect a lexical Zak variable to its Python name and module ownership."""

    identifier: str
    module: bool


class PythonEmitter:
    """One-shot emitter; every invocation owns its counters and lexical scopes."""

    def __init__(self, program: zak.Program, analysis: AnalysisResult):
        """Initialize emission state for this exact, successfully analyzed AST."""
        self.program = program
        self.types = analysis.expression_types
        self.scopes: list[dict[str, _Binding]] = [{}]
        self.next_variable = 0
        self.functions = {
            node.name: f'_ZAK_f{index}'
            for index, node in enumerate(n for n in program.statements if isinstance(n, zak.Function))
        }
        self.global_writes: set[str] | None = None
        self.needs_join = False

    def declare(self, name: str) -> _Binding:
        """Introduce a fresh Python identifier in the current lexical scope."""
        binding = _Binding(f'_ZAK_v{self.next_variable}', len(self.scopes) == 1)
        self.next_variable += 1
        self.scopes[-1][name] = binding

        return binding

    def lookup(self, name: str) -> _Binding:
        """Resolve the nearest binding; an absent name indicates invalid input."""
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]

        raise ValueError(f'Unresolved checked binding: {name}')

    def block(self, statements: tuple[zak.Statement, ...], *, child: bool = True) -> list[py.stmt]:
        """Lower a block, restoring scope on exit and inserting pass if empty.

        Functions and for loops already establish their parameter/loop scope;
        they pass ``child=False`` so their bodies share those bindings.
        """
        if child:
            self.scopes.append({})
        try:
            return [self.statement(node) for node in statements] or [py.Pass()]
        finally:
            if child:
                self.scopes.pop()

    def target(self, node: zak.Name | zak.Index) -> py.Name | py.Subscript:
        """Build a writable target and record module-name rebinding in functions.

        Mutating an indexed collection does not rebind its variable, so only
        direct name targets contribute to the function's global declaration.
        """
        if isinstance(node, zak.Name):
            binding = self.lookup(node.name)
            if binding.module and self.global_writes is not None:
                self.global_writes.add(binding.identifier)
            return _name(binding.identifier, store=True)
        return py.Subscript(value=self.expression(node.collection),
                            slice=self.expression(node.index), ctx=py.Store())

    def operator(self, operator: str, type_: zak.Type) -> py.operator:
        """Choose arithmetic operators, preserving I floor division and R division."""
        if operator == '/':
            return py.FloorDiv() if type_ == zak.I else py.Div()
        return {'+': py.Add, '-': py.Sub, '*': py.Mult, '%': py.Mod}[operator]()

    def statement(self, node: zak.Statement) -> py.stmt:
        """Lower one checked statement while maintaining lexical binding state."""
        if isinstance(node, zak.Declaration):
            # Resolve the initializer before introducing a shadowing binding.
            value = self.expression(node.value)
            binding = self.declare(node.name)
            return py.Assign(targets=[_name(binding.identifier, store=True)], value=value)
        if isinstance(node, zak.Assignment):
            assignment_target = self.target(node.target)
            value = self.expression(node.value)
            if node.operator == '=':
                return py.Assign(targets=[assignment_target], value=value)
            return py.AugAssign(target=assignment_target, op=self.operator(node.operator[:-1], self.types[id(node.target)]), value=value)
        if isinstance(node, zak.Append):
            return py.Expr(value=_call(_attribute(self.expression(node.target), 'append'), self.expression(node.value)))
        if isinstance(node, zak.Return):
            return py.Return(value=self.expression(node.value))
        if isinstance(node, zak.Break):
            return py.Break()
        if isinstance(node, zak.Continue):
            return py.Continue()
        if isinstance(node, zak.Call):
            return py.Expr(value=self.call(node))
        if isinstance(node, zak.If):
            return py.If(test=self.expression(node.condition), body=self.block(node.then_body),
                         orelse=self.block(node.else_body) if node.else_body else [])
        if isinstance(node, zak.While):
            return py.While(test=self.expression(node.condition), body=self.block(node.body), orelse=[])
        if isinstance(node, zak.For):
            iteration = node.iteration
            iterable = self.expression(iteration.start)
            if iteration.stop is not None:
                iterable = _builtin('range', iterable, self.expression(iteration.stop))
            elif len(node.names) == 2:
                iterable = _call(_attribute(iterable, 'items'))
            self.scopes.append({})
            try:
                names: list[py.expr] = [_name(self.declare(name).identifier, store=True) for name in node.names]
                loop_target = names[0] if len(names) == 1 else py.Tuple(elts=names, ctx=py.Store())
                body = self.block(node.body, child=False)
            finally:
                self.scopes.pop()
            return py.For(target=loop_target, iter=iterable, body=body, orelse=[], type_comment=None)
        if isinstance(node, zak.Function):
            return self.function(node)
        raise ValueError(f'Unsupported checked statement: {type(node).__name__}')

    def function(self, node: zak.Function) -> py.FunctionDef:
        """Lower a function with local parameters and explicit module rebindings.

        Names are preassigned for recursive/forward calls. Global writes are
        collected while lowering the body, then declared before any reads.
        """
        self.scopes.append({})
        previous_writes = self.global_writes
        self.global_writes = set()
        try:
            arguments = [py.arg(arg=self.declare(parameter.name).identifier) for parameter in node.parameters]
            body = self.block(node.body, child=False)
            if self.global_writes:
                body.insert(0, py.Global(names=sorted(self.global_writes)))
        finally:
            self.scopes.pop()
            self.global_writes = previous_writes
        return py.FunctionDef(name=self.functions[node.name],
                              args=py.arguments(posonlyargs=[], args=arguments, kwonlyargs=[], kw_defaults=[], defaults=[]),
                              body=body, decorator_list=[], returns=None, type_comment=None, type_params=[])

    def expression(self, node: zak.Expression) -> py.expr:
        """Translate an expression without executing it or changing evaluation order.

        Python AST nodes handle precedence, short circuiting, and literal
        escaping; semantic metadata supplies types for arithmetic lowering.
        """
        if isinstance(node, zak.Literal):
            return py.Constant(value=node.value)
        if isinstance(node, zak.Name):
            return _name(self.lookup(node.name).identifier)
        if isinstance(node, zak.Array):
            return py.List(elts=[self.expression(value) for value in node.elements], ctx=py.Load())
        if isinstance(node, zak.Map):
            return py.Dict(keys=[self.expression(key) for key, _ in node.entries],
                           values=[self.expression(value) for _, value in node.entries])
        if isinstance(node, zak.Unary):
            value = self.expression(node.operand)
            if node.operator == '#':
                return _builtin('len', value)
            return py.UnaryOp(op=py.Not() if node.operator == '!' else py.USub(), operand=value)
        if isinstance(node, zak.Binary):
            left, right = self.expression(node.left), self.expression(node.right)
            if node.operator in ('&', '|'):
                return py.BoolOp(op=py.And() if node.operator == '&' else py.Or(), values=[left, right])
            comparisons = {'==': py.Eq, '!=': py.NotEq, '<': py.Lt, '<=': py.LtE, '>': py.Gt, '>=': py.GtE, '@': py.In}
            if node.operator in comparisons:
                return py.Compare(left=left, ops=[comparisons[node.operator]()], comparators=[right])
            return py.BinOp(left=left, op=self.operator(node.operator, self.types[id(node.left)]), right=right)
        if isinstance(node, zak.Conditional):
            return py.IfExp(test=self.expression(node.condition), body=self.expression(node.then_value),
                            orelse=self.expression(node.else_value))
        if isinstance(node, zak.Index):
            return py.Subscript(value=self.expression(node.collection), slice=self.expression(node.index), ctx=py.Load())
        if isinstance(node, zak.Slice):
            return py.Subscript(value=self.expression(node.collection),
                                slice=py.Slice(lower=self.expression(node.lower) if node.lower is not None else None,
                                               upper=self.expression(node.upper) if node.upper is not None else None), ctx=py.Load())
        if isinstance(node, zak.Cast):
            if not isinstance(node.type, zak.PrimitiveType):
                raise ValueError('A checked cast must have a primitive target type.')
            return _builtin({zak.I: 'int', zak.R: 'float', zak.S: 'str', zak.B: 'bool'}[node.type], self.expression(node.value))
        if isinstance(node, zak.Call):
            return self.call(node)
        raise ValueError(f'Unsupported checked expression: {type(node).__name__}')

    def call(self, node: zak.Call) -> py.expr:
        """Lower user calls and builtin operations to standalone Python expressions.

        Container builtins preserve their declared result types. The join
        helper preserves argument order despite Python's receiver-first syntax.
        """
        arguments = [self.expression(value) for value in node.arguments]
        if node.name in self.functions:
            return _call(_name(self.functions[node.name]), *arguments)
        name = node.name
        if name in ('out', 'abs', 'min', 'max', 'srt'):
            return _builtin({'out': 'print', 'srt': 'sorted'}.get(name, name), *arguments)
        if name == 'sum':
            array_type = self.types[id(node.arguments[0])]
            if not isinstance(array_type, zak.ArrayType):
                raise ValueError('A checked sum argument must have an array type.')
            return _builtin('sum', arguments[0], py.Constant(value=0.0 if array_type.element == zak.R else 0))
        if name == 'rev':
            return _builtin('list', _builtin('reversed', arguments[0]))
        if name in ('keys', 'vals'):
            return _builtin('list', _call(_attribute(arguments[0], 'keys' if name == 'keys' else 'values')))
        if name in ('pop', 'del'):
            return _call(_attribute(arguments[0], 'pop'), *arguments[1:])
        if name in ('spl', 'up', 'lo'):
            return _call(_attribute(arguments[0], {'spl': 'split', 'up': 'upper', 'lo': 'lower'}[name]), *arguments[1:])
        if name == 'jn':
            # A helper preserves source argument order: values before delimiter.
            self.needs_join = True
            return _call(_name('_ZAK_join'), *arguments)
        raise ValueError(f'Unsupported checked builtin: {name}')

    def emit(self) -> str:
        """Render a module with helpers, hoisted functions, code, and function exports.

        Traverse in source order first so name resolution matches the checker;
        hoisting only rearranges the completed Python function definitions.
        Fresh emitter state and ordered traversal make output reproducible.
        """
        functions, statements = [], []
        for node in self.program.statements:
            rendered = self.statement(node)
            (functions if isinstance(node, zak.Function) else statements).append(rendered)
        exports = [py.Assign(targets=[py.Subscript(value=_builtin('globals'), slice=py.Constant(value=name), ctx=py.Store())],
                             value=_name(identifier)) for name, identifier in self.functions.items()]
        helpers = []
        if self.needs_join:
            helpers = py.parse('def _ZAK_join(values, delimiter):\n    return delimiter.join(values)\n').body
        module = py.Module(body=[py.Import(names=[py.alias(name='builtins', asname=_BUILTINS)])] + helpers + functions + statements + exports,
                           type_ignores=[])
        return py.unparse(py.fix_missing_locations(module)) + '\n'
