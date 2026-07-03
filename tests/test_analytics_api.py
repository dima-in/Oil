import ast
from pathlib import Path
import importlib.util


def _call_name(node):
    # Resolves a dotted call target, e.g. `op.create_index(...)` -> "op.create_index".
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _calls(tree, dotted_name):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n.func) == dotted_name]


def _func(tree, name):
    return next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name), None)


def _str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _str_list(node):
    if isinstance(node, (ast.List, ast.Tuple)):
        return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def _module_assign(tree, name):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value.value if isinstance(node.value, ast.Constant) else None
    return None


def _create_table(scope, table_name):
    for c in _calls(scope, "op.create_table"):
        if c.args and _str(c.args[0]) == table_name:
            return c
    return None


def _columns(create_table_call):
    # Each entry: {"name", "type", "primary_key", "nullable"}. Use this instead of
    # hand-rolling sa.Column / primary_key / nullable detection (which is easy to get wrong).
    cols = []
    for arg in (create_table_call.args[1:] if create_table_call else []):
        if not (isinstance(arg, ast.Call) and _call_name(arg.func) == "sa.Column" and arg.args):
            continue
        name = _str(arg.args[0])
        if name is None:
            continue
        ctype = ""
        if len(arg.args) > 1 and _call_name(arg.args[1]):
            ctype = _call_name(arg.args[1]).split(".")[-1]
        kw = {k.arg: (k.value.value if isinstance(k.value, ast.Constant) else None) for k in arg.keywords}
        cols.append({"name": name, "type": ctype, "primary_key": kw.get("primary_key") is True, "nullable": kw.get("nullable")})
    return cols


def _class(tree, name):
    return next((n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == name), None)


def _method(cls, name):
    # Returns the FunctionDef or AsyncFunctionDef for a method, or None.
    if cls is None:
        return None
    return next(
        (n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name),
        None,
    )


def _arg_names(func):
    return [a.arg for a in func.args.args] if func else []


MAIN_PATH = Path(__file__).resolve().parent.parent / "main.py"


def test_analytics_assistant_endpoint_exists():
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
    func = _func(tree, "analytics_assistant")
    assert func is not None
    assert _arg_names(func) == ["question", "username"]

    decorators = [d for d in func.decorator_list if isinstance(d, ast.Call) and _call_name(d.func) == "app.post"]
    assert len(decorators) == 1
    assert decorators[0].args
    assert _str(decorators[0].args[0]) == "/analytics/assistant"


def test_analytics_assistant_requires_auth():
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
    func = _func(tree, "analytics_assistant")
    assert func is not None

    defaults = list(func.args.defaults)
    assert len(defaults) == 1
    default = defaults[0]
    assert isinstance(default, ast.Call)
    assert _call_name(default.func) == "Depends"
    assert len(default.args) == 1
    assert _call_name(default.args[0]) == "get_current_username"

    username_arg = func.args.args[1]
    assert username_arg.arg == "username"
    assert isinstance(username_arg.annotation, ast.Name)
    assert username_arg.annotation.id == "str"


def test_analytics_assistant_returns_answer():
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
    func = _func(tree, "analytics_assistant")
    assert func is not None

    question_arg = func.args.args[0]
    assert question_arg.arg == "question"
    assert isinstance(question_arg.annotation, ast.Name)
    assert question_arg.annotation.id == "str"

    env_reads = [
        node for node in ast.walk(func)
        if isinstance(node, ast.Call)
        and _call_name(node.func) == "os.getenv"
        and node.args
        and _str(node.args[0]) == "OPENROUTER_API_KEY"
    ]
    assert env_reads

    answer_keys = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                value = _str(key)
                if value is not None:
                    answer_keys.add(value)
    assert "answer" in answer_keys


def test_get_customer_analytics_no_dates():
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
    func = _func(tree, "get_customer_analytics")
    assert func is not None
    assert _arg_names(func) == ["start_date", "end_date"]


def test_get_customer_analytics_with_dates():
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
    func = _func(tree, "get_customer_analytics")
    assert func is not None
    assert len(func.args.defaults) == 2
    assert all(isinstance(default, ast.Constant) and default.value is None for default in func.args.defaults)


def test_get_product_analytics_no_dates():
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
    func = _func(tree, "get_product_analytics")
    assert func is not None
    assert _arg_names(func) == ["start_date", "end_date"]


def test_get_product_analytics_with_dates():
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
    func = _func(tree, "get_product_analytics")
    assert func is not None
    assert len(func.args.defaults) == 2
    assert all(isinstance(default, ast.Constant) and default.value is None for default in func.args.defaults)


def test_get_summary_analytics_no_dates():
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
    func = _func(tree, "get_summary_analytics")
    assert func is not None
    assert _arg_names(func) == ["start_date", "end_date"]


def test_get_summary_analytics_with_dates():
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
    func = _func(tree, "get_summary_analytics")
    assert func is not None
    assert len(func.args.defaults) == 2
    assert all(isinstance(default, ast.Constant) and default.value is None for default in func.args.defaults)
