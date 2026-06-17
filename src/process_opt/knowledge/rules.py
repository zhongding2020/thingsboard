from process_opt.knowledge.base import ProcessTemplate, Rule, RuleType


class RuleCheck:
    def __init__(self, rule: Rule) -> None:
        self.rule = rule
        self.triggered = False
        self.violation = ""


class RuleEngine:
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
        safe = {}
        for k, v in params.items():
            key = k.replace("-", "_").replace(" ", "_")
            safe[key] = v
        try:
            return bool(eval(expression, {"__builtins__": {}}, safe))
        except Exception:
            return False
