"""测试脚本执行器

读取 script_cmd_cfg.ini 配置，通过串口或 SSH 执行测试脚本命令，
并解析输出中的 PASS/FAIL 标志。
"""
import configparser
import logging
import re
from pathlib import Path
from typing import Optional, Dict
from ..config import Config

logger = logging.getLogger(__name__)

# 测试类型 → 脚本子目录映射
TEST_TYPE_TO_CFG_SUBDIR = {
    "se9_interface_test": "SE9_cfg",
    "se9_aging_test": "SE9_cfg",
    "se9_mac_check": "SE9_cfg",
    "evb_interface_test": "EVB_cfg",
    "evb_aging_test": "EVB_cfg",
}
# case_name (test_case_config.ini key) → section_name (script_cmd_cfg.ini [section])
# 旧 PyQt5 代码在 _run() 中手动映射，Web 端需要此表统一转换
CASE_TO_SECTION = {
    "audio_check": "AUDIO",
    "usb_check": "USB",
    "eth_check": "ETH",
    "4g_check": "4G",
    "5g_check": "5G",
    "wifi_check": "WIFI",
    "bluetooth_check": "BLUETOOTH",
    "emmc_check": "EMMC",
    "drive_check": "DRIVE",
    "phoenix_check": "PHOENIX",
    "burn_board_sn": "SN",
    "burn_device_sn": "SN",
    "burn_mac": "MAC",
    "burn_oem": "OEM",
    "set_interface_flag": "INTERFACE_FLAG",
    "rs232_check": "RS232",
    "rs485_check": "RS485",
    "io_check": "IO",
}



class ScriptRunner:
    """测试脚本执行器

    读取 cfg/<subdir>/script_cmd_cfg.ini 中的测试脚本命令配置，
    通过串口或 SSH 执行命令，并检查输出中的 PASS/FAIL 标志。

    script_cmd_cfg.ini 格式：
    [test_case_name]
    exec_cmd = ./test_xxx.sh
    pass_flag = QA_PASS_XXX
    fail_flag = QA_FAIL_XXX
    case_timeout = 120
    """

    def __init__(self, test_type: str = None):
        self._test_type = test_type
        self._config = self._load_config(test_type)

    def _load_config(self, test_type: str = None) -> configparser.ConfigParser:
        """加载脚本命令配置

        根据测试类型从对应的子目录读取 script_cmd_cfg.ini。
        SE9 → SE9_cfg/, EVB → EVB_cfg/
        """
        if test_type:
            subdir = TEST_TYPE_TO_CFG_SUBDIR.get(test_type, "SE9_cfg")
            cfg_path = Config.CFG_DIR / subdir / "script_cmd_cfg.ini"
        else:
            cfg_path = Config.CFG_DIR / "script_cmd_cfg.ini"

        parser = configparser.ConfigParser()
        parser.optionxform = str  # 保留原始大小写
        if cfg_path.exists():
            parser.read(str(cfg_path), encoding="utf-8")
        else:
            logger.warning("Script cmd config not found: %s", cfg_path)
        return parser

    def get_test_cases(self) -> Dict[str, dict]:
        """获取所有测试用例配置

        Returns:
            {case_name: {cmd, pass_flag, fail_flag, timeout, sudo, sudo_password}}
        """
        cases = {}
        for section in self._config.sections():
            cases[section] = {
                "cmd": self._config.get(section, "exec_cmd", fallback="").strip('"'),
                "pass_flag": self._config.get(section, "pass_flag", fallback="PASS"),
                "fail_flag": self._config.get(section, "fail_flag", fallback="FAIL"),
                "timeout": self._config.getint(section, "case_timeout", fallback=30),
                "sudo": self._config.getboolean(section, "sudo", fallback=False),
                "sudo_password": self._config.get(section, "sudo_password", fallback=""),
            }
        return cases

    def run_serial(self, serial_client, case_name: str, timeout: int = None) -> dict:
        """通过串口执行测试用例

        Args:
            serial_client: SerialClient 实例
            case_name: 测试用例名称（script_cmd_cfg.ini 中的 section）
            timeout: 超时时间，默认从配置读取

        Returns:
            {result: "pass"/"fail", output: str, duration: float}
        """
        import time

        section_name = CASE_TO_SECTION.get(case_name, case_name)
        case = self.get_test_cases().get(section_name)
        if not case:
            return {"result": "fail", "output": f"未找到测试用例: {case_name} (section={section_name})", "duration": 0}

        cmd = case["cmd"]
        if cmd.startswith("./"):
            cmd = f"cd /data/SE9_test_files && {cmd}"
        timeout = timeout or case["timeout"]
        pass_flag = case["pass_flag"]
        fail_flag = case["fail_flag"]

        logger.info(f"执行测试用例 [{case_name}]: {cmd}")
        start = time.time()

        try:
            output = serial_client.send_cmd(cmd, timeout=timeout)
        except Exception as e:
            return {"result": "fail", "output": str(e), "duration": time.time() - start}

        duration = time.time() - start

        if pass_flag in output:
            result = "pass"
        elif fail_flag in output:
            result = "fail"
        else:
            result = "fail"  # 超时或无标志，默认失败

        logger.info(f"测试用例 [{case_name}] 结果: {result}, 耗时: {duration:.1f}s")
        return {"result": result, "output": output, "duration": duration}

    def run_ssh(self, ssh_client, case_name: str, timeout: int = None) -> dict:
        """通过 SSH 执行测试用例

        Args:
            ssh_client: SSHClient 实例
            case_name: 测试用例名称
            timeout: 超时时间

        Returns:
            {result: "pass"/"fail", output: str, duration: float}
        """
        import time

        section_name = CASE_TO_SECTION.get(case_name, case_name)
        case = self.get_test_cases().get(section_name)
        if not case:
            return {"result": "fail", "output": f"未找到测试用例: {case_name} (section={section_name})", "duration": 0}

        cmd = case["cmd"]
        if cmd.startswith("./"):
            cmd = f"cd /data/SE9_test_files && {cmd}"
        timeout = timeout or case["timeout"]
        pass_flag = case["pass_flag"]
        fail_flag = case["fail_flag"]
        use_sudo = case.get("sudo", False)
        sudo_password = case.get("sudo_password", "")

        logger.info(f"SSH 执行测试用例 [{case_name}]: {cmd} (sudo={use_sudo})")
        start = time.time()

        try:
            stdout, stderr, exit_code = ssh_client.exec_cmd(
                cmd, timeout=timeout, sudo=use_sudo, sudo_password=sudo_password
            )
            output = stdout + "\n" + stderr
        except Exception as e:
            return {"result": "fail", "output": str(e), "duration": time.time() - start}

        duration = time.time() - start

        if pass_flag in output:
            result = "pass"
        elif fail_flag in output:
            result = "fail"
        else:
            result = "fail"

        return {"result": result, "output": output, "duration": duration}
