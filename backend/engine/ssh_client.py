"""SSH 客户端封装（基于 paramiko）"""
import paramiko
import logging
import time
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SSHClient:
    """SSH 客户端

    封装 paramiko 操作，提供：
    - 连接管理：connect(ip, user, password)
    - 命令执行：exec_cmd(cmd, timeout) -> str
    - 设备存活检测：is_ip_alive(ip) -> bool
    """

    def __init__(self):
        self._client: Optional[paramiko.SSHClient] = None
        self._sftp: Optional[paramiko.SFTPClient] = None
        self.ip: str = ""

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.get_transport() is not None \
            and self._client.get_transport().is_active()

    def connect(self, ip: str, user: str = "root", password: str = "", port: int = 22, timeout: int = 10) -> bool:
        """建立 SSH 连接（如果已有连接则先关闭，支持 reconnect）"""
        # 先关闭旧连接（支持 reconnect 场景）
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None

        self.ip = ip
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self._client.connect(ip, port=port, username=user, password=password, timeout=timeout)
            # 启用 keepalive 防止长时传输断连
            transport = self._client.get_transport()
            if transport:
                transport.set_keepalive(30)
            logger.info(f"SSH 连接 {ip} 成功")
            return True
        except Exception as e:
            logger.error(f"SSH 连接 {ip} 失败: {e}")
            self._client = None
            return False

    def exec_cmd(self, cmd: str, timeout: int = 30, sudo: bool = False, sudo_password: str = "") -> tuple:
        """执行命令

        Returns:
            (stdout: str, stderr: str, exit_code: int)
        """
        if not self.is_connected:
            raise RuntimeError(f"SSH 未连接到 {self.ip}")

        if sudo and sudo_password:
            cmd = f"echo '{sudo_password}' | sudo -S {cmd}"

        try:
            stdin, stdout, stderr = self._client.exec_command(cmd, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            return stdout.read().decode(errors="ignore"), stderr.read().decode(errors="ignore"), exit_code
        except Exception as e:
            logger.error(f"SSH 执行命令失败 [{self.ip}]: {e}")
            return "", str(e), -1

    def open_sftp(self) -> Optional[paramiko.SFTPClient]:
        """打开 SFTP 通道"""
        if not self.is_connected:
            return None
        if self._sftp:
            return self._sftp
        self._sftp = self._client.open_sftp()
        return self._sftp

    def pipe_file_to_cmd(self, local_file: str, remote_cmd: str, timeout: int = 600) -> tuple:
        """将本地文件通过 stdin 管道传输到远程命令（不占用磁盘空间）

        用于场景：本地上传 tgz 并通过 tar 解压，无需在设备上存储 tgz 文件。

        Args:
            local_file: 本地文件路径
            remote_cmd: 远程命令（从 stdin 读取数据）
            timeout: 超时时间（秒）

        Returns:
            (stdout: str, stderr: str, exit_code: int)
        """
        if not self.is_connected:
            raise RuntimeError(f"SSH 未连接到 {self.ip}")

        try:
            stdin, stdout, stderr = self._client.exec_command(remote_cmd, timeout=timeout)
            with open(local_file, "rb") as f:
                chunk_size = 1024 * 1024  # 1MB chunks
                total = 0
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    stdin.write(chunk)
                    total += len(chunk)
                    if total % (500 * 1024 * 1024) < chunk_size:
                        logger.info(f"管道传输进度: {total / 1024**2:.0f} MB")
            stdin.close()
            stdin.channel.shutdown_write()
            logger.info(f"管道传输完成: {total / 1024**2:.0f} MB")
            exit_code = stdout.channel.recv_exit_status()
            stdout_str = stdout.read().decode(errors="ignore")
            stderr_str = stderr.read().decode(errors="ignore")
            return stdout_str, stderr_str, exit_code
        except Exception as e:
            logger.error(f"管道传输失败: {e}")
            return "", str(e), -1

    def upload_file(self, local_file: str, remote_file: str) -> bool:
        """通过 SFTP 上传单个文件到远程设备

        Args:
            local_file: 本地文件路径
            remote_file: 远程文件路径

        Returns:
            是否上传成功
        """
        sftp = self.open_sftp()
        if not sftp:
            logger.error("SFTP 通道不可用")
            return False

        try:
            logger.info(f"SFTP 上传单文件: {local_file} -> {remote_file}")
            sftp.put(local_file, remote_file)
            return True
        except Exception as e:
            logger.error(f"SFTP 上传单文件失败: {e}")
            return False

    def upload_directory(self, local_dir: str, remote_dir: str) -> bool:
        """通过 SFTP 上传整个目录到远程设备

        Args:
            local_dir: 本地目录路径
            remote_dir: 远程目录路径

        Returns:
            是否上传成功
        """
        sftp = self.open_sftp()
        if not sftp:
            logger.error("SFTP 通道不可用")
            return False

        local_path = Path(local_dir)
        if not local_path.is_dir():
            logger.error(f"本地目录不存在: {local_dir}")
            return False

        try:
            # 递归创建远程目录并上传文件
            for root, dirs, files in os.walk(str(local_path)):
                rel_root = Path(root).relative_to(local_path)
                remote_root = str(Path(remote_dir) / rel_root) if str(rel_root) != "." else remote_dir

                # 创建远程目录
                try:
                    sftp.stat(remote_root)
                except FileNotFoundError:
                    sftp.mkdir(remote_root)

                for fname in files:
                    local_file = str(Path(root) / fname)
                    remote_file = str(Path(remote_root) / fname)
                    logger.info(f"SFTP 上传: {local_file} -> {remote_file}")
                    sftp.put(local_file, remote_file)

            logger.info(f"目录上传完成: {local_dir} -> {remote_dir}")
            return True
        except Exception as e:
            logger.error(f"SFTP 上传失败: {e}")
            return False

    def exec_cmd_remote(self, cmd: str, timeout: int = 30, sudo: bool = False, sudo_password: str = "") -> tuple:
        """执行远程命令（exec_cmd 的别名，用于 upload 步骤中的后续命令）"""
        return self.exec_cmd(cmd, timeout=timeout, sudo=sudo, sudo_password=sudo_password)

    def close(self):
        """关闭连接"""
        if self._sftp:
            self._sftp.close()
            self._sftp = None
        if self._client:
            self._client.close()
            self._client = None
        logger.info(f"SSH 连接 {self.ip} 已关闭")

    @staticmethod
    def is_ip_alive(ip: str, timeout: int = 3) -> bool:
        """检测 IP 是否可达"""
        import subprocess
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", str(timeout), ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return result.returncode == 0
        except Exception:
            return False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
