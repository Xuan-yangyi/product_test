"""调机预览中继接口

产测网页的「调机预览」页通过这里拿板子上的双路实时画面。

为什么要在 .57 上中继一跳，而不是让浏览器直连板子：
  * 浏览器直连板子的 :8090 需要额外开跨域，且板子网段对办公网不直接暴露，
    每换一台调机电脑都要改一次配置 —— 不通用。
  * 中继后浏览器只跟 .57 说同源的话（/api/v1/camera/*），换电脑零配置。
  * 本机 HTTP 一跳 <1ms，相对板子上 4K 硬件编码的 ~55ms 可忽略。

本模块**只做转发，不落库、不写文件、不碰 sn_results**（REQ-006）。

板子侧对应服务：
  * V3.0（当前）：预览内嵌在 sn_monitor.py 里，由 sn_preview_embed.py 提供 :8090，
    与 SN 识别**同进程共享同一路解码** —— 相机源仍只被占用一次。起停走 sn-monitor.service。
  * V1/V2（已停用）：preview_service.py 独立进程，靠 systemd Conflicts= 与识别互斥。
    脚本保留可手动起，但不部署。
若板子侧没起服务，这里会返回 503 并带上提示，不会把 500 抛给浏览器。
"""

import logging
from typing import Optional

import anyio
import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/camera", tags=["camera"])

# 板子预览服务地址。换板子/换端口时改这一个常量，或设环境变量覆盖。
import os
BOARD_BASE = os.environ.get("PREVIEW_BOARD_BASE", "http://10.80.40.68:8090")

# MJPEG 是长连接：读超时必须关掉（None），否则 httpx 到点会自己掐断，
# 表现就是网页画面每隔几秒黑一下。
_STREAM_TIMEOUT = httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0)
# 控制类接口（status/resolution/snapshot）都是短请求，给正常超时
_SHORT_TIMEOUT = httpx.Timeout(connect=3.0, read=8.0, write=5.0, pool=5.0)

VALID_CAMS = ("front", "back")
VALID_RES = ("4k", "1080p", "720p", "360p")


def _board_get(path: str, params: dict, timeout):
    """向板子发 GET。板子没起服务 / 网络不通时统一转成 503，别把底噪当 500。"""
    url = BOARD_BASE.rstrip("/") + path
    try:
        return httpx.get(url, params=params, timeout=timeout)
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=503,
            detail=f"板子预览服务未启动或不可达（{BOARD_BASE}）。"
                   f"V3.0 预览内嵌在识别服务里，请在板子上执行：sudo systemctl start sn-monitor-big",
        ) from e
    except httpx.TimeoutException as e:
        raise HTTPException(status_code=504,
                            detail=f"板子预览服务响应超时（{BOARD_BASE}）") from e


@router.get("/stream")
async def camera_stream(
    request: Request,
    cam: str = Query("front", description="front=正面(1.9) / back=背面(1.8)"),
    res: Optional[str] = Query(None, description="4k|1080p|720p|360p，默认 4k"),
):
    """MJPEG 流转发。网页端直接 <img src="/api/v1/camera/stream?cam=front">。

    ★ 本函数与 relay() 必须是 async（BUG-001）：
      同步版会把上游连接泄漏在 .57 上，几十次前端重连就能把服务器拖死。
      机理与实测数据见 relay() 的注释。
    """
    if cam not in VALID_CAMS:
        raise HTTPException(status_code=400,
                            detail=f"cam 必须是 {VALID_CAMS} 之一")
    if res is not None and res not in VALID_RES:
        raise HTTPException(status_code=400,
                            detail=f"res 必须是 {VALID_RES} 之一")

    params = {"cam": cam}
    if res:
        params["res"] = res

    client = httpx.AsyncClient(timeout=_STREAM_TIMEOUT)
    try:
        upstream = await client.send(
            client.build_request("GET", BOARD_BASE.rstrip("/") + "/stream",
                                 params=params),
            stream=True,
        )
    except httpx.ConnectError as e:
        await client.aclose()
        raise HTTPException(
            status_code=503,
            detail=f"板子预览服务未启动或不可达（{BOARD_BASE}）。"
                   f"V3.0 预览内嵌在识别服务里，请在板子上执行：sudo systemctl start sn-monitor-big",
        ) from e
    except httpx.TimeoutException as e:
        await client.aclose()
        raise HTTPException(status_code=504, detail="板子预览服务连接超时") from e

    if upstream.status_code != 200:
        body = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(
            status_code=upstream.status_code,
            detail=f"板子返回 {upstream.status_code}: {body[:200].decode('utf-8', 'replace')}",
        )

    ctype = upstream.headers.get("content-type", "multipart/x-mixed-replace")

    async def relay():
        """逐块转发。

        为什么**必须**是 async 生成器（BUG-001，2026-09-16）：
          写成同步生成器时，StreamingResponse 会用 iterate_in_threadpool 驱动它，
          即把 next() 丢进 anyio 工作线程执行。anyio 3 的 to_thread.run_sync 默认
          cancellable=False —— 浏览器断开触发的那次取消，**要等那个线程自己返回**才落地；
          而线程此刻正阻塞在 read=None 的无限 socket 读上，永远不返回。
          结果：取消被无限期推迟，finally 永不执行，上游 TCP 连接与 httpx 客户端
          双双泄漏在 .57 上。板子侧表现为一堆只写不读的连接（send-q 持续积压）。

        实测（10 轮「每路拉 2s 后断开」，模拟刷新/切档）：
          板子 :8090 连接 0 → 26 条（积压 38.5MB，一条不释放）；
          .57 FD 38 → 64（与板子 26 条 1:1）、RSS 234 → 293MB；
          干净 close() 后 30s 连接仍 ESTAB，证明对端 FD 确实还开着。
          崩溃现场 `.57` 曾有 17 条这样的 4K 连接（单路 84Mbps），
          随后内核报 soft lockup（libuv-worker 卡死 22s），服务器失联。

        改 async 后，取消能在 await 点立刻投递，finally 才会真的跑。
        """
        _relay_bytes = 0
        _RELAY_MAX_BYTES = 60_000_000
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
                _relay_bytes += len(chunk)
                if _relay_bytes > _RELAY_MAX_BYTES:
                    break
        except httpx.HTTPError as e:  # 上游中断不该污染日志栈
            logger.warning("预览流中断 cam=%s: %s", cam, e)
        finally:
            # ★ 必须 shield：取消已在进行中时，裸 await 会被立刻打断，
            #   变成「看起来关了其实没关」—— 正是要修的那个泄漏。
            #   shield 保证这两次关闭无论如何都执行完。
            with anyio.CancelScope(shield=True):
                await upstream.aclose()
                await client.aclose()

    return StreamingResponse(
        relay(),
        media_type=ctype,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            # 反代（若将来加 nginx）别缓冲 MJPEG
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/snapshot")
def camera_snapshot(
    cam: str = Query("front"),
    res: Optional[str] = Query(None),
):
    """单张抓拍。MJPEG 放不出来时的兜底（网页端可退到定时刷新）。"""
    if cam not in VALID_CAMS:
        raise HTTPException(status_code=400, detail=f"cam 必须是 {VALID_CAMS} 之一")
    params = {"cam": cam}
    if res:
        params["res"] = res
    r = _board_get("/snapshot", params, _SHORT_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code,
                            detail=f"板子返回 {r.status_code}")
    return Response(content=r.content, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@router.get("/status")
def camera_status():
    """两路相机的连接状态。前端用它显示「正面已连接 / 背面重连中」。"""
    r = _board_get("/status", {}, _SHORT_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail="板子返回异常")
    return r.json()


@router.get("/resolution")
def camera_resolution(res: str = Query(..., description="4k|1080p|720p|360p")):
    """切换分辨率档位。网页下拉框变化时调用。"""
    if res not in VALID_RES:
        raise HTTPException(status_code=400, detail=f"res 必须是 {VALID_RES} 之一")
    r = _board_get("/resolution", {"res": res}, _SHORT_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail="档位切换失败")
    return r.json()


@router.get("/latest-capture")
def camera_latest_capture():
    """调机页回显：板子上刚抓到的那张 SN 图 + 元数据。

    ★ 只读代理，不写库。产测页「SN 抓拍」看到的仍是 uploader 正式上传后的记录
    （约 5s 延迟），本接口既不加快也不改变那条链路。
    板子上还没有抓拍图时返回 has=false（正常空态，不是错误）。
    """
    r = _board_get("/latest_capture", {}, _SHORT_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail="读取板子最新抓拍失败")
    data = r.json()
    # 把板子返回的相对图地址换成经本服务的代理地址，浏览器才能直接访问
    if data.get("has"):
        data["image"] = "/api/v1/camera/latest-capture/image"
    return data


@router.get("/latest-capture/image")
def camera_latest_capture_image():
    """回显图本体。直通转发板子的 JPEG 字节，不做解码/缩放（纯搬运最省事）。"""
    client = httpx.Client(timeout=_SHORT_TIMEOUT)
    try:
        upstream = client.get(BOARD_BASE.rstrip("/") + "/latest_capture/image")
    except httpx.ConnectError as e:
        client.close()
        raise HTTPException(status_code=503, detail="板子预览服务不可达") from e
    except httpx.TimeoutException as e:
        client.close()
        raise HTTPException(status_code=504, detail="板子响应超时") from e
    try:
        if upstream.status_code != 200:
            raise HTTPException(status_code=upstream.status_code,
                                detail="板上暂无抓拍图")
        return Response(
            content=upstream.content,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store",
                     "X-SN": upstream.headers.get("X-SN", "")},
        )
    finally:
        client.close()

# ============================================================
# V4.0 WebRTC preview endpoints (WHEP proxy)
# ============================================================

WEBRTC_BOARD = os.environ.get("WEBRTC_BOARD_BASE", "http://127.0.0.1:8889")

@router.get("/webrtc/config")
def webrtc_config():
    return {
        "boardUrl": WEBRTC_BOARD,
        "cams": ["front", "back"],
        "iceUdpPort": 8189,
        "mode": "whep",
    }

@router.api_route("/webrtc/whep/{cam}", methods=["POST", "OPTIONS"])
async def webrtc_whep(cam: str, request: Request):
    if cam not in ("cam_front", "cam_back"):
        raise HTTPException(status_code=400, detail=f"unknown cam: {cam}")
    sdp_offer = await request.body()
    if not sdp_offer:
        raise HTTPException(status_code=400, detail="empty SDP offer")
    async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0)) as client:
        try:
            resp = await client.post(
                f"{WEBRTC_BOARD}/{cam}/whep",
                content=sdp_offer,
                headers={"Content-Type": "application/sdp"},
            )
            return Response(
                content=resp.content,
                media_type=resp.headers.get("content-type", "application/sdp"),
                status_code=resp.status_code,
            )
        except httpx.ConnectError as e:
            raise HTTPException(status_code=503, detail="MediaMTX board unreachable") from e
