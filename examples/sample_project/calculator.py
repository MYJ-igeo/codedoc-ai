"""一个简单的计算器模块。"""


class Calculator:
    """支持基础四则运算的计算器。"""
    
    def __init__(self):
        self.history = []
    
    def add(self, a: float, b: float) -> float:
        result = a + b
        self.history.append(('add', a, b, result))
        return result
    
    def divide(self, a: float, b: float) -> float:
        if b == 0:
            raise ValueError("除数不能为零")
        return a / b


def factorial(n: int) -> int:
    if n < 0:
        raise ValueError("负数没有阶乘")
    if n <= 1:
        return 1
    return n * factorial(n - 1)
