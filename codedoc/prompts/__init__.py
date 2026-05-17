"""Prompt 模板和 tool schema 集合。

设计原则:
- 用 tool use 强制结构化输出,避免 JSON 解析
- prompt 强调"基于代码逻辑推断意图",而不是改写 docstring
- confidence 字段让低信心输出可被下游标记
"""

# ---------- Function 解释:tool schema ----------
# Anthropic tool use 会强制 Claude 按这个 schema 填字段。
# description 字段会被 Claude 用来理解每个 field 该填什么,要写清楚。

FUNCTION_TOOL_SCHEMA = {
    "name": "document_function",
    "description": "为一个 Python 函数生成基于代码逻辑的结构化文档。",
    "input_schema": {
        "type": "object",
        "properties": {
            "purpose": {
                "type": "string",
                "description": "一句话说明这个函数做什么。中文,30 字以内,以动词开头,不要废话。"
            },
            "behavior": {
                "type": "string",
                "description": "2-3 句话详细说明函数的执行流程和关键逻辑。中文。聚焦'怎么做'和'为什么',不要重复 purpose。"
            },
            "design_rationale": {
                "type": "string",
                "description": "推断作者为什么这样写——选择这种实现方式的可能原因。比如:为什么用递归而不是循环、为什么先校验输入、为什么这样处理边界。中文,1-2 句。如果代码逻辑明显没有特殊设计,填'常规实现,无特殊设计'。"
            },
            "params": {
                "type": "array",
                "description": "参数说明列表。即使函数没有参数也要返回空数组 []。",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "参数名"},
                        "type": {"type": "string", "description": "从代码或类型注解推断的类型,如 int / str / Optional[Dict] 等。无法推断填 'unknown'。"},
                        "description": {"type": "string", "description": "参数含义,中文,简短"}
                    },
                    "required": ["name", "type", "description"]
                }
            },
            "returns": {
                "type": "string",
                "description": "返回值说明,中文。无返回值或返回 None 填'无返回值'。"
            },
            "raises": {
                "type": "array",
                "description": "代码中实际可能抛出的异常类型(显式 raise 或调用栈中明确会抛的)。不要凭空猜测可能抛但代码里没写的。空数组表示无显式异常。",
                "items": {"type": "string"}
            },
            "notes": {
                "type": "string",
                "description": "需要注意的事项:边界条件、潜在 bug、与已有 docstring 不一致的地方、性能陷阱等。中文。如果代码完全符合预期且 docstring 一致,填'无'。"
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "对上述推断的信心。high=代码逻辑清晰,完全可推断;medium=部分依赖命名/docstring;low=代码意图不明,推断主要靠猜测。"
            },
            "confidence_reason": {
                "type": "string",
                "description": "信心评级的简短理由。中文,一句话。high 时填'代码逻辑清晰';低信心时说明哪里不清楚。"
            }
        },
        "required": [
            "purpose", "behavior", "design_rationale",
            "params", "returns", "raises", "notes",
            "confidence", "confidence_reason"
        ]
    }
}


# ---------- Function 解释:user prompt 模板 ----------
# 注意:tool schema 已经规定了输出结构,这里 prompt 只需要"喂数据"+"原则"。
# 不要在 prompt 里再重复"输出 JSON 字段..."——那是 schema 的工作,重复反而会让 Claude 困惑。

FUNCTION_EXPLAIN_PROMPT = """你是一名资深 Python 工程师。你的任务是为下面这个函数生成结构化的解释性文档。

# 输入函数

- 函数名: {name}
- 参数: {args}
- 所在文件: {file_path}
- 是否异步: {is_async}

已有 docstring(可能为空,可能与代码不一致——以代码为准,如有冲突在 notes 中指出):

{docstring}

源码:

{source}

# 工作原则

1. **基于代码实际逻辑推断**,不要照搬 docstring,不要瞎编代码里没有的功能。
2. **聚焦"为什么这样写"**,这比"做什么"更有价值——读代码就能看出做什么,但意图需要推断。
3. **如果代码逻辑不明确**,在 notes 中说明,并在 confidence 中标 low。
4. **类型推断从代码看**:类型注解、isinstance 检查、参数使用方式都是线索。
5. 必须调用 `document_function` 工具返回结果。"""