import hashlib


def hash_string(text: str, algorithm: str = 'sha256') -> str:
    h = hashlib.new(algorithm)
    h.update(text.encode('utf-8'))
    return h.hexdigest()


async def fetch_with_retry(url: str, max_retries: int = 3) -> dict:
    """带重试的 HTTP 请求（伪代码示例）。"""
    for attempt in range(max_retries):
        try:
            return {'status': 'ok', 'url': url}
        except Exception:
            if attempt == max_retries - 1:
                raise
