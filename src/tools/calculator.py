"""calculator tool.

Deterministic arithmetic, delegated away from the LLM. Used when the
synthesis step needs to compare numeric pricing (e.g. cost at a given
transaction volume) — the LLM decides *what* to compute, this tool computes
the exact answer instead of letting the model do mental math.

Only a restricted arithmetic grammar is evaluated (numbers, + - * / ()
and whitespace) — this is not a general `eval`.
"""

from __future__ import annotations

import ast
import operator

from src.tools.base import ToolError

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class CalculatorTool:
    name = "calculator"

    async def execute(self, expression: str) -> float:
        try:
            tree = ast.parse(expression, mode="eval")
            return self._eval_node(tree.body)
        except (SyntaxError, TypeError, ZeroDivisionError, KeyError) as exc:
            raise ToolError("SCHEMA_ERROR", f"Invalid expression '{expression}': {exc}") from exc

    def _eval_node(self, node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return _ALLOWED_OPERATORS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[type(node.op)](self._eval_node(node.operand))
        raise ToolError("SCHEMA_ERROR", f"Disallowed expression element: {ast.dump(node)}")
