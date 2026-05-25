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
CLASS_TOOL_SCHEMA = {
    "name": "document_class",
    "description": "为一个 Python 类生成基于代码逻辑的结构化文档。",
    "input_schema": {
        "type": "object",
        "properties": {
            "purpose": {
                "type": "string",
                "description": "一句话说明这个类的核心职责。中文,30 字以内,以名词或动名词开头。"
            },
            "responsibility": {
                "type": "string",
                "description": "2-3 句话详细说明这个类负责什么。中文。从所有方法的功能交集中归纳,不要简单堆砌方法列表。"
            },
            "design_rationale": {
                "type": "string",
                "description": "推断作者为什么这样设计这个类——为什么这样划分职责、为什么继承这个父类、为什么这样组织方法。中文,1-2 句。如无特殊设计填'常规设计,无特殊考虑'。"
            },
            "key_methods": {
                "type": "array",
                "description": "类的关键方法(必须理解的入口),最多 5 个。即使没有也要返回空数组 []。",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "方法名"},
                        "role": {"type": "string", "description": "该方法在类中扮演的角色,中文,20 字以内。如'对外入口'/'内部辅助'/'状态变更'等。"}
                    },
                    "required": ["name", "role"]
                }
            },
            "usage_scenario": {
                "type": "string",
                "description": "典型使用场景。中文,1-2 句话,说明这个类通常在什么情况下被实例化和使用。"
            },
            "design_notes": {
                "type": "string",
                "description": "设计要点、注意事项、潜在改进点。中文。如无可写'无'。"
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "推断信心。high=类职责清晰可推断;medium=部分依赖命名;low=类意图不明。"
            },
            "confidence_reason": {
                "type": "string",
                "description": "信心评级的简短理由,中文,一句话。"
            }
        },
        "required": [
            "purpose", "responsibility", "design_rationale",
            "key_methods", "usage_scenario", "design_notes",
            "confidence", "confidence_reason"
        ]
    }
}


# ---------- Class 解释:user prompt 模板 ----------

CLASS_EXPLAIN_PROMPT = """你是一名资深 Python 工程师。你的任务是为下面这个类生成结构化的解释性文档。

# 输入类

- 类名: {name}
- 继承自: {bases}
- 所在文件: {file_path}

方法签名一览:

{methods_summary}

已有 docstring(可能为空):

{docstring}

完整源码:

{source}

# 工作原则

1. **基于代码实际逻辑推断类的职责**,不要照搬 docstring,不要瞎编代码里没有的功能。
2. **purpose 是类级别的概括**——从所有方法的功能交集中归纳,不要写成某个方法的描述。
3. **key_methods 选"必须理解的入口"**,而不是把所有方法都列出来。__init__、对外公开方法优先,辅助方法(下划线开头)一般不选。
4. **如果类的意图不明确**,在 design_notes 中说明,并在 confidence 中标 low。
5. 必须调用 `document_class` 工具返回结果。"""
# ---------- Module 解释:tool schema ----------

MODULE_TOOL_SCHEMA = {
    "name": "document_module",
    "description": "为一个 Python 模块(文件)生成模块级总览文档。",
    "input_schema": {
        "type": "object",
        "properties": {
            "purpose": {
                "type": "string",
                "description": "一句话说明这个模块的核心定位。中文,30 字以内。"
            },
            "overview": {
                "type": "string",
                "description": "2-3 句话总览。中文。说明模块的整体职责和组织方式。从全局视角概括,不要逐一描述每个函数(那是函数级文档的事)。"
            },
            "key_components": {
                "type": "array",
                "description": "主要组件——关键类或函数的名字。最多 5 个。挑'外部使用者最常接触的'。空数组表示无明显主要组件。",
                "items": {"type": "string"}
            },
            "typical_usage": {
                "type": "string",
                "description": "这个模块通常如何被外部使用。中文,1-2 句话。比如'通常被 X 模块 import 后调用 Y 函数'。"
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "推断信心。high=模块定位清晰;medium=部分依赖命名;low=模块意图不明。"
            },
            "confidence_reason": {
                "type": "string",
                "description": "信心评级的简短理由,中文,一句话。"
            }
        },
        "required": [
            "purpose", "overview", "key_components", "typical_usage",
            "confidence", "confidence_reason"
        ]
    }
}


# ---------- Module 解释:user prompt 模板 ----------
# 注意:模块层级不传源码(token 会爆),只传结构信息。

MODULE_EXPLAIN_PROMPT = """你是一名资深 Python 工程师。你的任务是为下面这个模块(文件)生成模块级总览文档。

# 输入模块

文件路径: {file_path}

模块顶部 docstring(可能为空):

{module_docstring}

包含的类:

{classes_list}

包含的独立函数:

{functions_list}

# 工作原则

1. **仅根据上述信息推断模块整体定位**——类名、函数名、docstring 是你仅有的线索。
2. **不要瞎编没有的功能**,如果命名很抽象、看不出来做什么,在 overview 中说明,confidence 标 low。
3. **不要逐一描述每个函数**,而是从全局视角概括"这个文件是干什么的"。
4. **key_components 挑外部最常接触的**——通常是大写命名的类、公开函数(不以下划线开头),而不是所有函数都列。
5. 必须调用 `document_module` 工具返回结果。"""
