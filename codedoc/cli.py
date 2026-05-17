import click
from rich.console import Console
from pathlib import Path
from codedoc.parser  import scan_directory

console = Console()

@click.group()
def cli():
    """CodeDoc AI - 用 LLM 为 Python 代码生成解释性文档"""
    pass

@cli.command()
@click.argument('path', type=click.Path(exists=True, file_okay=False, path_type=Path))
def scan(path: Path):
    """扫描目录下所有 .py 文件，列出函数和类（不调用 AI）"""
    console.print(f"[bold cyan]正在扫描目录:[/] {path}")
    
    # 调用 parser.py 中的扫描函数
    results = scan_directory(path)
    
    if not results:
        console.print("[yellow]未找到包含函数或类的 Python 文件。[/]")
        return

    # 漂亮地打印出扫描结果
    for file_info in results:
        console.print(f"\n[bold green]📄 {file_info['file_path']}[/]")
        
        # 打印类和类里面的方法
        for cls in file_info['classes']:
            console.print(f"  [yellow]class[/] [bold]{cls['name']}[/] (第 {cls['line']} 行)")
            for method in cls['methods']:
                console.print(f"    [magenta]def[/] {method['name']}({', '.join(method['args'])})")
                
        # 打印独立函数
        for func in file_info['functions']:
            console.print(f"  [magenta]def[/] [bold]{func['name']}[/]({', '.join(func['args'])}) (第 {func['line']} 行)")


# ============================================================
# Day 2: explain 命令 - 用 Claude 解释单个函数
# ============================================================

from codedoc.ai import call_claude_tool, get_usage_stats
from codedoc.prompts import FUNCTION_TOOL_SCHEMA, FUNCTION_EXPLAIN_PROMPT


def _find_function(parsed: dict, function_name: str) -> dict | None:
    """在 parser 输出里查找指定函数(顶层函数 + 类方法都查)。"""
    for func in parsed.get('functions', []):
        if func['name'] == function_name:
            return func
    for cls in parsed.get('classes', []):
        for method in cls.get('methods', []):
            if method['name'] == function_name:
                return method
    return None


@cli.command()
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--function', '-f', required=True, help='要解释的函数名')
@click.option('--model', default='claude-haiku-4-5-20251001',
              help='模型 string(默认 Haiku 4.5)')
def explain(file_path: Path, function: str, model: str):
    """[Day 2] 用 Claude 解释单个函数。"""
    from codedoc.parser import parse_file

    # 1. 解析文件
    parsed = parse_file(file_path)
    if not parsed:
        console.print("[red]文件解析失败[/]")
        return

    # 2. 找目标函数
    target = _find_function(parsed, function)
    if not target:
        console.print(f"[red]找不到函数 {function}[/]")
        return

    console.print(f"[cyan]正在用 {model} 解释 [bold]{function}[/]...[/]")

    # 3. 构造 prompt
    prompt = FUNCTION_EXPLAIN_PROMPT.format(
        name=target['name'],
        args=', '.join(target.get('args', [])) or '(无参数)',
        file_path=str(file_path),
        is_async=target.get('is_async', False),
        docstring=target.get('docstring') or '(无 docstring)',
        source=target['source'],
    )

    # 4. 调 Claude
    result = call_claude_tool(
        prompt=prompt,
        tool_schema=FUNCTION_TOOL_SCHEMA,
        model=model,
    )

    # 5. 输出
    if not result['success']:
        console.print(f"[red]失败: {result.get('error')}[/]")
        return

    data = result['data']
    usage = result['usage']

    # 用 Rich 格式化输出
    confidence_color = {
        'high': 'green',
        'medium': 'yellow',
        'low': 'red',
    }.get(data.get('confidence', 'low'), 'red')

    console.print()
    console.print(f"[bold cyan]Purpose:[/] {data.get('purpose', '')}")
    console.print(f"[bold cyan]Behavior:[/] {data.get('behavior', '')}")
    console.print(f"[bold cyan]Design rationale:[/] {data.get('design_rationale', '')}")

    console.print(f"\n[bold cyan]Params:[/]")
    for p in data.get('params', []) or [{'name': '(无)', 'type': '', 'description': ''}]:
        console.print(f"  • [bold]{p.get('name')}[/] ({p.get('type')}): {p.get('description')}")

    console.print(f"\n[bold cyan]Returns:[/] {data.get('returns', '')}")
    console.print(f"[bold cyan]Raises:[/] {', '.join(data.get('raises', [])) or '(无)'}")
    console.print(f"[bold cyan]Notes:[/] {data.get('notes', '')}")
    console.print(f"\n[bold {confidence_color}]Confidence:[/] {data.get('confidence')} - {data.get('confidence_reason', '')}")

    console.print(
        f"\n[dim]Token: in={usage['input_tokens']}, out={usage['output_tokens']}, "
        f"cost=${usage['cost_usd']:.6f}, model={usage['model']}[/]"
    )

if __name__ == '__main__':
    cli()