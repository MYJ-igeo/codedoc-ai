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

if __name__ == '__main__':
    cli()