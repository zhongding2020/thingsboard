import ast
import operator
from process_opt.knowledge.base import ProcessTemplate, Rule, RuleType


class RuleCheck:
    def __init__(self, rule: Rule) -> None:
        self.rule = rule
        self.triggered = False
        self.violation = ""


class RuleEngine:
    _OPS: dict[type, object] = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.And: all,
        ast.Or: any,
    }

    def check_params(
        self, template: ProcessTemplate, params: dict[str, float]
    ) -> list[RuleCheck]:
        results: list[RuleCheck] = []
        for rule in template.rules:
            check = RuleCheck(rule)
            check.triggered = self._evaluate(rule.expression, params)
            if check.triggered:
                check.violation = rule.message
            results.append(check)
        return results

    def get_violations(
        self, checks: list[RuleCheck], severity: RuleType | None = None
    ) -> list[str]:
        messages: list[str] = []
        for c in checks:
            if not c.triggered:
                continue
            if severity and c.rule.type != severity:
                continue
            messages.append(c.rule.message)
        return messages

    @staticmethod
    def _evaluate(expression: str, params: dict[str, float]) -> bool:
        safe: dict[str, float] = {}
        for k, v in params.items():
            safe[k.replace("-", "_").replace(" ", "_")] = v
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            return bool(RuleEngine._eval_node(tree.body, safe))
        except Exception:
            return False

    @staticmethod
    def _eval_node(node: ast.AST, scope: dict[str, float]) -> object:
        if isinstance(node, ast.BoolOp):
            values = [RuleEngine._eval_node(v, scope) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
            raise ValueError(f"Unsupported BoolOp: {node.op}")

        if isinstance(node, ast.Compare):
            left = RuleEngine._eval_node(node.left, scope)
            result = True
            for op, comparator in zip(node.ops, node.comparators):
                right = RuleEngine._eval_node(comparator, scope)
                if isinstance(op, ast.Gt):
                    result = result and (float(left) > float(right))
                elif isinstance(op, ast.GtE):
                    result = result and (float(left) >= float(right))
                elif isinstance(op, ast.Lt):
                    result = result and (float(left) < float(right))
                elif isinstance(op, ast.LtE):
                    result = result and (float(left) <= float(right))
                elif isinstance(op, ast.Eq):
                    result = result and (float(left) == float(right))
                elif isinstance(op, ast.NotEq):
                    result = result and (float(left) != float(right))
                else:
                    raise ValueError(f"Unsupported Compare op: {op}")
            return result

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id in scope:
                return scope[node.id]
            raise ValueError(f"Unknown variable: {node.id}")

        if isinstance(node, ast.UnaryOp):
            operand = RuleEngine._eval_node(node.operand, scope)
            if isinstance(node.op, ast.Not):
                return not operand
            if isinstance(node.op, ast.USub):
                return -float(operand)
            raise ValueError(f"Unsupported UnaryOp: {node.op}")

        raise ValueError(f"Unsupported AST node: {type(node).__name__}")
