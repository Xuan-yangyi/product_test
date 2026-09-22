"""配置管理 API"""
import os
import shutil
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from pydantic import BaseModel
from ..services.config_service import ConfigService
from ..models.schemas import CreateProductModelRequest
from ..config import Config

router = APIRouter(prefix="/api/v1", tags=["config"])


def get_config_service() -> ConfigService:
    return ConfigService()


@router.get("/product-models/templates")
async def get_product_templates(cs: ConfigService = Depends(get_config_service)):
    """获取创建产品型号时可用的模板数据（已知测试用例、脚本命令模板）"""
    return cs.get_product_templates()


@router.post("/product-models")
async def create_product_model(
    req: CreateProductModelRequest,
    cs: ConfigService = Depends(get_config_service),
):
    """创建新的产品型号

    写入 ui_config.ini、test_case_config.ini、script_cmd_cfg.ini 等配置文件。
    所有必填字段校验通过后才执行写入。
    """
    try:
        result = cs.create_product_model(req.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/oem/upload")
async def upload_oem_config(
    file: UploadFile = File(...),
    cs: ConfigService = Depends(get_config_service),
):
    """上传 OEM 配置文件"""
    if not file.filename.endswith((".ini", ".cfg", ".conf")):
        raise HTTPException(status_code=400, detail="仅支持 .ini/.cfg/.conf 文件")

    upload_dir = Config.CFG_DIR / "oem"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = upload_dir / file.filename

    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        return {"filename": file.filename, "path": str(file_path), "status": "uploaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/oem/validate")
async def validate_oem_config(
    file: UploadFile = File(...),
    cs: ConfigService = Depends(get_config_service),
):
    """校验 OEM 配置文件"""
    if not file.filename.endswith((".ini", ".cfg", ".conf")):
        raise HTTPException(status_code=400, detail="仅支持 .ini/.cfg/.conf 文件")

    upload_dir = Config.CFG_DIR / "oem"
    os.makedirs(upload_dir, exist_ok=True)
    tmp_path = upload_dir / f"_tmp_{file.filename}"

    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        result = cs.validate_oem_file(str(tmp_path))
        os.remove(tmp_path)
        return result
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/script-cmd")
async def get_script_cmd_config(cs: ConfigService = Depends(get_config_service)):
    """获取脚本命令配置"""
    return {"config": cs.get_script_cmd_config()}


@router.get("/config/fw-version")
async def get_fw_version_config(cs: ConfigService = Depends(get_config_service)):
    """获取固件版本配置"""
    return {"config": cs.get_fw_version_config()}


@router.get("/config/show")
async def get_show_config(cs: ConfigService = Depends(get_config_service)):
    """获取 UI 显示配置"""
    return {"config": cs.get_show_config()}


# ============================================================
#  Profile 管理
# ============================================================

@router.get("/config/profiles")
async def list_profiles(cs: ConfigService = Depends(get_config_service)):
    """列出所有配置 profile"""
    return {"profiles": cs.list_profiles()}


@router.post("/config/profiles")
async def create_profile(
    name: str = Form(...),
    oem_file: UploadFile = File(...),
    cs: ConfigService = Depends(get_config_service),
):
    """创建新的配置 profile（名称 + OEMconfig.ini 文件）"""
    try:
        content = (await oem_file.read()).decode("utf-8")
        result = cs.create_profile(name, content)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="OEM 文件编码错误，仅支持 UTF-8")


@router.get("/config/profiles/{name}")
async def get_profile(
    name: str,
    cs: ConfigService = Depends(get_config_service),
):
    """获取 profile 详情（含 OEM 文件内容）"""
    try:
        return cs.get_profile(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/config/profiles/{name}/oem")
async def update_profile_oem(
    name: str,
    oem_file: UploadFile = File(...),
    cs: ConfigService = Depends(get_config_service),
):
    """更新 profile 的 OEM 配置文件"""
    try:
        content = (await oem_file.read()).decode("utf-8")
        return cs.update_profile_oem(name, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="OEM 文件编码错误，仅支持 UTF-8")


@router.delete("/config/profiles/{name}")
async def delete_profile(
    name: str,
    cs: ConfigService = Depends(get_config_service),
):
    """删除 profile"""
    try:
        cs.delete_profile(name)
        return {"status": "deleted", "name": name}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class UpdateTestOptionsRequest(BaseModel):
    test_options: dict


@router.put("/config/profiles/{name}/test-options")
async def update_profile_test_options(
    name: str,
    req: UpdateTestOptionsRequest,
    cs: ConfigService = Depends(get_config_service),
):
    """更新 profile 的测试选项"""
    try:
        return cs.update_profile_test_options(name, req.test_options)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
