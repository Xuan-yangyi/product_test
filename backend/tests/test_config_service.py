"""ConfigService unit tests"""
import pytest
import sys
from pathlib import Path

web_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(web_dir))


class TestConfigService:
    """ConfigService 配置解析测试"""

    @pytest.fixture
    def cs(self):
        from backend.services.config_service import ConfigService
        return ConfigService()

    def test_get_test_types(self, cs):
        """获取测试类型列表"""
        types = cs.get_test_types()
        assert len(types) >= 5
        type_keys = [t["type"] for t in types]
        assert "se9_interface_test" in type_keys
        assert "se9_aging_test" in type_keys
        assert "evb_interface_test" in type_keys
        assert "evb_aging_test" in type_keys
        assert "se9_mac_check" in type_keys

    def test_test_type_labels(self, cs):
        """测试类型标签正确"""
        types = {t["type"]: t["label"] for t in cs.get_test_types()}
        assert "SE9" in types["se9_interface_test"]
        assert "EVB" in types["evb_interface_test"]
        assert "MAC" in types["se9_mac_check"]

    def test_get_product_models(self, cs):
        """产品型号列表"""
        models = cs.get_product_models()
        assert len(models) >= 2
        model_names = [m["model"] for m in models]
        assert "SE9" in model_names
        assert "EVB" in model_names

    def test_get_test_cases_se9(self, cs):
        """SE9 接口测试用例"""
        cases = cs.get_test_cases("se9_interface_test")
        assert len(cases) >= 20
        case_names = [c["name"] for c in cases]
        assert "chip_type_check" in case_names
        assert "burn_emmc" in case_names
        assert "led_check" in case_names

    def test_get_test_cases_evb(self, cs):
        """EVB 接口测试用例"""
        cases = cs.get_test_cases("evb_interface_test")
        assert len(cases) >= 10
        case_names = [c["name"] for c in cases]
        assert "mcu_uart_check" in case_names
        assert "pcie_check" in case_names

    def test_get_test_cases_aging(self, cs):
        """老化测试用例（SoC_aging_test）"""
        cases = cs.get_test_cases("se9_aging_test")
        assert len(cases) >= 5
        case_names = [c["name"] for c in cases]
        assert "run_aging_test" in case_names

    def test_disabled_cases(self, cs):
        """禁用的测试用例标记正确"""
        cases = cs.get_test_cases("se9_interface_test")
        for c in cases:
            if c["name"] in ("drive_check", "4g_check", "5g_check", "wifi_check", "bluetooth_check"):
                assert c["enabled"] is False, f"{c['name']} should be disabled"

    def test_get_templates(self, cs):
        """模板数据"""
        templates = cs.get_product_templates()
        assert len(templates["test_case_names"]) >= 30
        assert len(templates["test_type_suffixes"]) == 3
        assert len(templates["script_cmd_templates"]) >= 10
        # 验证模板包含脚本命令
        for name, cmd in templates["script_cmd_templates"].items():
            assert "exec_cmd" in cmd
            assert "pass_flag" in cmd
            assert "fail_flag" in cmd

    def test_get_script_cmd_config(self, cs):
        """脚本命令配置（指定测试类型）"""
        cfg = cs.get_script_cmd_config("se9_interface_test")
        assert len(cfg) >= 10
        # 验证关键字段
        for section, items in cfg.items():
            assert "exec_cmd" in items
            assert "pass_flag" in items

    def test_get_fw_version_config(self, cs):
        """固件版本配置"""
        cfg = cs.get_fw_version_config("se9_interface_test")
        assert len(cfg) >= 5  # 至少有多个版本

    def test_validate_product_model(self, cs):
        """产品型号数据校验"""
        # 空数据
        errors = cs._validate_product_model({})
        assert len(errors) > 0

        # 缺少必要字段
        errors = cs._validate_product_model({
            "product_name": "TEST",
            "display_label": "",
            "test_types": [],
        })
        assert len(errors) > 0

        # 完整的有效数据
        errors = cs._validate_product_model({
            "product_name": "TEST",
            "display_label": "TEST测试",
            "test_types": [{
                "type_key": "test_interface_test",
                "label": "TEST 接口测试",
                "category": "test",
                "test_cases": [{
                    "name": "chip_type_check",
                    "enabled": True,
                    "script_cmd": {
                        "exec_cmd": "./test.sh",
                        "pass_flag": "PASS",
                        "fail_flag": "FAIL",
                        "case_timeout": 120,
                    }
                }]
            }]
        })
        assert len(errors) == 0

    def test_validate_invalid_product_name(self, cs):
        """产品名称格式校验"""
        errors = cs._validate_product_model({
            "product_name": "TEST MODEL",
            "display_label": "test",
            "test_types": [{
                "type_key": "test_type",
                "label": "test",
                "category": "test",
                "test_cases": [{
                    "name": "test",
                    "enabled": True,
                    "script_cmd": {
                        "exec_cmd": "./test.sh",
                        "pass_flag": "PASS",
                        "fail_flag": "FAIL",
                        "case_timeout": 120,
                    }
                }]
            }]
        })
        assert len(errors) > 0

    def test_validate_no_enabled_cases(self, cs):
        """没有启用的测试用例"""
        errors = cs._validate_product_model({
            "product_name": "TEST",
            "display_label": "test",
            "test_types": [{
                "type_key": "test_type",
                "label": "test",
                "category": "test",
                "test_cases": []
            }]
        })
        assert len(errors) > 0

    def test_validate_empty_script_cmd(self, cs):
        """脚本命令为空"""
        errors = cs._validate_product_model({
            "product_name": "TEST",
            "display_label": "test",
            "test_types": [{
                "type_key": "test_type",
                "label": "test",
                "category": "test",
                "test_cases": [{
                    "name": "test",
                    "enabled": True,
                    "script_cmd": {
                        "exec_cmd": "",
                        "pass_flag": "",
                        "fail_flag": "",
                        "case_timeout": 120,
                    }
                }]
            }]
        })
        assert len(errors) > 0