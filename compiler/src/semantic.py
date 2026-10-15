"""Static name, type, and control-flow validation for the SD1 subset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from . import ast as a
from .errors import CompileError

BUILTINS = frozenset({"abs", "min", "max", "sum", "srt", "rev", "keys", "vals", "pop", "del", "spl", "jn", "up", "lo", "out"})


@dataclass(frozen=True)
class AnalysisResult:
    """Types keyed by node identity, valid only for the analyzed AST's lifetime.

    Metadata from a failed analysis is partial and must not be used to emit
    code. The AST remains unchanged; separate analyses own separate mappings.
    """

    errors: list[CompileError]
    expression_types: dict[int, a.Type]


def type_name(type_: a.Type) -> str:
    """Format nested types using Zak notation for diagnostic messages."""
    if isinstance(type_, a.ArrayType):
        return f"[{type_name(type_.element)}]"
   
    if isinstance(type_, a.MapType):
        return f"{{{type_name(type_.key)}:{type_name(type_.value)}}}"
   
    return type_.name

class _Invalid(Exception):
    """Unwind one failed statement while preserving its located diagnostic."""
    def __init__(self, error: CompileError):
        self.error = error

class _Checker:
    """Track lexical types and validate each independent statement in a program."""

    def __init__(self):
        self.errors: list[CompileError] = []
        self.expression_types: dict[int, a.Type] = {}
        self.scopes: list[dict[str, a.Type]] = [{}]
        self.functions: dict[str, a.Function] = {}
        self.return_type: a.Type | None = None
        self.loop_depth = 0

    def fail(self, node: a.Node, code: str, message: str) -> NoReturn:
        """Stop the current check with an error at the responsible AST node."""
        raise _Invalid(CompileError(node.span.line, node.span.col, code, message))

    def expect(self, node: a.Node, actual: a.Type, expected: a.Type):
        """Require exact type equality; Zak never inserts implicit conversions."""

        if actual != expected:
            self.fail(node, "TYPE_MISMATCH", f"Expected {type_name(expected)}, got {type_name(actual)}.")

    def validate_type(self, node: a.Node, type_: a.Type):
        """Validate nested container annotations, including the I/S map-key rule."""

        if isinstance(type_, a.ArrayType):
            self.validate_type(node, type_.element)
        elif isinstance(type_, a.MapType):
            if type_.key not in (a.I, a.S):
                self.fail(node, "INVALID_TYPE", "Map keys must have type I or S.")
            self.validate_type(node, type_.value)

    def bind(self, node: a.Node, name: str, type_: a.Type):
        """Declare a lexical binding, rejecting duplicates and reserved function names."""
        if name in BUILTINS or name in self.functions:
            self.fail(node, "RESERVED_NAME", f"'{name}' is a function name.")

        if name in self.scopes[-1]:
            self.fail(node, "DUPLICATE_NAME", f"'{name}' is already declared in this scope.")

        self.scopes[-1][name] = type_

    def lookup(self, node: a.Node, name: str) -> a.Type:
        """Find the nearest visible variable type or report an undefined name."""

        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]

        self.fail(node, "UNDEFINED_NAME", f"Undefined name '{name}'.")

    def block(self, statements: tuple[a.Statement, ...], *, child: bool = True):
        """Check a block and retain errors from independently checkable statements.

        A child scope is discarded even on failure. Function and loop callers
        can reuse the scope they already created by passing ``child=False``.
        """

        if child:
            self.scopes.append({})
        try:
            for statement in statements:
                try:
                    self.statement(statement)
                except _Invalid as error:
                    self.errors.append(error.error)
        finally:
            if child:
                self.scopes.pop()

    def statement(self, node: a.Statement):
        """Validate a statement's types, bindings, and control-flow context."""

        if isinstance(node, a.Declaration):
            if node.declared_type is not None:
                self.validate_type(node, node.declared_type)

            type_ = self.value(node.value, node.declared_type)
            self.bind(node, node.name, type_)
        elif isinstance(node, a.Assignment):
            target = self.target(node.target)
            value = self.value(node.value, target)
            if node.operator != "=":
                self.binary(node, target, node.operator[:-1], value)
        elif isinstance(node, a.Append):
            target = self.target(node.target)
           
            if not isinstance(target, a.ArrayType):
                self.fail(node.target, "TYPE_MISMATCH", "Append requires an array.")
            self.value(node.value, target.element)
        elif isinstance(node, a.Return):
            if self.return_type is None:
                self.fail(node, "INVALID_CONTROL_FLOW", "Return is only valid inside a function.")
            self.value(node.value, self.return_type)
        elif isinstance(node, (a.Break, a.Continue)):
            if not self.loop_depth:
                self.fail(node, "INVALID_CONTROL_FLOW", "Break/continue requires an enclosing loop.")
        elif isinstance(node, a.If):
            self.value(node.condition, a.B)
            self.block(node.then_body)
            self.block(node.else_body)
        elif isinstance(node, a.While):
            self.value(node.condition, a.B)
            self.loop_depth += 1
            try:
                self.block(node.body)
            finally:
                self.loop_depth -= 1
        elif isinstance(node, a.For):
            types = self.iteration(node.iteration, len(node.names))
            self.scopes.append({})
            self.loop_depth += 1
            
            try:
                for name, type_ in zip(node.names, types):
                    self.bind(node, name, type_)
                self.block(node.body, child=False)
            finally:
                self.loop_depth -= 1
                self.scopes.pop()
        elif isinstance(node, a.Function):
            self.function(node)
        elif isinstance(node, a.Call):
            self.call(node)
        else:
            self.fail(node, "UNSUPPORTED_FEATURE", "Unsupported statement.")

    def function(self, node: a.Function):
        """Check parameter scope, return types, and guaranteed return paths.

        Functions cannot inherit loop permissions from their definition site;
        their return/loop context is restored after the body is checked.
        """
        
        if len(self.scopes) != 1 or self.return_type is not None:
            self.fail(node, "UNSUPPORTED_FEATURE", "Functions must be declared at top level.")
        
        self.validate_type(node, node.return_type)
        saved_return, saved_loop = self.return_type, self.loop_depth
        self.return_type, self.loop_depth = node.return_type, 0
        self.scopes.append({})
        
        try:
            for parameter in node.parameters:
                self.validate_type(parameter, parameter.type)
                self.bind(parameter, parameter.name, parameter.type)
            self.block(node.body, child=False)
            
            if not self.returns(node.body):
                self.fail(node, "MISSING_RETURN", f"Function '{node.name}' must return on every path.")
        finally:
            self.scopes.pop()
            self.return_type, self.loop_depth = saved_return, saved_loop

    def returns(self, statements: tuple[a.Statement, ...]) -> bool:
        """Conservatively prove return via a return statement or both if branches.

        Loops are not proof: their execution or termination is not guaranteed.
        """
        
        for node in statements:
            if isinstance(node, a.Return):
                return True
            if isinstance(node, a.If) and self.returns(node.then_body) and self.returns(node.else_body):
                return True
        return False

    def iteration(self, node: a.Iteration, count: int) -> tuple[a.Type, ...]:
        """Validate an iterable/range and derive the loop-variable types."""
        
        if node.stop is not None:
            self.value(node.start, a.I)
            self.value(node.stop, a.I)
            types = (a.I,)
        else:
            type_ = self.value(node.start)
            if isinstance(type_, a.ArrayType):
                types = (type_.element,)
            elif type_ == a.S:
                types = (a.S,)
            elif isinstance(type_, a.MapType):
                types = (type_.key, type_.value) if count == 2 else (type_.key,)
            else:
                self.fail(node, "INVALID_ITERATION", "Iteration requires an array, string, map, or integer range.")
        if count != len(types):
            self.fail(node, "INVALID_ITERATION", "Two iteration variables require a map.")
        return types

    def target(self, node: a.Name | a.Index) -> a.Type:
        """Check a variable-rooted writable target and record its resolved type."""
        if isinstance(node, a.Name):
            type_ = self.lookup(node, node.name)
        else:
            if not isinstance(node.collection, (a.Name, a.Index)):
                self.fail(node, "INVALID_TARGET", "Assignment targets must be rooted in a variable.")
         
            collection = self.target(node.collection)
         
            if collection == a.S:
                self.fail(node, "INVALID_TARGET", "Strings cannot be mutated.")
    
            type_ = self.index(node, collection)
   
        self.expression_types[id(node)] = type_
   
        return type_

    def index(self, node: a.Index, collection: a.Type) -> a.Type:
        """Check the index/key type and return the selected value's static type."""
        if isinstance(collection, a.MapType):
            self.value(node.index, collection.key)
            return collection.value
        if isinstance(collection, a.ArrayType):
            self.value(node.index, a.I)
            return collection.element
        if collection == a.S:
            self.value(node.index, a.I)
            return a.S
    
        self.fail(node, "TYPE_MISMATCH", "Indexing requires an array, string, or map.")

    def value(self, node: a.Expression, expected: a.Type | None = None) -> a.Type:
        """Check a value expression, reject void, and retain its inferred type.

        Expected types provide context for empty containers and typed calls;
        they constrain inference rather than authorizing type conversion.
        """
        type_ = self.expression(node, expected)
        
        if type_ == a.VOID:
            self.fail(node, "VOID_VALUE", "This call does not return a value.")
        
        if expected is not None:
            self.expect(node, type_, expected)
        
        self.expression_types[id(node)] = type_
        
        return type_

    def expression(self, node: a.Expression, expected: a.Type | None) -> a.Type:
        """Infer an expression type, using context for otherwise ambiguous containers."""
        if isinstance(node, a.Literal):
            return node.type
        if isinstance(node, a.Name):
            return self.lookup(node, node.name)
        if isinstance(node, a.Array):
            element = expected.element if isinstance(expected, a.ArrayType) else None
       
            for item in node.elements:
                current = self.value(item, element)
                element = current if element is None else element
       
            if element is None:
                self.fail(node, "CANNOT_INFER_TYPE", "An empty array requires a contextual array type.")
       
            return a.ArrayType(element)
        if isinstance(node, a.Map):
            key = expected.key if isinstance(expected, a.MapType) else None
            value = expected.value if isinstance(expected, a.MapType) else None
       
            for k, v in node.entries:
                current_key, current_value = self.value(k, key), self.value(v, value)
                key = current_key if key is None else key
                value = current_value if value is None else value
       
                if key not in (a.I, a.S):
                    self.fail(k, "INVALID_TYPE", "Map keys must have type I or S.")
       
            if key is None or value is None:
                self.fail(node, "CANNOT_INFER_TYPE", "An empty map requires a contextual map type.")
       
            return a.MapType(key, value)
        if isinstance(node, a.Unary):
            type_ = self.value(node.operand)
       
            if node.operator == "!":
                self.expect(node, type_, a.B)
                return a.B
          
            if node.operator == "#":
                if not isinstance(type_, (a.ArrayType, a.MapType)) and type_ != a.S:
                    self.fail(node, "TYPE_MISMATCH", "Length requires an array, string, or map.")
                return a.I
          
            if type_ not in (a.I, a.R):
                self.fail(node, "TYPE_MISMATCH", "Negation requires I or R.")
          
            return type_
        if isinstance(node, a.Binary):
            if node.operator == "@":
                left = self.value(node.left)
                right = self.value(node.right)
          
                return self.binary(node, left, node.operator, right)
          
            context = expected if node.operator == "+" else None
          
            try:
                left = self.value(node.left, context)
            except _Invalid as error:
                if error.error.code != "CANNOT_INFER_TYPE":
                    raise
                # A typed right operand can establish the empty left type.
                right = self.value(node.right, context)
                left = self.value(node.left, right)
            else:
                right = self.value(node.right, left)

            return self.binary(node, left, node.operator, right)

        if isinstance(node, a.Conditional):
            self.value(node.condition, a.B)
            then = self.value(node.then_value, expected)
            self.value(node.else_value, then)
            return then

        if isinstance(node, a.Index):
            return self.index(node, self.value(node.collection))

        if isinstance(node, a.Slice):
            collection = self.value(node.collection)
            if collection != a.S and not isinstance(collection, a.ArrayType):
                self.fail(node, "TYPE_MISMATCH", "Slicing requires an array or string.")
            for bound in (node.lower, node.upper):
                if bound is not None:
                    self.value(bound, a.I)
            return collection

        if isinstance(node, a.Cast):
            source = self.value(node.value)
            if not isinstance(source, a.PrimitiveType):
                self.fail(node, "TYPE_MISMATCH", "Casts require a primitive value.")
            return node.type

        if isinstance(node, a.Call):
            return self.call(node)

        if isinstance(node, a.Comprehension):
            self.fail(node, "UNSUPPORTED_FEATURE", "Comprehensions are outside the SD1 compiler subset.")

        self.fail(node, "UNSUPPORTED_FEATURE", "Unsupported expression.")

    def binary(self, node: a.Node, left: a.Type, operator: str, right: a.Type) -> a.Type:
        """Validate an operator's operand types and derive its result type."""

        if operator == "@":
            if isinstance(right, a.MapType):
                self.expect(node, left, right.key)
            elif isinstance(right, a.ArrayType):
                self.expect(node, left, right.element)
            elif right == a.S:
                self.expect(node, left, a.S)
            else:
                self.fail(node, "TYPE_MISMATCH", "Membership requires an array, string, or map.")
            return a.B

        self.expect(node, right, left)

        if operator in ("&", "|"):
            self.expect(node, left, a.B)
            return a.B

        if operator in ("==", "!="):
            return a.B

        if operator in ("<", "<=", ">", ">="):
            if left not in (a.I, a.R, a.S):
                self.fail(node, "TYPE_MISMATCH", "Ordering requires matching numeric or string values.")
            return a.B

        if operator == "+" and (left == a.S or isinstance(left, a.ArrayType)):
            return left

        if left not in (a.I, a.R):
            self.fail(node, "TYPE_MISMATCH", "Arithmetic requires matching numeric values.")
        return left

    def arity(self, node: a.Call, count: int):
        if len(node.arguments) != count:
            self.fail(node, "CALL_ARITY", f"'{node.name}' expects {count} argument(s), got {len(node.arguments)}.")

    def call(self, node: a.Call) -> a.Type:
        """Check a call and retain its result type, including void statement calls."""
        type_ = self._call(node)
        self.expression_types[id(node)] = type_
        return type_

    def _call(self, node: a.Call) -> a.Type:
        """Apply declared function signatures or the supported builtin type rules."""
        if node.name in self.functions:
            function = self.functions[node.name]
            self.arity(node, len(function.parameters))
            for argument, parameter in zip(node.arguments, function.parameters):
                self.value(argument, parameter.type)
            return function.return_type
       
        if node.name not in BUILTINS:
            self.fail(node, "UNDEFINED_NAME", f"Undefined function '{node.name}'.")
       
        name = node.name
        self.arity(node, 2 if name in ("min", "max", "spl", "jn", "del") else 1)
       
        if name == "jn":
            self.value(node.arguments[0], a.ArrayType(a.S))
            self.value(node.arguments[1], a.S)
            return a.S
        first = self.value(node.arguments[0])
       
        if name == "out":
            return a.VOID
       
        if name in ("abs", "min", "max"):
            if first not in (a.I, a.R):
                self.fail(node, "TYPE_MISMATCH", f"'{name}' requires numeric values.")
            if len(node.arguments) == 2:
                self.value(node.arguments[1], first)
            return first
   
        if name in ("up", "lo", "spl"):
            self.expect(node.arguments[0], first, a.S)
            if name == "spl":
                self.value(node.arguments[1], a.S)
                return a.ArrayType(a.S)
            return a.S
   
        if name in ("keys", "vals", "del"):
            if not isinstance(first, a.MapType):
                self.fail(node, "TYPE_MISMATCH", f"'{name}' requires a map.")
            if name == "del":
                self.value(node.arguments[1], first.key)
                return a.VOID
            return a.ArrayType(first.key if name == "keys" else first.value)
       
        if not isinstance(first, a.ArrayType):
            self.fail(node, "TYPE_MISMATCH", f"'{name}' requires an array.")
       
        if name == "sum":
            if first.element not in (a.I, a.R):
                self.fail(node, "TYPE_MISMATCH", "'sum' requires an array of I or R.")
            return first.element
       
        if name == "srt" and first.element not in (a.I, a.R, a.S):
            self.fail(node, "TYPE_MISMATCH", "'srt' requires an array of I, R, or S.")
        return first.element if name == "pop" else first


def analyze(program: a.Program) -> AnalysisResult:
    """Validate a program and collect types for downstream compiler stages.

    Register top-level function signatures first to allow recursion and forward
    calls. Each run owns its scopes and node-identity metadata; failed analyses
    return partial metadata that callers must not use to emit code.
    """
    checker = _Checker()
    for node in program.statements:
        if isinstance(node, a.Function):
            if node.name in BUILTINS:
                checker.errors.append(CompileError(node.span.line, node.span.col, "RESERVED_NAME", f"'{node.name}' is a builtin name."))
            elif node.name in checker.functions:
                checker.errors.append(CompileError(node.span.line, node.span.col, "DUPLICATE_NAME", f"Function '{node.name}' is already defined."))
            else:
                checker.functions[node.name] = node
    checker.block(program.statements, child=False)
    return AnalysisResult(checker.errors, checker.expression_types)


def check(program: a.Program) -> list[CompileError]:
    """Check one program without running it; independent statement errors accumulate."""
    return analyze(program).errors
