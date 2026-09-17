"""转换工作线程：后台执行 ffmpeg，实时上报进度，支持取消。"""

import os
import subprocess
import tempfile

from PySide6.QtCore import QThread, Signal

import ffmpeg_pipeline as ff


class ConvertWorker(QThread):
    progress = Signal(int)       # 0..100
    succeeded = Signal(str)      # 输出文件路径
    failed = Signal(str)         # 错误信息

    def __init__(self, src, dst, fmt, codec, duration,
                 scale=None, fps=None, abitrate=None, parent=None):
        super().__init__(parent)
        self.src = src
        self.dst = dst
        self.fmt = fmt
        self.codec = codec
        self.duration = duration
        self.scale = scale
        self.fps = fps
        self.abitrate = abitrate
        self._proc = None
        self._canceled = False

    def cancel(self):
        self._canceled = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    @staticmethod
    def _parse_time(raw, factor_us):
        """解析 ffmpeg 进度时间；N/A / 浮点 / 异常值一律安全返回 None。"""
        if not raw or raw == "N/A":
            return None
        try:
            return float(raw) * factor_us
        except ValueError:
            return None

    @staticmethod
    def _short_err(err):
        """从 stderr 提取最有信息量的一行错误：优先含 error 的行，否则末行。"""
        lines = [ln.strip() for ln in err.splitlines() if ln.strip()]
        if not lines:
            return ""
        hit = next((ln for ln in lines if "rror" in ln), None)
        return hit or lines[-1]

    def run(self):
        cmd = [ff.ffmpeg_exe(), "-y", "-progress", "pipe:1", "-nostats"] \
            + ff.build_convert_args(self.src, self.dst, self.fmt, self.codec,
                                    self.scale, self.fps, self.abitrate)

        # stderr 写入临时文件而非管道，避免管道塞满导致与 stdout 相互阻塞
        err_f = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=err_f,
                text=True, encoding="utf-8", errors="replace",
                creationflags=ff.CREATE_NO_WINDOW,
            )
        except FileNotFoundError:
            err_f.close()
            self.failed.emit("找不到 ffmpeg 可执行文件")
            return

        total_us = (self.duration * 1_000_000) if self.duration else None
        try:
            for line in self._proc.stdout:
                if self._canceled:
                    break
                line = line.strip()
                us = None
                if line.startswith("out_time_us="):
                    us = self._parse_time(line.split("=", 1)[1], 1)
                elif line.startswith("out_time_ms="):
                    us = self._parse_time(line.split("=", 1)[1], 1000)
                if us is not None and total_us:
                    # 编码中封顶 99：慢编码（VP9）音频先写完会让上报时间提前到
                    # 总时长，导致进度虚满。100% 只由成功信号（else 分支）给出。
                    self.progress.emit(min(99, int(us * 100 / total_us)))
        finally:
            self._proc.wait()

        err_f.seek(0)
        err = err_f.read()
        err_f.close()

        if self._canceled:
            # 清理未完成的残留输出，不留半截文件
            try:
                os.remove(self.dst)
            except OSError:
                pass
            self.failed.emit("已取消")
        elif self._proc.returncode != 0:
            self.failed.emit(self._short_err(err) or "转换失败")
        else:
            self.progress.emit(100)
            self.succeeded.emit(self.dst)