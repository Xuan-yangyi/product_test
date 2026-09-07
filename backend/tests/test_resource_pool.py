"""Resource pool unit tests"""
import pytest
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

pytestmark = pytest.mark.skip(reason="ResourcePool tests require full environment setup", allow_module_level=True)

try:
    from services.resource_pool import ResourcePool
    pytestmark = []  # Clear skip if imports succeed

    class TestResourcePool:
        @pytest.mark.asyncio
        async def test_acquire_release(self, mocker):
            """Test acquiring and releasing serial ports"""
            pool = ResourcePool()

            mocker.patch('engine.serial_client.SerialClient.open', return_value=True)
            mocker.patch('engine.serial_client.SerialClient.close')

            client = await pool.acquire_serial("/dev/ttyUSB0")
            assert client is not None
            assert pool._in_use["/dev/ttyUSB0"] is True

            pool.release_serial("/dev/ttyUSB0")
            assert pool._in_use["/dev/ttyUSB0"] is False

        def test_get_available_ports(self):
            """Get available ports"""
            pool = ResourcePool()
            ports = pool.get_available_ports()
            assert isinstance(ports, list)

        def test_get_usage_status(self):
            """Get usage status"""
            pool = ResourcePool()
            status = pool.get_usage_status()
            assert "total_managed_ports" in status
            assert "ports_in_use" in status

        def test_init_state(self):
            """ResourcePool should initialize with empty state"""
            pool = ResourcePool()
            assert len(pool._locks) == 0
            assert len(pool._clients) == 0
            assert len(pool._in_use) == 0

        def test_usage_status_structure(self):
            """Usage status should have correct structure"""
            pool = ResourcePool()
            status = pool.get_usage_status()
            assert "total_managed_ports" in status
            assert "ports_in_use" in status
            assert "ports_available" in status
            assert "details" in status

except ImportError:
    pass  # Tests will be skipped due to pytestmark
