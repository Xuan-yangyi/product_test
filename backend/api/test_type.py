"""测试类型 API"""
from fastapi import APIRouter, Depends
from ..services.config_service import ConfigService

router = APIRouter(prefix="/api/v1", tags=["test-types"])


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
