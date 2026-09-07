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
                            "requires_serial": key != "se9_mac_check",
                            "requires_network": "aging" in key,
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

            # 上传步骤：SFTP 上传 tgz 到设备，解压后删除 tgz
            if name == "upload_aging_files":
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
                        remote_tgz = "/data/athena2_soc_aging_v1_2_5.tgz"
                        # 1. SFTP 上传 tgz 到设备
                        logger.info(f"SFTP 上传 tgz: {local_tgz} -> {remote_tgz}")
                        if not ssh.upload_file(local_tgz, remote_tgz):
                            return False
                        # 2. 在设备上解压
                        logger.info("在设备上解压 tgz...")
                        stdout, stderr, code = ssh.exec_cmd(
                            f"tar -xzf {remote_tgz} -C /data",
                            timeout=300, sudo=True, sudo_password="linaro"
                        )
                        if code != 0:
                            logger.error(f"解压失败: {stderr}")
                            return False
                        # 3. 删除 tgz 释放空间
                        logger.info("删除 tgz 释放空间...")
                        ssh.exec_cmd(
                            f"rm -f {remote_tgz}",
                            timeout=10, sudo=True, sudo_password="linaro"
                        )
                        # 4. 校验 MD5
                        stdout, stderr, code = ssh.exec_cmd(
                            'sh -c "cd /data/soc_aging && md5sum -c soc_aging.md5"',
                            timeout=60, sudo=True, sudo_password="linaro"
                        )
                        output = stdout + "\n" + stderr
                        if "FAILED" in output or code != 0:
                            logger.error(f"MD5 校验失败: {output}")
                            return False
                        # 5. 设置权限
                        stdout, stderr, code = ssh.exec_cmd(
                            "chmod -R 755 /data/soc_aging",
                            timeout=30, sudo=True, sudo_password="linaro"
                        )
                        if code != 0:
                            logger.error(f"权限设置失败: {stderr}")
                            return False
                        return True
                    return execute

                step = TestStep(
                    name=name,
                    label=case["label"],
                    execute=make_upload_execute(name),
                    timeout=600,
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
                        chip_type = "bm1688"  # SE9 固定为 bm1688

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
                            logger.info(f"老化测试已启动: loop={loop}, reboot={reboot}")
                            return True
                        logger.error(f"老化测试启动失败: {stderr}")
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
                        if not ssh or not device_ip:
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
                                        f"wc -c < {remote_path} 2>/dev/null || echo 0", timeout=5,
                                        sudo=True, sudo_password="linaro"
                                    )
                                else:
                                    chk, _, _ = ssh.exec_cmd(
                                        f"wc -c < {remote_path} 2>/dev/null || echo 0", timeout=5
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
                                    "/data/aging.log", aging_pos, "aging", aging_log_file, sudo=False
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
            else:
                def make_execute(case_name, sr):
                    def execute(context):
                        serial = context.get("serial_client")
                        ssh = context.get("ssh_client")
                        if serial:
                            result = sr.run_serial(serial, case_name)
                        elif ssh:
                            result = sr.run_ssh(ssh, case_name)
                        else:
                            return False
                        return result["result"] == "pass"
                    return execute

                step = TestStep(
                    name=name,
                    label=case["label"],
                    execute=make_execute(name, script_runner),
                    timeout=30,
                    required=True,
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