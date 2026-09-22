"""老化日志解析器

解析 /data/aging.log 的内容，提取：
- 每轮循环的耗时（loop timing）
- 芯片温度变化趋势
- 模块日志过滤
"""
import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 日志行标记正则
RE_LOOP_START = re.compile(r"soc aging test loop (\d+) start")
RE_LOOP_DONE = re.compile(r"aging test loop (\d+) done, use (\d+)")
RE_LOOP_PASS = re.compile(r"soc aging test loop (\d+) pass")
RE_LOOP_FAIL = re.compile(r"soc aging test loop (\d+) fail")
RE_TEMP_LINE = re.compile(r"current time:.*chip temp: (\d+);\s*aging time: (\d+)")
RE_REBOOT_COUNT = re.compile(r"reboot_count (\d+)")
RE_MODULE_PASS = re.compile(r"AGING_PASS_(\w+)")
RE_MODULE_FAIL = re.compile(r"AGING_FAIL_(\w+)")
RE_MODULE_LINE = re.compile(r"(\w+) aging test (\d+) (passed|failed)")


def parse_loop_timing(test_id: str, log_dir: Path) -> dict:
    """解析老化日志中的每轮耗时

    Returns:
        {
            "test_id": str,
            "aging_loops": [{"loop": 1, "duration_sec": 1501, "status": "pass"}, ...],
            "reboot_cycles": 0,
            "total_loops": 2,
            "is_running": bool,
        }
    """
    log_path = log_dir / f"aging_{test_id}.log"
    if not log_path.exists():
        return {
            "test_id": test_id,
            "aging_loops": [],
            "reboot_cycles": 0,
            "total_loops": 0,
            "is_running": False,
        }

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"读取日志文件失败: {e}")
        return {"test_id": test_id, "aging_loops": [], "reboot_cycles": 0,
                "total_loops": 0, "is_running": False}

    loops = {}
    reboot_cycles = 0
    last_loop_start = 0
    # 记录 loop 编号的连续段，用于检测重启（编号重置）
    loop_numbers = []

    for line in content.split("\n"):
        # 匹配 loop start
        m = RE_LOOP_START.search(line)
        if m:
            loop_num = int(m.group(1))
            loop_numbers.append(loop_num)
            if loop_num not in loops:
                loops[loop_num] = {"loop": loop_num, "duration_sec": 0, "status": "running"}
            last_loop_start = loop_num

        # 匹配 loop done（提取耗时）
        m = RE_LOOP_DONE.search(line)
        if m:
            loop_num = int(m.group(1))
            duration = int(m.group(2))
            if loop_num in loops:
                loops[loop_num]["duration_sec"] = duration
            else:
                loops[loop_num] = {"loop": loop_num, "duration_sec": duration, "status": "pass"}

        # 匹配 loop pass
        m = RE_LOOP_PASS.search(line)
        if m:
            loop_num = int(m.group(1))
            if loop_num in loops:
                loops[loop_num]["status"] = "pass"
            else:
                loops[loop_num] = {"loop": loop_num, "duration_sec": 0, "status": "pass"}

        # 匹配 loop fail
        m = RE_LOOP_FAIL.search(line)
        if m:
            loop_num = int(m.group(1))
            if loop_num in loops:
                loops[loop_num]["status"] = "fail"
            else:
                loops[loop_num] = {"loop": loop_num, "duration_sec": 0, "status": "fail"}

        # 匹配 reboot_count
        m = RE_REBOOT_COUNT.search(line)
        if m:
            reboot_cycles = int(m.group(1))

    # 从 loop 编号序列推断重启次数（如果日志中没有 reboot_count 标记）
    if reboot_cycles == 0 and len(loop_numbers) > 1:
        resets = 0
        for i in range(1, len(loop_numbers)):
            if loop_numbers[i] <= loop_numbers[i - 1]:
                resets += 1
        reboot_cycles = resets

    aging_loops = sorted(loops.values(), key=lambda x: x["loop"])
    is_running = any(
        l["status"] == "running" for l in aging_loops
    )

    return {
        "test_id": test_id,
        "aging_loops": aging_loops,
        "reboot_cycles": reboot_cycles,
        "total_loops": len(aging_loops),
        "is_running": is_running,
    }


def parse_temperature(test_id: str, log_dir: Path) -> dict:
    """解析老化日志中的温度数据

    Returns:
        {
            "test_id": str,
            "data": [
                {"time": "2026-09-07T11:50:41", "temp_c": 40.3, "aging_sec": 10},
                ...
            ],
            "max_temp": 46.3,
            "avg_temp": 42.1,
            "count": 200,
        }
    """
    log_path = log_dir / f"aging_{test_id}.log"
    if not log_path.exists():
        return {"test_id": test_id, "data": [], "max_temp": 0, "avg_temp": 0, "count": 0}

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"读取日志文件失败: {e}")
        return {"test_id": test_id, "data": [], "max_temp": 0, "avg_temp": 0, "count": 0}

    data = []
    temps = []

    for line in content.split("\n"):
        m = RE_TEMP_LINE.search(line)
        if m:
            temp_raw = int(m.group(1))
            aging_sec = int(m.group(2))
            temp_c = round(temp_raw / 1000.0, 1)

            # 提取时间戳
            ts_match = re.match(r"\[([^\]]+)\]", line)
            time_str = ts_match.group(1) if ts_match else ""

            data.append({
                "time": time_str,
                "temp_c": temp_c,
                "aging_sec": aging_sec,
            })
            temps.append(temp_c)

    max_temp = round(max(temps), 1) if temps else 0
    avg_temp = round(sum(temps) / len(temps), 1) if temps else 0

    return {
        "test_id": test_id,
        "data": data,
        "max_temp": max_temp,
        "avg_temp": avg_temp,
        "count": len(data),
    }


def filter_module_log(test_id: str, module: str, log_dir: Path) -> dict:
    """从老化日志中过滤指定模块的日志行

    模块名映射（前端传入的 value → 日志中的模块名）:
        cpu, dpu, jpu, tpu, vpss_convertto, vpss_csc, vpu_dec, vpu_enc

    Returns:
        {"test_id": str, "module": str, "lines": [...], "count": int}
    """
    log_path = log_dir / f"aging_{test_id}.log"
    if not log_path.exists():
        return {"test_id": test_id, "module": module, "lines": [], "count": 0}

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"读取日志文件失败: {e}")
        return {"test_id": test_id, "module": module, "lines": [], "count": 0}

    # 模块名关键字（大小写不敏感匹配）
    module_upper = module.upper()
    lines = []

    for line in content.split("\n"):
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # 匹配模块相关行：包含模块名的 PASS/FAIL 行，或模块 aging test 行
        if module_upper in line_stripped.upper():
            lines.append(line_stripped)

    return {
        "test_id": test_id,
        "module": module,
        "lines": lines[-500:],  # 限制返回最近 500 行
        "count": len(lines),
    }