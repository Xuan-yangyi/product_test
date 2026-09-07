from .test_type import router as test_type_router
from .device import router as device_router
from .test_execution import router as test_execution_router
from .ws import router as ws_router

__all__ = ["test_type_router", "device_router", "test_execution_router", "ws_router"]
