"""Serial client unit tests"""
import pytest
from engine.serial_client import SerialClient


class TestSerialClient:
    def test_scan_ports(self):
        """scan_ports() should return a list"""
        ports = SerialClient.scan_ports()
        assert isinstance(ports, list)

    def test_init_state(self):
        """After init, is_open should be False"""
        client = SerialClient("/dev/ttyUSB0")
        assert client.is_open is False
        assert client.port == "/dev/ttyUSB0"

    def test_send_cmd_without_open_raises(self):
        """Sending cmd without opening should raise RuntimeError"""
        client = SerialClient("/dev/ttyUSB0")
        with pytest.raises(RuntimeError, match="未打开"):
            client.send_cmd("test")

    def test_baudrate_default(self):
        """Default baudrate should be 115200"""
        client = SerialClient("/dev/ttyUSB0")
        assert client.baudrate == 115200

    def test_timeout_default(self):
        """Default timeout should be 3.0"""
        client = SerialClient("/dev/ttyUSB0")
        assert client.timeout == 3.0

    def test_custom_baudrate(self):
        """Should accept custom baudrate"""
        client = SerialClient("/dev/ttyUSB0", baudrate=9600)
        assert client.baudrate == 9600
