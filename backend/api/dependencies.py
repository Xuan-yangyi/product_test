"""共享依赖注入

提供全局单例，确保所有 API 模块使用同一个 TestManager 实例。
"""
from ..services.test_manager import TestManager
from ..services.resource_pool import ResourcePool
from ..services.config_service import ConfigService
from ..services.result_service import ResultService

_test_manager: TestManager = None


def get_test_manager() -> TestManager:
    """获取全局唯一的 TestManager 实例"""
    global _test_manager
    if _test_manager is None:
        resource_pool = ResourcePool()
        config_service = ConfigService()
        result_service = ResultService()
        _test_manager = TestManager(resource_pool, config_service, result_service)
    return _test_manager