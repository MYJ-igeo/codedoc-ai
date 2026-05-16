import ast
from pathlib import Path
from typing import Optional


def parse_function(node: ast.FunctionDef, source_lines: list[str]) -> dict:
    """从 AST 函数节点提取信息"""
    return {
        'name': node.name,
        'line': node.lineno,
        # 提取所有参数名
        'args': [arg.arg for arg in node.args.args],
        # 提取原有的 docstring（如果有）
        'docstring': ast.get_docstring(node) or '',
        # 根据行号，准确切出这个函数的源代码
        'source': '\n'.join(source_lines[node.lineno - 1:node.end_lineno]),
        'is_async': isinstance(node, ast.AsyncFunctionDef),
    }


def parse_class(node: ast.ClassDef, source_lines: list[str]) -> dict:
    """从 AST 类节点提取信息"""
    methods = []
    # 遍历类里面的每一行，找出函数（也就是方法）
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(parse_function(item, source_lines))

    return {
        'name': node.name,
        'line': node.lineno,
        'docstring': ast.get_docstring(node) or '',
        # 提取继承的父类
        'bases': [ast.unparse(base) for base in node.bases],
        'methods': methods,
        'source': '\n'.join(source_lines[node.lineno - 1:node.end_lineno]),
    }


def parse_file(file_path: Path) -> Optional[dict]:
    """解析单个 .py 文件"""
    try:
        source = file_path.read_text(encoding='utf-8')
        source_lines = source.split('\n')
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"⚠️ 解析跳过 {file_path}: {e}")
        return None

    functions = []
    classes = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(parse_function(node, source_lines))
        elif isinstance(node, ast.ClassDef):
            classes.append(parse_class(node, source_lines))

    return {
        'file_path': str(file_path),
        'module_docstring': ast.get_docstring(tree) or '',
        'functions': functions,
        'classes': classes,
    }


def scan_directory(root: Path, exclude_patterns: list[str] = None) -> list[dict]:
    """递归扫描目录，找出所有 .py 文件并解析"""
    if exclude_patterns is None:
        # 默认跳过这些无关文件夹
        exclude_patterns = ['__pycache__', 'venv', '.venv', 'site-packages', 'tests']

    results = []
    for py_file in root.rglob('*.py'):
        if any(part in exclude_patterns for part in py_file.parts):
            continue

        result = parse_file(py_file)
        # 只有当文件里真的有类或函数时，才加入结果
        if result and (result['functions'] or result['classes']):
            results.append(result)

    return results