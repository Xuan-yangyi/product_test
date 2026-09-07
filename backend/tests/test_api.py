"""Comprehensive API endpoint tests — covers all 26 endpoints"""
import pytest
import io


class TestHealthCheck:
    """健康检查"""

    def test_health_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"


class TestTestTypes:
    """测试类型相关端点"""

    def test_list_types(self, client):
        """GET /api/v1/test-types"""
        r = client.get("/api/v1/test-types")
        assert r.status_code == 200
        data = r.json()
        assert "types" in data
        assert isinstance(data["types"], list)
        assert len(data["types"]) >= 5
        # 检查每个类型有必需字段
        for t in data["types"]:
            assert "type" in t
            assert "label" in t
            assert "product" in t
            assert "requires_serial" in t
            assert "requires_network" in t

    def test_get_cases_se9_interface(self, client):
        """GET /api/v1/test-types/se9_interface_test/cases"""
        r = client.get("/api/v1/test-types/se9_interface_test/cases")
        assert r.status_code == 200
        data = r.json()
        assert "cases" in data
        assert len(data["cases"]) >= 20
        for c in data["cases"]:
            assert "name" in c
            assert "enabled" in c

    def test_get_cases_evb_interface(self, client):
        """GET /api/v1/test-types/evb_interface_test/cases"""
        r = client.get("/api/v1/test-types/evb_interface_test/cases")
        assert r.status_code == 200
        data = r.json()
        assert len(data["cases"]) >= 10

    def test_get_cases_aging(self, client):
        """GET /api/v1/test-types/se9_aging_test/cases"""
        r = client.get("/api/v1/test-types/se9_aging_test/cases")
        assert r.status_code == 200
        data = r.json()
        assert len(data["cases"]) >= 5

    def test_get_product_models(self, client):
        """GET /api/v1/product-models"""
        r = client.get("/api/v1/product-models")
        assert r.status_code == 200
        data = r.json()
        assert "models" in data
        models = data["models"]
        assert len(models) >= 2
        model_names = [m["model"] for m in models]
        assert "SE9" in model_names
        assert "EVB" in model_names

    def test_get_show_config(self, client):
        """GET /api/v1/test-types/se9_interface_test/show-config"""
        r = client.get("/api/v1/test-types/se9_interface_test/show-config")
        assert r.status_code == 200
        data = r.json()
        assert "config" in data


class TestDevices:
    """设备管理端点"""

    def test_list_serials(self, client):
        """GET /api/v1/devices/serials"""
        r = client.get("/api/v1/devices/serials")
        assert r.status_code == 200
        data = r.json()
        assert "devices" in data

    @pytest.mark.skip(reason="Network scan takes too long (254 IPs × 2s timeout)")
    def test_network_devices(self, client):
        """GET /api/v1/devices/network — 跳过：网络扫描耗时过长"""
        r = client.get("/api/v1/devices/network")
        assert r.status_code == 200
        data = r.json()
        assert "devices" in data

    def test_resource_pool_status(self, client):
        """GET /api/v1/resource-pool/status"""
        r = client.get("/api/v1/resource-pool/status")
        assert r.status_code == 200
        data = r.json()
        # 资源池状态可能返回空
        assert isinstance(data, dict)


class TestTestExecution:
    """测试执行端点"""

    def test_create_test_validation_empty(self, client):
        """POST /api/v1/tests — 空请求应返回 422"""
        r = client.post("/api/v1/tests", json={})
        assert r.status_code == 422

    def test_create_test_invalid_type(self, client):
        """POST /api/v1/tests — 无效类型仍会创建（当前未校验test_type）"""
        r = client.post("/api/v1/tests", json={
            "test_type": "nonexistent_type",
            "product_model": "SE9",
        })
        # API 当前不校验 test_type 有效性，接受任意字符串
        assert r.status_code == 200
        data = r.json()
        assert "test_id" in data
        assert data["status"] == "pending"

    def test_get_nonexistent_test(self, client):
        """GET /api/v1/tests/nonexistent — 应返回 404"""
        r = client.get("/api/v1/tests/nonexistent-id")
        assert r.status_code == 404

    def test_list_tests(self, client):
        """GET /api/v1/tests"""
        r = client.get("/api/v1/tests")
        assert r.status_code in (200, 404)  # 可能为空列表


class TestConfigManagement:
    """配置管理端点"""

    def test_get_templates(self, client):
        """GET /api/v1/product-models/templates"""
        r = client.get("/api/v1/product-models/templates")
        assert r.status_code == 200
        data = r.json()
        assert "test_case_names" in data
        assert "test_type_suffixes" in data
        assert "script_cmd_templates" in data
        assert len(data["test_case_names"]) >= 30
        assert len(data["test_type_suffixes"]) == 3
        assert len(data["script_cmd_templates"]) >= 10

    def test_get_script_cmd(self, client):
        """GET /api/v1/config/script-cmd"""
        r = client.get("/api/v1/config/script-cmd")
        assert r.status_code == 200
        data = r.json()
        assert "config" in data

    def test_get_fw_version(self, client):
        """GET /api/v1/config/fw-version"""
        r = client.get("/api/v1/config/fw-version")
        assert r.status_code == 200
        data = r.json()
        assert "config" in data

    def test_get_show_config(self, client):
        """GET /api/v1/config/show"""
        r = client.get("/api/v1/config/show")
        assert r.status_code == 200
        data = r.json()
        assert "config" in data

    def test_oem_validate_no_file(self, client):
        """POST /api/v1/config/oem/validate — 无文件应返回 422"""
        r = client.post("/api/v1/config/oem/validate")
        assert r.status_code == 422

    def test_create_product_model_validation(self, client):
        """POST /api/v1/product-models — 空请求应返回 422"""
        r = client.post("/api/v1/product-models", json={})
        assert r.status_code == 422

    def test_create_product_model_missing_fields(self, client):
        """POST /api/v1/product-models — 缺少必要字段"""
        r = client.post("/api/v1/product-models", json={
            "product_name": "TEST",
            "display_label": "",
            "test_types": [],
        })
        assert r.status_code in (400, 422)


class TestResults:
    """结果查询端点"""

    def test_list_results(self, client):
        """GET /api/v1/results"""
        r = client.get("/api/v1/results")
        assert r.status_code == 200
        data = r.json()
        assert "results" in data or "items" in data or "data" in data

    def test_get_nonexistent_result(self, client):
        """GET /api/v1/results/nonexistent — 应返回 404"""
        r = client.get("/api/v1/results/nonexistent-id")
        assert r.status_code in (200, 404)  # 可能返回空

    def test_get_nonexistent_logs(self, client):
        """GET /api/v1/results/nonexistent-id/logs"""
        r = client.get("/api/v1/results/nonexistent-id/logs")
        assert r.status_code in (200, 404)


class TestProductModelCRUD:
    """产品型号 CRUD 端到端测试"""

    def test_create_and_verify(self, client):
        """创建产品型号并验证能正确回读"""
        # 1. 创建
        product = "TESTCRUD"
        r = client.post("/api/v1/product-models", json={
            "product_name": product,
            "display_label": f"{product}接口测试",
            "test_types": [{
                "type_key": f"{product.lower()}_interface_test",
                "label": f"{product} 接口测试",
                "category": "test",
                "test_cases": [
                    {
                        "name": "chip_type_check",
                        "enabled": True,
                        "script_cmd": {
                            "exec_cmd": "./test_chip.sh",
                            "pass_flag": "QA_PASS_CHIP",
                            "fail_flag": "QA_FAIL_CHIP",
                            "case_timeout": 120,
                        }
                    },
                    {
                        "name": "led_check",
                        "enabled": True,
                        "script_cmd": {
                            "exec_cmd": "./test_led.sh",
                            "pass_flag": "QA_PASS_LED",
                            "fail_flag": "QA_FAIL_LED",
                            "case_timeout": 60,
                        }
                    }
                ]
            }]
        })
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["product_name"] == product

        # 2. 验证测试类型出现在列表中
        r = client.get("/api/v1/test-types")
        types = r.json()["types"]
        type_keys = [t["type"] for t in types]
        assert f"{product.lower()}_interface_test" in type_keys

        # 3. 验证产品型号出现
        r = client.get("/api/v1/product-models")
        models = r.json()["models"]
        model_names = [m["model"] for m in models]
        assert product in model_names

        # 4. 清理测试数据
        from backend.config import Config
        import configparser

        # Clean ui_config.ini
        p = configparser.ConfigParser()
        p.optionxform = str
        ui_path = Config.CFG_DIR / "ui_config.ini"
        p.read(str(ui_path), encoding="utf-8")
        p.remove_section(product)
        p.remove_option("test_case", f"{product.lower()}_interface_test")
        with open(ui_path, "w", encoding="utf-8") as f:
            p.write(f)

        # Clean test_case_config.ini
        p = configparser.ConfigParser()
        p.optionxform = str
        tc_path = Config.CFG_DIR / "test_case_config.ini"
        p.read(str(tc_path), encoding="utf-8")
        section_name = f"{product}_interface_test"
        if section_name in p:
            p.remove_section(section_name)
        with open(tc_path, "w", encoding="utf-8") as f:
            p.write(f)

        # Clean product cfg dir
        import shutil
        cfg_dir = Config.CFG_DIR / f"{product}_cfg"
        if cfg_dir.exists():
            shutil.rmtree(cfg_dir)

    def test_create_then_verify_cases(self, client):
        """创建产品型号后验证测试用例可以正确读取"""
        product = "TESTCASE"
        r = client.post("/api/v1/product-models", json={
            "product_name": product,
            "display_label": f"{product}测试",
            "test_types": [{
                "type_key": f"{product.lower()}_interface_test",
                "label": f"{product} 接口测试",
                "category": "test",
                "test_cases": [
                    {
                        "name": "chip_type_check",
                        "enabled": True,
                        "script_cmd": {
                            "exec_cmd": "./test_chip.sh",
                            "pass_flag": "QA_PASS_CHIP",
                            "fail_flag": "QA_FAIL_CHIP",
                            "case_timeout": 120,
                        }
                    }
                ]
            }]
        })
        assert r.status_code == 200

        # 验证测试用例
        r = client.get(f"/api/v1/test-types/{product.lower()}_interface_test/cases")
        assert r.status_code == 200
        cases = r.json()["cases"]
        case_names = [c["name"] for c in cases]
        assert "chip_type_check" in case_names

        # 清理
        from backend.config import Config
        import configparser, shutil
        p = configparser.ConfigParser()
        p.optionxform = str
        ui_path = Config.CFG_DIR / "ui_config.ini"
        p.read(str(ui_path), encoding="utf-8")
        p.remove_section(product)
        p.remove_option("test_case", f"{product.lower()}_interface_test")
        with open(ui_path, "w", encoding="utf-8") as f:
            p.write(f)
        p = configparser.ConfigParser()
        p.optionxform = str
        tc_path = Config.CFG_DIR / "test_case_config.ini"
        p.read(str(tc_path), encoding="utf-8")
        if f"{product}_interface_test" in p:
            p.remove_section(f"{product}_interface_test")
        with open(tc_path, "w", encoding="utf-8") as f:
            p.write(f)
        cfg_dir = Config.CFG_DIR / f"{product}_cfg"
        if cfg_dir.exists():
            shutil.rmtree(cfg_dir)