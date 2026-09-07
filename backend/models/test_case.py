"""测试步骤声明式定义"""
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Any
from enum import Enum


class StepResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class TestStep:
    """单个测试步骤定义"""
    name: str                          # 内部名称，如 "chip_check"
    label: str                         # 显示名称，如 "芯片类型检查"
    execute: Callable                  # 执行函数，签名: (context: dict) -> bool
    timeout: int = 30                  # 超时时间（秒）
    required: bool = True              # 是否必须通过
    depends_on: List[str] = field(default_factory=list)  # 依赖的前置步骤
    skip_if_failed: bool = False       # 前置步骤失败时是否跳过

    def __call__(self, context: dict) -> bool:
        return self.execute(context)


@dataclass
class TestCaseConfig:
    """测试用例配置"""
    test_type: str
    product_model: str
    steps: List[TestStep]
    product_info: dict = field(default_factory=dict)
