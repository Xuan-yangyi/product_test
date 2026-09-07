"""Test configuration and fixtures"""
import pytest
import sys
import os
from pathlib import Path

# Ensure backend can be imported as a package
backend_dir = Path(__file__).resolve().parent.parent
web_dir = backend_dir.parent
sys.path.insert(0, str(web_dir))
os.chdir(str(backend_dir))


@pytest.fixture(scope="session")
def app():
    """FastAPI app fixture"""
    from backend.main import app
    return app


@pytest.fixture
def client(app):
    """HTTP test client"""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def mock_serial(mocker):
    """Mock SerialClient"""
    try:
        from backend.engine.serial_client import SerialClient
        mocker.patch.object(SerialClient, 'open', return_value=True)
        mocker.patch.object(SerialClient, 'close')
        mocker.patch.object(SerialClient, 'send_cmd', return_value="PASS: test")
        return SerialClient
    except ImportError:
        pytest.skip("SerialClient not available")


@pytest.fixture
def mock_ssh(mocker):
    """Mock SSHClient"""
    try:
        from backend.engine.ssh_client import SSHClient
        mocker.patch.object(SSHClient, 'connect', return_value=True)
        mocker.patch.object(SSHClient, 'exec_cmd', return_value=("PASS: test", "", 0))
        return SSHClient
    except ImportError:
        pytest.skip("SSHClient not available")


@pytest.fixture
def test_steps():
    """Create test steps for testing"""
    from backend.models.test_case import TestStep

    def make_step(name, should_pass=True):
        def execute(ctx):
            return should_pass
        return TestStep(
            name=name,
            label=name.replace("_", " ").title(),
            execute=execute,
            timeout=5,
            required=True,
        )

    return [make_step(f"step_{i}") for i in range(5)]