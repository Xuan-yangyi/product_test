"""测试类型 API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..services.config_service import ConfigService

router = APIRouter(prefix="/api/v1", tags=["test-types"])


class UpdateCaseRequest(BaseModel):
    enabled: bool


def get_config_service() -> ConfigService:
    """依赖注入：ConfigService"""
    return ConfigService()


@router.get("/test-types")
async def get_test_types(cs: ConfigService = Depends(get_config_service)):
    """获取可用测试类型列表"""
    return {"types": cs.get_test_types()}


@router.get("/test-types/{test_type}/cases")
async def get_test_cases(test_type: str, cs: ConfigService = Depends(get_config_service)):
    """获取指定测试类型的用例列表"""
    return {"cases": cs.get_test_cases(test_type)}


@router.get("/product-models")
async def get_product_models(cs: ConfigService = Depends(get_config_service)):
    """获取产品型号列表"""
    return {"models": cs.get_product_models()}


@router.get("/test-types/{test_type}/show-config")
async def get_show_config(test_type: str, cs: ConfigService = Depends(get_config_service)):
    """获取 UI 控件显示配置"""
    config = cs.get_show_config()
    return {"config": config.get(test_type, {})}


@router.put("/test-types/{test_type}/cases/{case_name}")
async def update_test_case(
    test_type: str,
    case_name: str,
    req: UpdateCaseRequest,
    cs: ConfigService = Depends(get_config_service),
):
    """更新测试用例的启用/禁用状态"""
    try:
        result = cs.update_test_case_enabled(test_type, case_name, req.enabled)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
