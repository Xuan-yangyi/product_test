"""配置服务

读取现有 cfg/ 目录下的配置文件，提供测试类型、测试用例、产品型号等配置信息。
解析逻辑与原有 QT 代码保持一致。
"""
import configparser
import logging
import os
import re
from pathlib import Path
from typing import List, Dict
from ..config import Config
from ..models.test_case import TestCaseConfig

logger = logging.getLogger(__name__)

# 测试类型 → test_case_config.ini section 名称映射
# ui_config.ini [test_case] 中的 key 是 snaked_lowercase，
# 但 test_case_config.ini 中的 section 是 PascalCase 混合格式
TEST_TYPE_TO_SECTION = {
    "se9_interface_test": "SE9_interface_test",
    "evb_interface_test": "EVB_interface_test",
    "se9_aging_test": "SoC_aging_test",
    "evb_aging_test": "SoC_aging_test",
}

# 测试类型 → 脚本子目录映射
TEST_TYPE_TO_CFG_SUBDIR = {
    "se9_interface_test": "SE9_cfg",
    "se9_aging_test": "SE9_cfg",
    "se9_mac_check": "SE9_cfg",
    "evb_interface_test": "EVB_cfg",
    "evb_aging_test": "EVB_cfg",
}


class ConfigService:
    """配置服务"""

    def get_test_types(self) -> list:
        """获取可用的测试类型列表

        读取 ui_config.ini 中 [test_case] 和 [other_case] 的配置项。
        与 QT 代码 get_test_items('test') 逻辑一致。
        """
        ui_cfg = self._read_ini("ui_config.ini")
        types = []

        for section in ("test_case", "other_case"):
            if section in ui_cfg:
                for key, value in ui_cfg[section].items():
                    if value.strip() == "1":
                        types.append({
                            "type": key,
                            "label": self._get_type_label(key),
                            "description": self._get_type_description(key),
                            "product": self._get_product_type(key),
                            "requires_serial": False,
                            "requires_network": True,
                        })
        return types

    def get_test_cases(self, test_type: str) -> list:
        """获取测试用例列表

        读取 test_case_config.ini 中对应测试类型的用例配置。
        处理 test_type key 与 section name 的大小写不一致。
        """
        test_cfg = self._read_ini("test_case_config.ini")
        cases = []

        # 查找匹配的 section（大小写不敏感，并处理 aging → SoC 映射）
        section_name = TEST_TYPE_TO_SECTION.get(test_type, test_type)
        matched_section = None

        for sec in test_cfg.sections():
            if sec.lower() == section_name.lower():
                matched_section = sec
                break

        if matched_section:
            for name, value in test_cfg[matched_section].items():
                cases.append({
                    "name": name,
                    "label": self._get_case_label(name),
                    "enabled": value.strip() == "1",
                })
        return cases

    def update_test_case_enabled(self, test_type: str, case_name: str, enabled: bool) -> dict:
        """更新测试用例的启用/禁用状态

        直接写入 test_case_config.ini 文件。

        Args:
            test_type: 测试类型 key，如 se9_interface_test
            case_name: 用例名称，如 4g_check
            enabled: True 启用 / False 禁用

        Returns:
            {"case_name": "...", "enabled": True/False, "test_type": "..."}

        Raises:
            ValueError: section 或 case 不存在
        """
        section_name = TEST_TYPE_TO_SECTION.get(test_type, test_type)
        cfg_path = Config.CFG_DIR / "test_case_config.ini"

        parser = configparser.ConfigParser()
        parser.optionxform = str
        if cfg_path.exists():
            parser.read(str(cfg_path), encoding="utf-8")
        else:
            raise ValueError(f"配置文件不存在: {cfg_path}")

        # 查找匹配的 section
        matched_section = None
        for sec in parser.sections():
            if sec.lower() == section_name.lower():
                matched_section = sec
                break

        if not matched_section:
            raise ValueError(f"测试类型不存在: {test_type} (section={section_name})")

        if case_name not in parser[matched_section]:
            raise ValueError(f"测试用例不存在: {case_name} (section={matched_section})")

        new_value = "1" if enabled else "0"
        parser.set(matched_section, case_name, new_value)

        with open(cfg_path, "w", encoding="utf-8") as f:
            parser.write(f)

        logger.info(f"更新测试用例: [{matched_section}] {case_name} = {new_value}")
        return {"case_name": case_name, "enabled": enabled, "test_type": test_type}

    def get_product_models(self) -> list:
        """获取产品型号列表

        从测试类型中提取产品型号（SE9, EVB）。
        与 QT 代码中 self.product = self.test_type.split("_")[0].upper() 一致。
        """
        test_types = self.get_test_types()
        seen = set()
        models = []
        for t in test_types:
            product = t.get("product", "")
            if product and product not in seen:
                seen.add(product)
                models.append({"model": product, "label": product})
        return models

    def get_show_config(self) -> dict:
        """获取 UI 控件显示配置"""
        return dict(self._read_ini("show_config.ini"))

    def get_script_cmd_config(self, test_type: str = None) -> dict:
        """获取脚本命令配置

        根据测试类型从对应的子目录读取 script_cmd_cfg.ini。
        SE9 → SE9_cfg/script_cmd_cfg.ini
        EVB → EVB_cfg/script_cmd_cfg.ini
        """
        if test_type:
            subdir = TEST_TYPE_TO_CFG_SUBDIR.get(test_type, "SE9_cfg")
            cfg_path = Config.CFG_DIR / subdir / "script_cmd_cfg.ini"
        else:
            cfg_path = Config.CFG_DIR / "script_cmd_cfg.ini"

        parser = configparser.ConfigParser()
        if cfg_path.exists():
            parser.read(str(cfg_path), encoding="utf-8")

        result = {}
        for section in parser.sections():
            result[section] = dict(parser[section])
        return result

    def get_fw_version_config(self, test_type: str = None) -> dict:
        """获取固件版本配置

        根据测试类型从对应的子目录读取 fw_version_cfg.ini。
        """
        if test_type:
            subdir = TEST_TYPE_TO_CFG_SUBDIR.get(test_type, "SE9_cfg")
            cfg_path = Config.CFG_DIR / subdir / "fw_version_cfg.ini"
        else:
            cfg_path = Config.CFG_DIR / "fw_version_cfg.ini"

        parser = configparser.ConfigParser()
        if cfg_path.exists():
            parser.read(str(cfg_path), encoding="utf-8")

        result = {}
        for section in parser.sections():
            result[section] = dict(parser[section])
        return result

    def build_test_steps(self, test_type: str, product_model: str, task: dict) -> list:
        """构建测试步骤列表

        根据 test_type 和 test_case_config.ini 构建 TestStep 序列。
        这是核心方法，将配置文件中的用例定义转化为可执行的步骤序列。
        """
        from ..models.test_case import TestStep
        from ..engine.script_runner import ScriptRunner
        from ..engine.device_ops import DeviceOps
        import logging
        logger = logging.getLogger(__name__)

        script_runner = ScriptRunner(test_type=test_type)
        test_cases = self.get_test_cases(test_type)
        enabled_cases = [c for c in test_cases if c["enabled"]]

        steps = []
        for i, case in enumerate(enabled_cases):
            name = case["name"]

            # OEM 写入：只有用户明确要求时才执行
            if name == "burn_oem":
                if not task.get("params", {}).get("write_oem"):
                    logger.info(f"跳过 OEM 写入（未启用）")
                    continue

                oem_profile_name = task.get("params", {}).get("oem_profile", "")
                if not oem_profile_name:
                    logger.warning(f"未指定 oem_profile，跳过 OEM 写入")
                    continue

                def make_burn_oem_execute(case_name, profile_name):
                    def execute(context):
                        import os as _os4
                        import re as _re4
                        from ..config import Config as _Config4

                        test_id = context.get("test_id", "")
                        on_log = context.get("_on_log_callback")
                        ssh = context.get("ssh_client")
                        if not ssh:
                            logger.error(f"[{test_id}] burn_oem: 无 SSH 连接")
                            return False

                        _syslog_path = str(_Config4.LOG_DIR / f"syslog_{test_id}.log")

                        def _push_log(msg):
                            ts = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            logger.info(f"[{test_id}] {msg}")
                            if on_log:
                                on_log(test_id, "INFO", "syslog", msg)
                            try:
                                _os4.makedirs(_os4.path.dirname(_syslog_path), exist_ok=True)
                                with open(_syslog_path, "a") as _lf:
                                    _lf.write(f"[{ts}] {msg}\n")
                            except Exception:
                                pass

                        # 读取 profile 的 OEMconfig.ini
                        oem_path = _Config4.CFG_DIR / "profiles" / profile_name / "OEMconfig.ini"
                        if not oem_path.exists():
                            _push_log(f"OEM 配置文件不存在: {oem_path}")
                            return False

                        with open(oem_path, "r", encoding="utf-8") as _f:
                            oem_content = _f.read()

                        # 解析 key=value 对（跳过 [section] 头和空行/注释）
                        pairs = []
                        for line in oem_content.splitlines():
                            line = line.strip()
                            if not line or line.startswith("#") or line.startswith("["):
                                continue
                            m = _re4.match(r'^(\w+)\s*=\s*(.+)$', line)
                            if m:
                                pairs.append((m.group(1), m.group(2).strip()))

                        if not pairs:
                            _push_log("OEM 配置文件中未找到有效的键值对")
                            return False

                        _push_log(f"开始 OEM 烧录（profile={profile_name}），共 {len(pairs)} 项")
                        all_ok = True
                        for key, value in pairs:
                            cmd = f"./burn_oem.sh {key} {value}"
                            _push_log(f"执行: {cmd}")
                            try:
                                stdout, stderr, code = ssh.exec_cmd(
                                    cmd, timeout=120, sudo=True, sudo_password="linaro"
                                )
                                output = stdout + "\n" + stderr
                                if "QA_PASS_OEM" in output:
                                    _push_log(f"OEM 烧录成功: {key}={value}")
                                elif "QA_FAIL_OEM" in output:
                                    _push_log(f"OEM 烧录失败: {key}={value}")
                                    all_ok = False
                                else:
                                    _push_log(f"OEM 烧录结果未知: {key}={value}, output={output[:200]}")
                                    all_ok = False
                            except Exception as e:
                                _push_log(f"OEM 烧录异常: {key}={value}, {e}")
                                all_ok = False

                        if all_ok:
                            _push_log("OEM 烧录全部完成")
                        else:
                            _push_log("OEM 烧录部分失败")
                        return all_ok
                    return execute

                burn_oem_step = TestStep(
                    name="burn_oem",
                    label="烧录OEM",
                    execute=make_burn_oem_execute("burn_oem", oem_profile_name),
                    timeout=600,
                    required=True,
                )
                steps.append(burn_oem_step)
                continue

            # 上传步骤：管道传输 tgz 到设备并解压（幂等：已存在且完整则跳过）
            elif name == "upload_aging_files":
                def make_upload_execute(case_name):
                    def execute(context):
                        ssh = context.get("ssh_client")
                        if not ssh:
                            return False
                        local_tgz = str(Config.ATHENA2_ROOT / "data" / "AGING_test_files" / "soc_aging" / "athena2_soc_aging_v1_2_5.tgz")
                        import os as _os
                        if not _os.path.exists(local_tgz):
                            logger.error(f"本地 tgz 文件不存在: {local_tgz}")
                            return False

                        test_id = context.get("test_id", "")
                        on_log = context.get("_on_log_callback")
                        import os as _os2

                        # 日志文件路径（仅写入系统日志，老化日志只显示老化程序输出）
                        from ..config import Config as _Config
                        _syslog_path = str(_Config.LOG_DIR / f"syslog_{test_id}.log")

                        def _push_log(msg):
                            """推送日志到 WebSocket 并写入系统日志文件"""
                            ts = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            line = f"[{ts}] {msg}"
                            logger.info(msg)
                            if on_log:
                                on_log(test_id, "INFO", "syslog", msg)
                            try:
                                _os2.makedirs(_os2.path.dirname(_syslog_path), exist_ok=True)
                                with open(_syslog_path, "a") as _lf:
                                    _lf.write(line + "\n")
                            except Exception:
                                pass

                        # 提取老化包版本号
                        _tgz_basename = _os.path.basename(local_tgz)
                        _version_match = __import__("re").search(r'v(\d+[_\d]*)', _tgz_basename)
                        _aging_version = _version_match.group(1).replace("_", ".") if _version_match else "unknown"
                        _push_log(f"老化测试版本: v{_aging_version}")

                        # 1. 幂等性检查：比对本地 tgz 的 MD5 与设备上的部署标记文件
                        _push_log("检查设备上是否已有老化文件...")
                        import hashlib as _hashlib
                        _push_log("计算本地老化包 MD5...")
                        _local_md5 = ""
                        with open(local_tgz, "rb") as _f:
                            _m = _hashlib.md5()
                            _chunk_size = 64 * 1024 * 1024  # 64MB 块读
                            _total_read = 0
                            while True:
                                _chunk = _f.read(_chunk_size)
                                if not _chunk:
                                    break
                                _m.update(_chunk)
                                _total_read += len(_chunk)
                            _local_md5 = _m.hexdigest()
                        _push_log(f"本地老化包 MD5: {_local_md5}")

                        # 检查设备上的部署标记文件
                        stdout, _, _ = ssh.exec_cmd(
                            "cat /data/soc_aging/.deploy_md5 2>/dev/null || echo NOT_FOUND",
                            timeout=10, sudo=True, sudo_password="linaro"
                        )
                        _remote_md5 = stdout.strip()
                        if _remote_md5 and _remote_md5 != "NOT_FOUND":
                            if _remote_md5 == _local_md5:
                                _push_log("设备上老化文件完整且与本地一致，跳过上传（已就绪）")
                                return True
                            else:
                                _push_log(f"设备上老化文件版本不匹配，将重新部署")
                        else:
                            _push_log("设备上尚无老化文件，开始部署")

                        # 2. 管道传输 tgz → 远程 tar 解压（不占用设备磁盘空间）
                        total_size = _os.path.getsize(local_tgz)
                        file_size_mb = total_size / 1024**2
                        _push_log(f"开始上传老化包 ({file_size_mb:.0f} MB)，通过管道直传解压...")

                        def on_progress(sent, total):
                            pct = int(sent / total * 100)
                            _push_log(f"上传进度: {pct}% ({sent / 1024**2:.0f} / {total / 1024**2:.0f} MB)")

                        # 使用 --no-same-owner 避免 tar 因权限不足失败，权限由后续 chmod 统一设置
                        stdout, stderr, code = ssh.pipe_file_to_cmd(
                            local_tgz,
                            "tar -xzf - -C /data --no-same-owner",
                            timeout=900,
                            on_progress=on_progress,
                        )
                        if code != 0:
                            _push_log(f"上传失败 (exit={code}): {stderr[:200]}")
                            return False
                        _push_log("老化包解压完成")

                        # 3. 写入部署标记文件（用于后续快速幂等检查）
                        _push_log("写入部署标记...")
                        stdout, stderr, code = ssh.exec_cmd(
                            f"echo '{_local_md5}' > /data/soc_aging/.deploy_md5",
                            timeout=10, sudo=True, sudo_password="linaro"
                        )
                        if code != 0:
                            _push_log(f"写入部署标记失败: {stderr}")
                            return False

                        # 4. 设置权限
                        _push_log("设置文件权限...")
                        stdout, stderr, code = ssh.exec_cmd(
                            "chmod -R 755 /data/soc_aging",
                            timeout=30, sudo=True, sudo_password="linaro"
                        )
                        if code != 0:
                            _push_log(f"权限设置失败: {stderr}")
                            return False
                        _push_log("老化文件部署完成")
                        return True
                    return execute

                step = TestStep(
                    name=name,
                    label=case["label"],
                    execute=make_upload_execute(name),
                    timeout=900,
                    required=True,
                )
            elif name == "run_aging_test":
                # 使用 aging.sh 启动老化测试，支持 loop/reboot 参数
                def make_run_aging(case_name):
                    def execute(context):
                        ssh = context.get("ssh_client")
                        if not ssh:
                            return False
                        params = context.get("params", {})
                        loop = params.get("loop", 0)
                        reboot = params.get("reboot", 0)
                        chip_type = params.get("chip_model", "bm1688")
                        test_id = context.get("test_id", "")
                        on_log = context.get("_on_log_callback")

                        import os as _os3
                        from ..config import Config as _Config2
                        _syslog_path = str(_Config2.LOG_DIR / f"syslog_{test_id}.log")

                        def _push_syslog(msg):
                            """推送日志到系统日志（老化日志只显示老化程序输出）"""
                            ts = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            line = f"[{ts}] {msg}"
                            logger.info(msg)
                            if on_log:
                                on_log(test_id, "INFO", "syslog", msg)
                            try:
                                _os3.makedirs(_os3.path.dirname(_syslog_path), exist_ok=True)
                                with open(_syslog_path, "a") as _lf:
                                    _lf.write(line + "\n")
                            except Exception:
                                pass

                        _push_syslog(f"启动老化测试: loop={loop}, reboot={reboot}, chip_type={chip_type}")

                        cmd = (
                            f"sh -c 'cd /data/soc_aging && "
                            f"nohup ./aging.sh --chip_type {chip_type} "
                            f"--loop {loop} --reboot {reboot} "
                            f"> /dev/null 2>&1 & echo AGING_STARTED'"
                        )
                        stdout, stderr, code = ssh.exec_cmd(
                            cmd, timeout=30, sudo=True, sudo_password="linaro"
                        )
                        if "AGING_STARTED" in stdout:
                            _push_syslog("老化测试已成功启动，等待日志输出...")
                            return True
                        _push_syslog(f"老化测试启动失败: {stderr[:200]}")
                        return False
                    return execute

                step = TestStep(
                    name=name,
                    label=case["label"],
                    execute=make_run_aging(name),
                    timeout=30,
                    required=True,
                )
            elif name == "monitor_aging":
                # 监控老化日志：实时读取 /data/aging.log
                # 推送 WebSocket，保存到本地，支持 SSH 断线重连、设备重启后恢复
                # syslog 监控优先由 TestManager 在 SSH 连接时启动，
                # 此处作为 fallback 确保旧测试也能获得 syslog 监控
                def make_monitor_aging(case_name):
                    def execute(context):
                        import time
                        from datetime import datetime
                        from ..engine.ssh_client import SSHClient

                        ssh = context.get("ssh_client")
                        device_ip = context.get("device_ip", "")
                        test_id = context.get("test_id", "unknown")

                        on_log = context.get("_on_log_callback")
                        if on_log:
                            on_log(test_id, "INFO", "syslog", f"[自定义] Monitor Aging 开始监控 (ssh={bool(ssh)}, ip={device_ip})")

                        if not ssh or not device_ip:
                            if on_log:
                                on_log(test_id, "ERROR", "syslog", f"[自定义] Monitor Aging 失败: ssh={bool(ssh)}, ip={bool(device_ip)}")
                            return False

                        # 本地日志文件路径
                        aging_log_file = str(Config.LOG_DIR / f"aging_{test_id}.log")
                        syslog_file = str(Config.LOG_DIR / f"syslog_{test_id}.log")
                        os.makedirs(os.path.dirname(aging_log_file), exist_ok=True)

                        on_log = context.get("_on_log_callback")

                        # fallback: 如果 syslog 监控尚未启动（旧测试），在此启动
                        start_syslog_monitor = context.get("_start_syslog_monitor")
                        if start_syslog_monitor:
                            start_syslog_monitor(test_id, ssh, device_ip)

                        logger.info(f"开始监控日志: aging={aging_log_file}")

                        aging_pos = 0
                        prev_aging_pos = -1
                        idle_count = 0
                        max_idle = 120  # 10 分钟无新日志视为异常
                        start_time = time.time()
                        max_duration = 86400 * 3  # 最长 3 天

                        # 跳到 /data/aging.log 当前末尾，跳过旧测试的残留日志
                        # 注意：不能使用 < 重定向，因为在 sudo 模式下
                        # cmd 会被包装为 echo 'linaro' | sudo -S {cmd}，
                        # < 重定向会应用到 echo 而非 wc
                        try:
                            chk, _, _ = ssh.exec_cmd(
                                "stat -c%s /data/aging.log 2>/dev/null || echo 0", timeout=5,
                                sudo=True, sudo_password="linaro"
                            )
                            remote_size = int(chk.strip())
                            if remote_size > 0:
                                aging_pos = remote_size
                                if on_log:
                                    on_log(test_id, "INFO", "aging",
                                           f"跳过旧日志 {remote_size} 字节，从末尾开始监控")
                        except (ValueError, Exception):
                            pass

                        def read_remote_log(remote_path, last_pos, source, local_file, sudo=False):
                            """读取远程日志增量，返回 (new_pos, has_pass, has_fail)"""
                            if sudo:
                                stdout, stderr, code = ssh.exec_cmd(
                                    f"tail -c +{last_pos + 1} {remote_path} 2>/dev/null || echo ''",
                                    timeout=10, sudo=True, sudo_password="linaro"
                                )
                            else:
                                stdout, stderr, code = ssh.exec_cmd(
                                    f"tail -c +{last_pos + 1} {remote_path} 2>/dev/null || echo ''",
                                    timeout=10
                                )
                            new_content = stdout
                            new_pos = last_pos
                            has_pass = False
                            has_fail = False

                            if new_content and new_content.strip():
                                lines = new_content.split("\n")
                                for line in lines:
                                    if not line.strip():
                                        continue
                                    ts = datetime.now().isoformat()
                                    try:
                                        with open(local_file, "a") as f:
                                            f.write(f"[{ts}] {line}\n")
                                    except Exception:
                                        pass
                                    if on_log:
                                        on_log(test_id, "INFO", source, line)
                                    new_pos += len(line.encode()) + 1

                                    if source == "aging":
                                        if "AGING_PASS_TEST" in line or "AGING_REBOOT_PASS" in line:
                                            has_pass = True
                                        if "AGING_FAIL_TEST" in line or "AGING_REBOOT_FAIL" in line:
                                            has_fail = True

                            return new_pos, has_pass, has_fail

                        def check_truncated(remote_path, last_pos, sudo=False):
                            """检查远程文件是否被截断"""
                            try:
                                if sudo:
                                    chk, _, _ = ssh.exec_cmd(
                                        f"stat -c%s {remote_path} 2>/dev/null || echo 0", timeout=5,
                                        sudo=True, sudo_password="linaro"
                                    )
                                else:
                                    chk, _, _ = ssh.exec_cmd(
                                        f"stat -c%s {remote_path} 2>/dev/null || echo 0", timeout=5
                                    )
                                return int(chk.strip()) < last_pos
                            except (ValueError, Exception):
                                return False

                        def reconnect_ssh():
                            """尝试重新连接 SSH"""
                            if not SSHClient.is_ip_alive(device_ip, timeout=3):
                                if on_log:
                                    on_log(test_id, "INFO", "aging", f"设备 {device_ip} 离线，等待恢复...")
                                while not SSHClient.is_ip_alive(device_ip, timeout=3):
                                    time.sleep(10)
                                if on_log:
                                    on_log(test_id, "INFO", "aging", f"设备 {device_ip} 恢复在线，等待 SSH 就绪...")
                                time.sleep(15)
                            if ssh.connect(device_ip, user="linaro", password="linaro", timeout=10):
                                if on_log:
                                    on_log(test_id, "INFO", "aging", "SSH 重新连接成功")
                                return True
                            else:
                                if on_log:
                                    on_log(test_id, "WARN", "aging", "SSH 重新连接失败")
                                return False

                        while True:
                            if time.time() - start_time > max_duration:
                                logger.error("老化测试监控超时（3天）")
                                if on_log:
                                    on_log(test_id, "ERROR", "aging", "老化测试监控超时（72小时）")
                                return False

                            try:
                                # 读取 aging.log
                                aging_pos, has_pass, has_fail = read_remote_log(
                                    "/data/aging.log", aging_pos, "aging", aging_log_file, sudo=True
                                )
                                if has_pass:
                                    logger.info("老化测试完成: PASS")
                                    if on_log:
                                        on_log(test_id, "INFO", "aging", "老化测试完成: PASS")
                                    return True
                                if has_fail:
                                    logger.error("老化测试失败")
                                    if on_log:
                                        on_log(test_id, "ERROR", "aging", "老化测试失败")
                                    return False

                                # 空闲检测
                                if aging_pos == prev_aging_pos:
                                    idle_count += 1
                                else:
                                    idle_count = 0

                                prev_aging_pos = aging_pos

                                if idle_count > max_idle:
                                    logger.warning("日志长时间无更新")
                                    if on_log:
                                        on_log(test_id, "WARN", "aging", "日志长时间无更新，检查设备状态...")

                                    if reconnect_ssh():
                                        if check_truncated("/data/aging.log", aging_pos):
                                            if on_log:
                                                on_log(test_id, "INFO", "aging", "aging.log 已重置，从头读取")
                                            aging_pos = 0
                                        idle_count = 0

                                time.sleep(5)

                            except Exception as e:
                                logger.error(f"监控日志异常: {e}")
                                if on_log:
                                    on_log(test_id, "WARN", "aging", f"监控异常: {e}，等待重试...")

                                if not ssh.is_connected:
                                    if on_log:
                                        on_log(test_id, "INFO", "aging", "SSH 断开，尝试重新连接...")
                                    if reconnect_ssh():
                                        if check_truncated("/data/aging.log", aging_pos):
                                            aging_pos = 0

                                idle_count += 1
                                time.sleep(10)

                        return False
                    return execute

                step = TestStep(
                    name=name,
                    label="监控老化日志",
                    execute=make_monitor_aging(name),
                    timeout=86400 * 3,  # 最长 3 天
                    required=True,
                )
            elif name in ("led_check", "hdmi_check", "power_key_check", "reset_key_check", "rtc_cell_check"):
                # 交互式检查：旧版弹窗询问操作员，Web 端通过 on_interaction_required 回调实现
                def make_interactive_execute(case_name, _case=case):
                    def execute(context):
                        import os as _os_int
                        from ..config import Config as _Config_int
                        test_id = context.get("test_id", "")
                        on_log = context.get("_on_log_callback")
                        on_interact = context.get("_on_interaction_callback")
                        _syslog_path = str(_Config_int.LOG_DIR / f"syslog_{test_id}.log")

                        def _push_log(msg):
                            ts = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            if on_log:
                                on_log(test_id, "INFO", "syslog", msg)
                            try:
                                _os_int.makedirs(_os_int.path.dirname(_syslog_path), exist_ok=True)
                                with open(_syslog_path, "a") as _lf:
                                    _lf.write(f"[{ts}] {msg}\n")
                            except Exception:
                                pass

                        label = _case.get("label", case_name)
                        _push_log(f"交互检查: {label} — 请在设备端确认")
                        if on_interact:
                            try:
                                result = on_interact(test_id, case_name,
                                    f"请检查设备: {label} 是否正常？",
                                    dialog_type="confirm", timeout=300)
                                if result and result.get("action") == "confirm":
                                    _push_log(f"交互检查通过: {label} (操作员确认)")
                                    return True
                                else:
                                    _push_log(f"交互检查失败: {label} (操作员取消)")
                                    return False
                            except Exception as e:
                                _push_log(f"交互检查异常: {label} — {e}")
                                return False
                        # 无交互回调时默认通过（兼容）
                        _push_log(f"交互检查: {label} — 无交互回调，默认通过")
                        return True
                    return execute

                step = TestStep(
                    name=name,
                    label=case["label"],
                    execute=make_interactive_execute(name),
                    timeout=300,
                    required=False,
                )
            elif name == "upload_test_files":
                # SCP 上传测试文件到 DUT + md5sum 校验
                def make_upload_execute(case_name):
                    def execute(context):
                        import os as _os_up
                        import hashlib as _hashlib
                        from ..config import Config as _Config_up
                        ssh = context.get("ssh_client")
                        test_id = context.get("test_id", "")
                        on_log = context.get("_on_log_callback")
                        _syslog_path = str(_Config_up.LOG_DIR / f"syslog_{test_id}.log")

                        def _push_log(msg):
                            ts = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            if on_log:
                                on_log(test_id, "INFO", "syslog", msg)
                            try:
                                _os_up.makedirs(_os_up.path.dirname(_syslog_path), exist_ok=True)
                                with open(_syslog_path, "a") as _lf:
                                    _lf.write(f"[{ts}] {msg}\n")
                            except Exception:
                                pass

                        if not ssh:
                            _push_log("上传测试文件失败: 无 SSH 连接")
                            return False

                        local_dir = _Config_up.DATA_DIR / "SE9_test_files"
                        if not local_dir.exists():
                            _push_log(f"上传测试文件失败: 本地目录不存在 {local_dir}")
                            return False

                        _push_log("开始上传测试文件到设备...")
                        try:
                            # 创建远程目录
                            ssh.exec_cmd("mkdir -p /data/SE9_test_files", timeout=10,
                                        sudo=True, sudo_password="linaro")
                            ssh.exec_cmd("chown linaro:linaro /data/SE9_test_files", timeout=10,
                                        sudo=True, sudo_password="linaro")

                            # 逐个上传文件
                            import os as _os_up2
                            all_ok = True
                            for fname in _os_up2.listdir(str(local_dir)):
                                local_path = local_dir / fname
                                if not local_path.is_file():
                                    continue
                                if fname.endswith(".md5"):
                                    continue
                                _push_log(f"  上传: {fname}")
                                remote_path = f"/data/SE9_test_files/{fname}"
                                ok = ssh.upload_file(str(local_path), remote_path)
                                if not ok:
                                    _push_log(f"  上传失败: {fname}")
                                    all_ok = False

                            if all_ok:
                                ssh.exec_cmd("chmod +x /data/SE9_test_files/*.sh", timeout=10,
                                            sudo=True, sudo_password="linaro")
                                _push_log("测试文件上传完成，开始 md5sum 校验...")
                                # 从本地 md5 文件读取期望值
                                md5_file = local_dir / "SE9_test_files.md5"
                                if md5_file.exists():
                                    with open(str(md5_file), "r") as _mf:
                                        expected = {}
                                        for line in _mf:
                                            line = line.strip()
                                            if not line:
                                                continue
                                            parts = line.split()
                                            if len(parts) >= 2:
                                                expected[parts[1].lstrip("./")] = parts[0]

                                    stdout, _, _ = ssh.exec_cmd(
                                        "cd /data/SE9_test_files && md5sum * 2>/dev/null", timeout=30,
                                        sudo=True, sudo_password="linaro"
                                    )
                                    for line in stdout.split("\n"):
                                        line = line.strip()
                                        if not line:
                                            continue
                                        parts = line.split()
                                        if len(parts) >= 2:
                                            fname = parts[1]
                                            actual_md5 = parts[0]
                                            exp = expected.get(fname, "")
                                            if exp and actual_md5 != exp:
                                                _push_log(f"  MD5 不匹配: {fname} (期望={exp[:8]}..., 实际={actual_md5[:8]}...)")
                                                all_ok = False

                            if all_ok:
                                _push_log("测试文件上传完成且校验通过")
                            else:
                                _push_log("测试文件上传或校验存在问题")
                            return all_ok
                        except Exception as e:
                            _push_log(f"上传测试文件异常: {e}")
                            return False
                    return execute

                step = TestStep(
                    name=name,
                    label=case["label"],
                    execute=make_upload_execute(name),
                    timeout=300,
                    required=True,
                )
            elif name == "remove_test_files":
                # 清理 DUT 上的测试文件
                def make_remove_execute(case_name):
                    def execute(context):
                        import os as _os_rm
                        from ..config import Config as _Config_rm
                        ssh = context.get("ssh_client")
                        test_id = context.get("test_id", "")
                        on_log = context.get("_on_log_callback")
                        _syslog_path = str(_Config_rm.LOG_DIR / f"syslog_{test_id}.log")

                        def _push_log(msg):
                            ts = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            if on_log:
                                on_log(test_id, "INFO", "syslog", msg)
                            try:
                                _os_rm.makedirs(_os_rm.path.dirname(_syslog_path), exist_ok=True)
                                with open(_syslog_path, "a") as _lf:
                                    _lf.write(f"[{ts}] {msg}\n")
                            except Exception:
                                pass

                        if not ssh:
                            _push_log("清理测试文件失败: 无 SSH 连接")
                            return False

                        _push_log("清理设备上的测试文件...")
                        try:
                            ssh.exec_cmd("rm -rf /data/SE9_test_files", timeout=10,
                                        sudo=True, sudo_password="linaro")
                            _push_log("测试文件清理完成")
                            return True
                        except Exception as e:
                            _push_log(f"清理测试文件异常: {e}")
                            return False
                    return execute

                step = TestStep(
                    name=name,
                    label=case["label"],
                    execute=make_remove_execute(name),
                    timeout=30,
                    required=False,
                )
            elif name == "ddr_size_check":
                def make_ddr_check_execute(case_name):
                    def execute(context):
                        import re as _re_ddr
                        ssh = context.get("ssh_client")
                        test_id = context.get("test_id", "")
                        on_log = context.get("_on_log_callback")
                        import os as _os_ddr
                        from ..config import Config as _Config_ddr
                        _syslog_path = str(_Config_ddr.LOG_DIR / f"syslog_{test_id}.log")
                        def _push_log(msg):
                            ts = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            if on_log:
                                on_log(test_id, "INFO", "syslog", msg)
                            try:
                                _os_ddr.makedirs(_os_ddr.path.dirname(_syslog_path), exist_ok=True)
                                with open(_syslog_path, "a") as _lf:
                                    line = f"[{ts}] {msg}"
                                    _lf.write(line + "\n")
                            except Exception:
                                pass
                        if not ssh:
                            _push_log("DDR检查失败: 无 SSH 连接")
                            return False
                        _push_log("DDR检查: 读取 show_ddr...")
                        try:
                            stdout, stderr, code = ssh.exec_cmd(
                                "show_ddr 2>/dev/null", timeout=10,
                                sudo=True, sudo_password="linaro"
                            )
                        except Exception as e:
                            _push_log(f"DDR检查失败: show_ddr 执行异常: {e}")
                            return False
                        output = stdout + "\n" + stderr
                        m = _re_ddr.search(r"SIZE\s*:\s*(\d+)\s*(MB|GB)", output, _re_ddr.IGNORECASE)
                        if not m:
                            _push_log(f"DDR检查失败: show_ddr 输出中未找到 SIZE 字段, output={output[:200]}")
                            return False
                        actual_gb = int(m.group(1))
                        if m.group(2).upper() == "MB":
                            actual_gb = actual_gb // 1024
                        _push_log(f"DDR检查: 实际 DDR = {actual_gb}GB")
                        try:
                            stdout2, _, _ = ssh.exec_cmd(
                                "cat /factory/OEMconfig.ini 2>/dev/null", timeout=10,
                                sudo=True, sudo_password="linaro"
                            )
                        except Exception as e:
                            _push_log(f"DDR检查失败: 读取 OEMconfig.ini 异常: {e}")
                            return False
                        m2 = _re_ddr.search(r"DTS_TYPE\s*=\s*(\S+)", stdout2)
                        if not m2:
                            _push_log("DDR检查失败: OEMconfig.ini 中未找到 DTS_TYPE")
                            return False
                        dts_type = m2.group(1).strip()
                        _push_log(f"DDR检查: DTS_TYPE = {dts_type}")
                        m3 = _re_ddr.search(r"_(\d+)G", dts_type, _re_ddr.IGNORECASE)
                        if not m3:
                            _push_log(f"DDR检查失败: DTS_TYPE 中未解析到容量 (_XG), dts_type={dts_type}")
                            return False
                        expected_gb = int(m3.group(1))
                        _push_log(f"DDR检查: 期望 DDR = {expected_gb}GB")
                        if actual_gb == expected_gb:
                            _push_log(f"DDR检查通过: 实际 {actual_gb}GB == 期望 {expected_gb}GB")
                            return True
                        else:
                            _push_log(f"DDR检查失败: 实际 {actual_gb}GB != 期望 {expected_gb}GB (DTS_TYPE={dts_type})")
                            return False
                    return execute
                step = TestStep(
                    name=name,
                    label=case["label"],
                    execute=make_ddr_check_execute(name),
                    timeout=30,
                    required=True,
                )
            else:
                def make_execute(case_name, sr, _case=case):
                    def execute(context):
                        test_id = context.get("test_id", "")
                        on_log = context.get("_on_log_callback")
                        label = _case.get("label", case_name)

                        import os as _os3
                        from ..config import Config as _Config3
                        _syslog_path = str(_Config3.LOG_DIR / f"syslog_{test_id}.log")

                        def _push_log(msg):
                            """推送日志到系统日志（老化日志只显示老化程序输出）"""
                            ts = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            line = f"[{ts}] {msg}"
                            if on_log:
                                on_log(test_id, "INFO", "syslog", msg)
                            try:
                                _os3.makedirs(_os3.path.dirname(_syslog_path), exist_ok=True)
                                with open(_syslog_path, "a") as _lf:
                                    _lf.write(line + "\n")
                            except Exception:
                                pass

                        _push_log(f"开始执行: {label}")
                        serial = context.get("serial_client")
                        ssh = context.get("ssh_client")
                        if serial:
                            result = sr.run_serial(serial, case_name)
                        elif ssh:
                            result = sr.run_ssh(ssh, case_name)
                        else:
                            _push_log(f"失败: {label} — 无可用连接")
                            return False
                        ok = result["result"] == "pass"
                        if ok:
                            _push_log(f"完成: {label} — 通过 (耗时 {result.get('duration', 0):.1f}s)")
                        else:
                            output = result.get("output", "")
                            # 提取关键错误信息：优先 QA_FAIL 行，其次最后几行非空输出
                            lines = [l.strip() for l in output.split("\n") if l.strip()]
                            fail_lines = [l for l in lines if "QA_FAIL" in l or "fail" in l.lower() or "error" in l.lower() or "not found" in l.lower() or "No such" in l.lower()]
                            if fail_lines:
                                detail = "; ".join(fail_lines[-3:])
                            elif lines:
                                detail = "; ".join(lines[-3:])
                            else:
                                detail = "(无输出，可能是硬件未连接或脚本立即退出)"
                            _push_log(f"失败: {label} — {detail}")
                        return ok
                    return execute

                step = TestStep(
                    name=name,
                    label=case["label"],
                    execute=make_execute(name, script_runner),
                    timeout=30,
                    required=False,
                )
            steps.append(step)

        return steps

    def validate_oem_file(self, file_path: str) -> dict:
        """校验 OEM 配置文件"""
        try:
            parser = configparser.ConfigParser()
            parser.read(file_path, encoding="utf-8")
            product_model = ""
            if "common" in parser:
                product_model = parser.get("common", "product_model", fallback="")
            return {"valid": bool(product_model), "product_model": product_model, "message": "OK"}
        except Exception as e:
            return {"valid": False, "product_model": "", "message": str(e)}

    def create_product_model(self, data: dict) -> dict:
        """创建新的产品型号

        写入 ui_config.ini、test_case_config.ini、script_cmd_cfg.ini。
        所有校验通过后才执行写入操作。

        Args:
            data: {
                "product_name": "SE10",
                "display_label": "SE10接口测试",
                "test_types": [
                    {
                        "type_key": "se10_interface_test",
                        "label": "SE10 接口测试",
                        "category": "test",
                        "test_cases": [
                            {
                                "name": "chip_type_check",
                                "enabled": true,
                                "script_cmd": {
                                    "exec_cmd": "./test_chip.sh",
                                    "pass_flag": "QA_PASS_CHIP",
                                    "fail_flag": "QA_FAIL_CHIP",
                                    "case_timeout": 120
                                }
                            }
                        ]
                    }
                ]
            }

        Returns:
            {"success": True, "product_name": "SE10", "message": "..."}

        Raises:
            ValueError: 校验失败
        """
        errors = self._validate_product_model(data)
        if errors:
            raise ValueError("; ".join(errors))

        product_name = data["product_name"]
        display_label = data["display_label"]
        test_types = data["test_types"]

        # 1. 写入 ui_config.ini
        #    - [PRODUCT_NAME] section: display_label = 1
        #    - [test_case] / [other_case]: type_key = 1
        self._append_ini_section(
            Config.CFG_DIR / "ui_config.ini",
            product_name,
            {display_label: "1"},
            comment=f"# {product_name} 产品"
        )
        for tt in test_types:
            target_section = "test_case" if tt["category"] == "test" else "other_case"
            self._append_ini_section(
                Config.CFG_DIR / "ui_config.ini",
                target_section,
                {tt["type_key"]: "1"},
            )

        # 2. 写入 test_case_config.ini
        #    section 名格式: {PRODUCT}_{test_suffix}
        #    如 se10_interface_test → SE10_interface_test
        for tt in test_types:
            section_name = TEST_TYPE_TO_SECTION.get(tt["type_key"])
            if not section_name:
                # 约定：type_key = {product}_{suffix}，section = {PRODUCT}_{suffix}
                parts = tt["type_key"].split("_", 1)
                if len(parts) == 2:
                    section_name = f"{parts[0].upper()}_{parts[1]}"
                else:
                    section_name = tt["type_key"].upper()
            enabled_cases = {c["name"]: "1" for c in tt["test_cases"] if c.get("enabled", True)}
            disabled_cases = {c["name"]: "0" for c in tt["test_cases"] if not c.get("enabled", True)}
            items = {**enabled_cases, **disabled_cases}
            self._append_ini_section(
                Config.CFG_DIR / "test_case_config.ini",
                section_name,
                items,
            )

        # 3. 创建 <PRODUCT>_cfg/script_cmd_cfg.ini
        subdir = Config.CFG_DIR / f"{product_name}_cfg"
        os.makedirs(subdir, exist_ok=True)
        script_cfg_path = subdir / "script_cmd_cfg.ini"

        for tt in test_types:
            for tc in tt["test_cases"]:
                if not tc.get("enabled", True):
                    continue
                cmd = tc.get("script_cmd", {})
                if cmd:
                    self._append_ini_section(
                        script_cfg_path,
                        tc["name"].upper(),
                        {
                            "exec_cmd": cmd.get("exec_cmd", ""),
                            "pass_flag": cmd.get("pass_flag", "PASS"),
                            "fail_flag": cmd.get("fail_flag", "FAIL"),
                            "case_timeout": str(cmd.get("case_timeout", 120)),
                        },
                    )

        # 4. 创建 <PRODUCT>_cfg/fw_version_cfg.ini（空模板）
        fw_cfg_path = subdir / "fw_version_cfg.ini"
        if not fw_cfg_path.exists():
            fw_cfg_path.write_text(
                f"# {product_name} 固件版本配置\n"
                f"# [{product_name}_v1_0]\n"
                f"# KernelVersion = ''\n"
                f"# MCUVersion = ''\n",
                encoding="utf-8",
            )

        logger.info("Product model created: %s", product_name)
        return {"success": True, "product_name": product_name, "message": f"产品型号 {product_name} 创建成功"}

    def _validate_product_model(self, data: dict) -> list:
        """校验产品型号数据，返回错误列表"""
        errors = []

        product_name = data.get("product_name", "").strip()
        if not product_name:
            errors.append("产品名称不能为空")
        elif not re.match(r'^[A-Za-z0-9_]+$', product_name):
            errors.append("产品名称只能包含字母、数字和下划线")

        if not data.get("display_label", "").strip():
            errors.append("显示标签不能为空")

        test_types = data.get("test_types", [])
        if not test_types:
            errors.append("至少需要一个测试类型")
        else:
            for i, tt in enumerate(test_types):
                prefix = f"测试类型[{i+1}]"
                if not tt.get("type_key", "").strip():
                    errors.append(f"{prefix}: type_key 不能为空")
                if not tt.get("label", "").strip():
                    errors.append(f"{prefix}: label 不能为空")

                test_cases = tt.get("test_cases", [])
                enabled_cases = [c for c in test_cases if c.get("enabled", True)]
                if not enabled_cases:
                    errors.append(f"{prefix}: 至少需要一个启用的测试用例")
                else:
                    for j, tc in enumerate(enabled_cases):
                        tc_prefix = f"{prefix} 用例[{j+1}]"
                        if not tc.get("name", "").strip():
                            errors.append(f"{tc_prefix}: 用例名称不能为空")
                        cmd = tc.get("script_cmd", {})
                        if not cmd:
                            errors.append(f"{tc_prefix}: 脚本命令不能为空")
                        else:
                            if not cmd.get("exec_cmd", "").strip():
                                errors.append(f"{tc_prefix}: exec_cmd 不能为空")
                            if not cmd.get("pass_flag", "").strip():
                                errors.append(f"{tc_prefix}: pass_flag 不能为空")
                            if not cmd.get("fail_flag", "").strip():
                                errors.append(f"{tc_prefix}: fail_flag 不能为空")

        return errors

    def _append_ini_section(self, filepath, section: str, items: dict, comment: str = None):
        """向 ini 文件追加 section

        如果 section 已存在，追加 items 到该 section 末尾（不覆盖已有 key）。
        如果 section 不存在，在文件末尾新建。

        Args:
            filepath: ini 文件路径
            section: section 名称
            items: {key: value} 字典
            comment: 可选注释（仅新建 section 时添加）
        """
        parser = configparser.ConfigParser()
        parser.optionxform = str
        if filepath.exists():
            parser.read(str(filepath), encoding="utf-8")

        if section not in parser:
            parser.add_section(section)

        for key, value in items.items():
            if value is not None:
                parser.set(section, key, str(value))

        with open(filepath, "w", encoding="utf-8") as f:
            parser.write(f)

    def get_product_templates(self) -> dict:
        """获取创建产品型号时可用的模板数据

        返回所有已知测试用例名称、脚本命令模板和测试类型后缀。
        """
        # 收集所有已有测试用例名称
        test_cfg = self._read_ini("test_case_config.ini")
        all_case_names = set()
        for section in test_cfg.sections():
            for name in test_cfg[section]:
                all_case_names.add(name)

        # 收集脚本命令模板（从所有现有产品的 script_cmd_cfg.ini）
        script_templates = {}
        cfg_dir = Config.CFG_DIR
        for subdir_name in os.listdir(str(cfg_dir)):
            subdir = cfg_dir / subdir_name
            if subdir.is_dir() and subdir_name.endswith("_cfg"):
                script_path = subdir / "script_cmd_cfg.ini"
                if script_path.exists():
                    parser = configparser.ConfigParser()
                    parser.optionxform = str
                    parser.read(str(script_path), encoding="utf-8")
                    for section in parser.sections():
                        if section.lower() not in script_templates:
                            script_templates[section.lower()] = {
                                "exec_cmd": parser.get(section, "exec_cmd", fallback=""),
                                "pass_flag": parser.get(section, "pass_flag", fallback="PASS"),
                                "fail_flag": parser.get(section, "fail_flag", fallback="FAIL"),
                                "case_timeout": parser.getint(section, "case_timeout", fallback=120),
                            }

        return {
            "test_case_names": sorted(all_case_names),
            "test_type_suffixes": [
                {"key": "interface_test", "label": "接口测试"},
                {"key": "aging_test", "label": "老化测试"},
                {"key": "mac_check", "label": "MAC地址校验"},
            ],
            "script_cmd_templates": script_templates,
        }

    def _get_product_type(self, test_type_key: str) -> str:
        """从测试类型 key 提取产品类型（SE9, EVB, SE10, ...）

        se9_interface_test → SE9
        evb_aging_test → EVB
        se10_interface_test → SE10
        """
        # 已知映射优先
        if test_type_key in TEST_TYPE_TO_CFG_SUBDIR:
            return TEST_TYPE_TO_CFG_SUBDIR[test_type_key].replace("_cfg", "")
        # 通用规则：取第一个下划线前的部分，转大写
        parts = test_type_key.split("_", 1)
        return parts[0].upper()

    def _read_ini(self, filename: str) -> configparser.ConfigParser:
        parser = configparser.ConfigParser()
        parser.optionxform = str  # 保留 key 原始大小写
        cfg_path = Config.CFG_DIR / filename
        if cfg_path.exists():
            parser.read(str(cfg_path), encoding="utf-8")
        else:
            logger.warning("Config file not found: %s", cfg_path)
        return parser

    def _get_type_label(self, type_key: str) -> str:
        """获取测试类型的中文标签

        优先使用硬编码标签，再通过产品 section 查找，
        最后回退到 type_key 格式化。
        """
        # 优先：硬编码标签
        labels = {
            "se9_interface_test": "SE9-整机接口测试",
            "se9_aging_test": "SE9-整机老化测试",
            "evb_interface_test": "EVB接口测试",
            "evb_aging_test": "EVB老化测试",
            "se9_mac_check": "SE9-MAC地址校验",
        }
        if type_key in labels:
            return labels[type_key]

        # 从产品 section 查找：提取产品名，读 [PRODUCT] section 第一个 key 作为标签
        product = self._get_product_type(type_key)
        ui_cfg = self._read_ini("ui_config.ini")
        if product in ui_cfg:
            for key, value in ui_cfg[product].items():
                if value.strip() == "1":
                    return f"{product}-{key.upper()}"

        # 最终回退
        return type_key.replace("_", " ").title()

    def _get_type_description(self, type_key: str) -> str:
        descriptions = {
            "se9_interface_test": "SE9 整机接口功能测试，包含芯片、DDR、固件、LED、HDMI、USB、网络等",
            "se9_aging_test": "SE9 整机老化测试，长时间运行稳定性验证",
            "evb_interface_test": "EVB 开发板接口功能测试",
            "evb_aging_test": "EVB 开发板老化测试",
            "se9_mac_check": "SE9 MAC 地址校验",
        }
        return descriptions.get(type_key, "")

    def _get_case_label(self, case_name: str) -> str:
        return case_name.replace("_", " ").title()

    # ============================================================
    #  Profile 管理（OEM 配置文件持久化）
    # ============================================================

    @property
    def profiles_dir(self):
        from ..config import Config
        return Config.CFG_DIR / "profiles"

    def _ensure_profiles_dir(self):
        """确保 profiles 目录和 index.json 存在"""
        import os as _os
        _os.makedirs(self.profiles_dir, exist_ok=True)
        index_path = self.profiles_dir / "index.json"
        if not index_path.exists():
            with open(index_path, "w") as f:
                __import__("json").dump([], f)

    def _load_profiles_index(self) -> list:
        """加载 profile 索引"""
        self._ensure_profiles_dir()
        import json as _json
        with open(self.profiles_dir / "index.json", "r") as f:
            return _json.load(f)

    def _save_profiles_index(self, profiles: list):
        """保存 profile 索引"""
        self._ensure_profiles_dir()
        import json as _json
        with open(self.profiles_dir / "index.json", "w") as f:
            _json.dump(profiles, f, indent=2, ensure_ascii=False)

    def list_profiles(self) -> list:
        """列出所有 profile"""
        return self._load_profiles_index()

    def create_profile(self, name: str, oem_content: str) -> dict:
        """创建新的 profile

        Args:
            name: profile 名称（如 SE9-16-BP1-18）
            oem_content: OEMconfig.ini 文件内容（文本）
        """
        import os as _os
        import re as _re
        from datetime import datetime

        if not name or not _re.match(r'^[A-Za-z0-9_\-]+$', name):
            raise ValueError(f"无效的 profile 名称: {name}，仅支持字母、数字、下划线、连字符")
        if not oem_content or not oem_content.strip():
            raise ValueError("OEM 配置文件内容不能为空")

        profiles = self._load_profiles_index()
        for p in profiles:
            if p["name"] == name:
                raise ValueError(f"Profile '{name}' 已存在")

        profile_dir = self.profiles_dir / name
        _os.makedirs(profile_dir, exist_ok=True)
        oem_path = profile_dir / "OEMconfig.ini"
        with open(oem_path, "w", encoding="utf-8") as f:
            f.write(oem_content)

        product_model = ""
        m = _re.search(r'PRODUCT\s*=\s*(\S+)', oem_content)
        if m:
            product_model = m.group(1)

        now = datetime.now().isoformat()
        entry = {
            "name": name,
            "product_model": product_model or (name.split("-")[0] if "-" in name else ""),
            "created_at": now,
            "updated_at": now,
            "oem_size": len(oem_content.encode("utf-8")),
        }
        profiles.append(entry)
        self._save_profiles_index(profiles)
        logger.info(f"创建 Profile: {name}, product_model={product_model}")
        return entry

    def get_profile(self, name: str) -> dict:
        """获取 profile 详情（含 OEM 文件内容 + test_options）"""
        import os as _os

        profiles = self._load_profiles_index()
        for p in profiles:
            if p["name"] == name:
                oem_path = self.profiles_dir / name / "OEMconfig.ini"
                oem_content = ""
                if oem_path.exists():
                    with open(oem_path, "r", encoding="utf-8") as f:
                        oem_content = f.read()
                result = {**p, "oem_content": oem_content}
                # 读取 profile.json 获取 test_type 和 test_options
                profile_json = self.profiles_dir / name / "profile.json"
                if profile_json.exists():
                    import json as _json
                    with open(profile_json, "r", encoding="utf-8") as _pf:
                        pdata = _json.load(_pf)
                    result["test_type"] = pdata.get("test_type", "")
                    result["product_model"] = pdata.get("product_model", "")
                    result["test_options"] = pdata.get("test_options", {})
                return result
        raise ValueError(f"Profile '{name}' 不存在")

    def update_profile_oem(self, name: str, oem_content: str) -> dict:
        """更新 profile 的 OEM 配置文件"""
        import os as _os
        import re as _re
        from datetime import datetime

        if not oem_content or not oem_content.strip():
            raise ValueError("OEM 配置文件内容不能为空")

        profiles = self._load_profiles_index()
        for p in profiles:
            if p["name"] == name:
                profile_dir = self.profiles_dir / name
                if not profile_dir.exists():
                    raise ValueError(f"Profile 目录不存在: {name}")
                oem_path = profile_dir / "OEMconfig.ini"
                with open(oem_path, "w", encoding="utf-8") as f:
                    f.write(oem_content)

                m = _re.search(r'PRODUCT\s*=\s*(\S+)', oem_content)
                if m:
                    p["product_model"] = m.group(1)
                p["updated_at"] = datetime.now().isoformat()
                p["oem_size"] = len(oem_content.encode("utf-8"))
                self._save_profiles_index(profiles)
                logger.info(f"更新 Profile OEM: {name}")
                return p
        raise ValueError(f"Profile '{name}' 不存在")

    def delete_profile(self, name: str):
        """删除 profile"""
        import shutil
        import os as _os

        profiles = self._load_profiles_index()
        new_profiles = [p for p in profiles if p["name"] != name]
        if len(new_profiles) == len(profiles):
            raise ValueError(f"Profile '{name}' 不存在")
        self._save_profiles_index(new_profiles)

        profile_dir = self.profiles_dir / name
        if profile_dir.exists():
            shutil.rmtree(profile_dir, ignore_errors=True)

        logger.info(f"删除 Profile: {name}")

    def update_profile_test_options(self, name: str, test_options: dict) -> dict:
        """更新 profile 的测试选项

        Args:
            name: profile 名称
            test_options: 测试选项字典，如 {"burn_emmc": True, "chip_type_check": False}
        """
        from datetime import datetime

        profiles = self._load_profiles_index()
        for p in profiles:
            if p["name"] == name:
                p["test_options"] = test_options
                p["updated_at"] = datetime.now().isoformat()
                self._save_profiles_index(profiles)
                logger.info(f"更新 Profile 测试选项: {name}, options={len(test_options)}")
                return p
        raise ValueError(f"Profile '{name}' 不存在")