"""SCP 文件传输封装（基于 pexpect）"""
import pexpect
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class SCPClient:
    """SCP 文件传输客户端

    封装 pexpect 的 SCP 操作，用于将测试脚本上传到设备
    """

    @staticmethod
    def upload(local_path: str, remote_path: str, ip: str,
               user: str = "root", password: str = "", timeout: int = 60) -> bool:
        """上传文件到远程设备

        Args:
            local_path: 本地文件路径
            remote_path: 远程目标路径
            ip: 目标 IP
            user: 用户名
            password: 密码
            timeout: 超时时间

        Returns:
            是否成功
        """
        if not os.path.exists(local_path):
            logger.error(f"本地文件不存在: {local_path}")
            return False

        remote = f"{user}@{ip}:{remote_path}"
        cmd = f"scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {local_path} {remote}"

        try:
            child = pexpect.spawn(cmd, timeout=timeout)
            index = child.expect([
                "password:", "yes/no", pexpect.EOF, pexpect.TIMEOUT
            ], timeout=15)

            if index == 1:  # "yes/no"
                child.sendline("yes")
                child.expect("password:", timeout=10)
                child.sendline(password)
            elif index == 0:  # "password:"
                child.sendline(password)

            child.expect(pexpect.EOF, timeout=timeout)
            child.close()

            if child.exitstatus == 0:
                logger.info(f"SCP 上传成功: {local_path} -> {remote}")
                return True
            else:
                logger.error(f"SCP 上传失败, exit={child.exitstatus}")
                return False
        except pexpect.TIMEOUT:
            logger.error(f"SCP 上传超时: {local_path} -> {remote}")
            return False
        except Exception as e:
            logger.error(f"SCP 上传异常: {e}")
            return False

    @staticmethod
    def download(remote_path: str, local_path: str, ip: str,
                 user: str = "root", password: str = "", timeout: int = 60) -> bool:
        """从远程设备下载文件"""
        remote = f"{user}@{ip}:{remote_path}"
        cmd = f"scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {remote} {local_path}"

        try:
            child = pexpect.spawn(cmd, timeout=timeout)
            index = child.expect([
                "password:", "yes/no", pexpect.EOF, pexpect.TIMEOUT
            ], timeout=15)

            if index == 1:
                child.sendline("yes")
                child.expect("password:", timeout=10)
                child.sendline(password)
            elif index == 0:
                child.sendline(password)

            child.expect(pexpect.EOF, timeout=timeout)
            child.close()
            return child.exitstatus == 0
        except Exception as e:
            logger.error(f"SCP 下载异常: {e}")
            return False
