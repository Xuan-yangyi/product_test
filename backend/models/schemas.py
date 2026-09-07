"""Pydantic 请求/响应模型"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TestStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    stopped = "stopped"


class StepResult(str, Enum):
    pass_ = "pass"
    fail = "fail"
    skip = "skip"
    running = "running"
    pending = "pending"


# === 测试类型 ===
class TestTypeInfo(BaseModel):
    type: str
    label: str
    description: str
    requires_serial: bool = True
    requires_network: bool = False

class TestCaseItem(BaseModel):
    name: str
    label: str
    enabled: bool
    timeout: int
    pass_flag: Optional[str] = None
    fail_flag: Optional[str] = None


# === 测试执行 ===
class TestRunRequest(BaseModel):
    test_type: str = Field(..., description="测试类型")
    product_model: str = Field(..., description="产品型号")
    serial_port: Optional[str] = Field(None, description="串口设备")
    device_ip: Optional[str] = Field(None, description="设备 IP")
    device_count: int = Field(1, description="设备数量")
    params: dict = Field(default_factory=dict, description="额外参数")

class TestRunResponse(BaseModel):
    test_id: str
    status: TestStatus
    created_at: datetime

class TestInfo(BaseModel):
    test_id: str
    test_type: str
    status: TestStatus
    product_model: str
    serial_port: Optional[str]
    device_ip: Optional[str]
    created_at: datetime
    current_step: int = 0
    total_steps: int = 0
    steps: List[dict] = Field(default_factory=list)

class TestStepResult(BaseModel):
    step_index: int
    step_name: str
    step_label: str
    result: StepResult
    duration_ms: int
    message: str

class TestLog(BaseModel):
    timestamp: datetime
    level: str  # INFO, WARN, ERROR, DEBUG
    source: str  # step name
    message: str


# === 交互 ===
class InteractionRequest(BaseModel):
    step_name: str
    message: str
    dialog_type: str = "confirm"  # info, confirm, input
    timeout: int = 300
    options: Optional[List[str]] = None

class InteractionResponse(BaseModel):
    action: str  # confirm, cancel, skip, input
    value: Optional[str] = None


# === 设备 ===
# === 集群老化 ===
class ClusterDevice(BaseModel):
    ip: str = Field(..., description="设备 IP")
    params: dict = Field(default_factory=dict, description="设备参数（loop, reboot等）")


class ClusterTestRequest(BaseModel):
    test_type: str = Field("se9_aging_test", description="测试类型")
    product_model: str = Field(..., description="产品型号")
    devices: List[ClusterDevice] = Field(..., description="设备列表")
    write_oem: bool = Field(False, description="是否写入OEM信息")


class ClusterTestResponse(BaseModel):
    cluster_id: str
    status: str
    sub_tests: List[dict]
    created_at: str


class SerialDevice(BaseModel):
    port: str
    device_type: str
    in_use: bool = False

class NetworkDevice(BaseModel):
    ip: str
    hostname: str = ""
    status: str = "online"
    device_type: str = ""


# === 配置 ===
class OEMUploadRequest(BaseModel):
    product_model: str
    file_content: bytes

class OEMValidateResponse(BaseModel):
    valid: bool
    product_model: Optional[str] = None
    message: str = ""


# === 结果 ===
class TestResultSummary(BaseModel):
    test_id: str
    test_type: str
    product_model: str
    serial_number: Optional[str]
    status: TestStatus
    total_steps: int
    passed: int
    failed: int
    skipped: int
    duration_seconds: float
    created_at: datetime

class ResultQuery(BaseModel):
    serial_number: Optional[str] = None
    test_type: Optional[str] = None
    status: Optional[TestStatus] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    page: int = 1
    page_size: int = 20


# === WebSocket 消息 ===
class WSMessage(BaseModel):
    type: str  # log, step_update, status_change, interaction_request
    data: dict


# === 产品型号创建 ===
class ScriptCmdSchema(BaseModel):
    exec_cmd: str = Field(..., min_length=1, description="执行命令")
    pass_flag: str = Field(..., min_length=1, description="通过标志")
    fail_flag: str = Field(..., min_length=1, description="失败标志")
    case_timeout: int = Field(default=120, description="超时时间(秒)")


class TestCaseSchema(BaseModel):
    name: str = Field(..., min_length=1, description="用例名称")
    enabled: bool = Field(default=True, description="是否启用")
    script_cmd: Optional[ScriptCmdSchema] = Field(default=None, description="脚本命令")


class TestTypeSchema(BaseModel):
    type_key: str = Field(..., min_length=1, description="测试类型 key")
    label: str = Field(..., min_length=1, description="测试类型标签")
    category: str = Field(default="test", description="分类: test 或 other")
    test_cases: List[TestCaseSchema] = Field(default_factory=list, description="测试用例列表")


class CreateProductModelRequest(BaseModel):
    product_name: str = Field(..., min_length=1, pattern=r'^[A-Za-z0-9_]+$', description="产品名称")
    display_label: str = Field(..., min_length=1, description="显示标签")
    test_types: List[TestTypeSchema] = Field(..., min_length=1, description="测试类型列表")
