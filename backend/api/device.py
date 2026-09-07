"""设备管理 API"""
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List
from ..services.device_manager import DeviceManager
from ..services.resource_pool import ResourcePool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["devices"])


class ScanRequest(BaseModel):
    ips: List[str]


def get_device_manager() -> DeviceManager:
    return DeviceManager()


def get_resource_pool() -> ResourcePool:
    return ResourcePool()


@router.get("/devices/serials")
async def scan_serial_devices(dm: DeviceManager = Depends(get_device_manager)):
    """扫描串口设备"""
    devices = dm.scan_serial_devices()
    return {"devices": devices}


@router.post("/devices/network/scan")
async def batch_scan_ips(req: ScanRequest, dm: DeviceManager = Depends(get_device_manager)):
    """批量扫描 IP 地址，检测在线设备"""
    devices = dm.batch_scan_ips(req.ips)
    return {"devices": devices}


@router.get("/devices/network")
async def scan_network_devices(dm: DeviceManager = Depends(get_device_manager)):
    """扫描网络设备"""
    devices = dm.scan_network_devices()
    return {"devices": devices}


@router.get("/devices/network/{ip}/info")
async def get_device_info(ip: str, dm: DeviceManager = Depends(get_device_manager)):
    """获取设备详细信息"""
    info = dm.get_device_info_via_ssh(ip)
    return {"device": info}


@router.get("/resource-pool/status")
async def get_resource_status(rp: ResourcePool = Depends(get_resource_pool)):
    """获取资源池使用状态"""
    return rp.get_usage_status()
