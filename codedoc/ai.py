"""Claude API 客户端封装。

提供:
- get_client(): 单例 Anthropic 客户端
- call_claude_tool(): 用 tool use 调用 Claude,强制结构化输出
- get_usage_stats() / reset_usage_stats(): token 用量统计
- estimate_cost(): 根据 token 估算成本
"""

import os
from typing import Optional
from anthropic import Anthropic
import httpx
from dotenv import load_dotenv

load_dotenv()

# ---------- 客户端单例 ----------
_client: Optional[Anthropic] = None

def get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise RuntimeError("缺少 ANTHROPIC_API_KEY,请检查 .env 文件")

        # 可选代理:从环境变量读,没有就直连
        proxy_url = os.getenv('CODEDOC_PROXY')
        if proxy_url:
            http_client = httpx.Client(proxy=proxy_url, timeout=60.0)
            _client = Anthropic(api_key=api_key, http_client=http_client)
        else:
            _client = Anthropic(api_key=api_key)
    return _client


# ---------- Token 用量统计 ----------
_usage_stats = {
    'calls': 0,
    'input_tokens': 0,
    'output_tokens': 0,
    'failed_calls': 0,
}

# 价格表 ($ per 1M tokens),更新于 2026-05
# 来源: https://www.anthropic.com/pricing
_PRICING = {
    'claude-haiku-4-5-20251001': {'input': 1.0, 'output': 5.0},
    'claude-sonnet-4-6': {'input': 3.0, 'output': 15.0},
    'claude-opus-4-7': {'input': 15.0, 'output': 75.0},
}

def get_usage_stats() -> dict:
    """返回累计用量(含估算成本)。"""
    return dict(_usage_stats)

def reset_usage_stats() -> None:
    """重置统计(测试用)。"""
    for k in _usage_stats:
        _usage_stats[k] = 0

def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """按模型估算单次调用成本(美元)。"""
    price = _PRICING.get(model)
    if not price:
        return 0.0
    return (input_tokens * price['input'] + output_tokens * price['output']) / 1_000_000


# ---------- 核心调用 ----------
def call_claude_tool(
    prompt: str,
    tool_schema: dict,
    system: Optional[str] = None,
    model: str = 'claude-haiku-4-5-20251001',
    max_tokens: int = 2000,
) -> dict:
    """用 tool use 调用 Claude,强制结构化输出。

    参数:
        prompt: 用户消息内容
        tool_schema: 工具定义,形如
            {"name": "...", "description": "...", "input_schema": {...}}
        system: 可选 system prompt
        model: 模型 string
        max_tokens: 最大输出 token 数

    返回:
        {
          'success': bool,
          'data': dict,         # 成功时为 tool_use.input
          'error': str,         # 失败时填
          'usage': {            # 永远有
            'input_tokens': int,
            'output_tokens': int,
            'cost_usd': float,
            'model': str,
          }
        }
    """
    client = get_client()
    _usage_stats['calls'] += 1

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system or "You are a senior Python engineer who writes clear, accurate code documentation.",
            tools=[tool_schema],
            tool_choice={"type": "tool", "name": tool_schema['name']},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        _usage_stats['failed_calls'] += 1
        return {
            'success': False,
            'error': f'API 调用失败: {e}',
            'usage': {'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0.0, 'model': model},
        }

    # 统计 token
    in_tok = response.usage.input_tokens
    out_tok = response.usage.output_tokens
    cost = estimate_cost(model, in_tok, out_tok)
    _usage_stats['input_tokens'] += in_tok
    _usage_stats['output_tokens'] += out_tok

    usage_info = {
        'input_tokens': in_tok,
        'output_tokens': out_tok,
        'cost_usd': cost,
        'model': model,
    }

    # 提取 tool_use block
    for block in response.content:
        if block.type == 'tool_use':
            return {
                'success': True,
                'data': block.input,
                'usage': usage_info,
            }

    # 强制 tool_choice 后理论上不会到这里,但留个兜底
    _usage_stats['failed_calls'] += 1
    return {
        'success': False,
        'error': '模型没有调用工具',
        'raw_content': str(response.content),
        'usage': usage_info,
    }