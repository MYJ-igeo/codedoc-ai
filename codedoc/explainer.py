"""调用 Claude 解释代码的主流程。

负责把 parser 解析出的结构化数据 + AI 调用串起来,
为每个函数/类/模块附加 `ai_explain` 或 `ai_overview` 字段。
"""
from typing import Callable, Optional

from codedoc.ai import call_claude_tool
from codedoc.prompts import (
    FUNCTION_EXPLAIN_PROMPT,
    FUNCTION_TOOL_SCHEMA,
    CLASS_EXPLAIN_PROMPT,
    CLASS_TOOL_SCHEMA,
    MODULE_EXPLAIN_PROMPT,
    MODULE_TOOL_SCHEMA,
)


def explain_function(func: dict, file_path: str) -> dict:
    """解释单个函数。

    Args:
        func: parser.parse_function 的输出
        file_path: 函数所在文件路径(用于 prompt 上下文)

    Returns:
        call_claude_tool 的标准返回(含 success / data / usage)
    """
    prompt = FUNCTION_EXPLAIN_PROMPT.format(
        name=func['name'],
        args=', '.join(func['args']) or '(无参数)',
        file_path=file_path,
        is_async=func.get('is_async', False),
        docstring=func.get('docstring') or '(无)',
        source=func['source'],
    )
    return call_claude_tool(prompt, FUNCTION_TOOL_SCHEMA)


def explain_class(cls: dict, file_path: str) -> dict:
    """解释单个类。"""
    methods_summary = '\n'.join([
        f"- {m['name']}({', '.join(m['args'])})"
        for m in cls['methods']
    ]) or '(无方法)'

    prompt = CLASS_EXPLAIN_PROMPT.format(
        name=cls['name'],
        bases=', '.join(cls['bases']) or '(无父类)',
        file_path=file_path,
        methods_summary=methods_summary,
        docstring=cls.get('docstring') or '(无)',
        source=cls['source'],
    )
    return call_claude_tool(prompt, CLASS_TOOL_SCHEMA)


def explain_module(file_info: dict) -> dict:
    """解释整个模块(文件)。"""
    classes_list = '\n'.join([
        f"- class {c['name']}" for c in file_info['classes']
    ]) or '(无)'
    functions_list = '\n'.join([
        f"- def {f['name']}({', '.join(f['args'])})"
        for f in file_info['functions']
    ]) or '(无)'

    prompt = MODULE_EXPLAIN_PROMPT.format(
        file_path=file_info['file_path'],
        module_docstring=file_info.get('module_docstring') or '(无)',
        classes_list=classes_list,
        functions_list=functions_list,
    )
    return call_claude_tool(prompt, MODULE_TOOL_SCHEMA)


def explain_file(
    file_info: dict,
    on_progress: Optional[Callable[[str], None]] = None,
) -> dict:
    """对一个文件的所有内容生成 AI 解释。

    会原地修改 file_info,加上以下字段:
    - file_info['ai_overview']                              模块总览
    - file_info['classes'][i]['ai_explain']                 每个类
    - file_info['classes'][i]['methods'][j]['ai_explain']   每个方法
    - file_info['functions'][i]['ai_explain']               每个独立函数
    - file_info['_token_usage']                             token 用量统计

    Args:
        file_info: parser.parse_file 的输出
        on_progress: 可选的进度回调,接收一个字符串描述

    Returns:
        修改后的 file_info(同一个对象)
    """
    file_path = file_info['file_path']
    total = {'input': 0, 'output': 0, 'cost': 0.0, 'failed': 0}

    def _accumulate(result):
        total['input'] += result['usage']['input_tokens']
        total['output'] += result['usage']['output_tokens']
        total['cost'] += result['usage']['cost_usd']
        if not result['success']:
            total['failed'] += 1

    # 1. 模块总览
    if on_progress:
        on_progress(f"📄 {file_path} - 模块总览")
    module_result = explain_module(file_info)
    if module_result['success']:
        file_info['ai_overview'] = module_result['data']
    _accumulate(module_result)

    # 2. 每个类(及其方法)
    for cls in file_info['classes']:
        if on_progress:
            on_progress(f"   类 {cls['name']}")
        cls_result = explain_class(cls, file_path)
        if cls_result['success']:
            cls['ai_explain'] = cls_result['data']
        _accumulate(cls_result)

        for method in cls['methods']:
            if on_progress:
                on_progress(f"      方法 {cls['name']}.{method['name']}")
            m_result = explain_function(method, file_path)
            if m_result['success']:
                method['ai_explain'] = m_result['data']
            _accumulate(m_result)

    # 3. 每个独立函数
    for func in file_info['functions']:
        if on_progress:
            on_progress(f"   函数 {func['name']}")
        f_result = explain_function(func, file_path)
        if f_result['success']:
            func['ai_explain'] = f_result['data']
        _accumulate(f_result)

    file_info['_token_usage'] = total
    return file_info
