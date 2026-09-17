"""基于 ffmpeg/ffprobe 命令行的视频信息探测、缩略图抽帧与转换命令构建。

信息解析采用 `ffprobe -print_format json`，输出字段稳定（JSON 而非逐行正则），
缩略图抽帧与编码转换由 ffmpeg 完成。
"""

import json
import os
import subprocess
import sys
import tempfile

# Windows 下子进程 ffmpeg/ffprobe 不弹控制台窗口（打包成 --windowed 后必须）
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _bin_dir():
    """定位 bin/ 目录：开发时在项目内，打包后在 PyInstaller 临时目录。"""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "bin")


def ffmpeg_exe():
    return os.path.join(_bin_dir(), "ffmpeg.exe")


def ffprobe_exe():
    return os.path.join(_bin_dir(), "ffprobe.exe")


def _fmt_duration(seconds):
    if not seconds:
        return "未知"
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def probe_info(path):
    """用 ffprobe 解析视频信息，返回 dict，缺失字段用 None/“未知”。"""
    proc = subprocess.run(
        [ffprobe_exe(), "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = {}

    fmt = data.get("format", {})
    streams = data.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), {})
    astream = next((s for s in streams if s.get("codec_type") == "audio"), {})

    # 时长（优先容器，其次视频流）
    duration = None
    for raw in (fmt.get("duration"), vstream.get("duration")):
        try:
            duration = float(raw)
            break
        except (TypeError, ValueError):
            continue

    # 码率 kb/s
    bitrate = None
    try:
        bitrate = int(fmt.get("bit_rate"))
    except (TypeError, ValueError):
        bitrate = None
    if bitrate:
        bitrate //= 1000

    # 帧率（avg_frame_rate 或 r_frame_rate，形如 "30000/1001"）
    fps = None
    fr = vstream.get("avg_frame_rate") or vstream.get("r_frame_rate")
    if fr:
        num, _, den = fr.partition("/")
        try:
            if den and float(den):
                fps = float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            fps = None

    return {
        "path": path,
        "name": os.path.basename(path),
        "size_bytes": os.path.getsize(path),
        "duration": duration,
        "duration_str": _fmt_duration(duration),
        "width": vstream.get("width"),
        "height": vstream.get("height"),
        "video_codec": vstream.get("codec_name") or "未知",
        "fps": fps,
        "bitrate": bitrate,
        "audio_codec": astream.get("codec_name") or "未知",
    }


def format_size(num_bytes):
    """字节数转易读字符串。"""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024


def make_thumbnail(path, out_path, width=320):
    """抽取视频前部一帧作为缩略图，成功返回 True。"""
    exe = ffmpeg_exe()
    # -ss 放在 -i 前做快速 seek；先取 1 秒处，避开开头黑帧
    cmd = [
        exe, "-y", "-ss", "1", "-i", path,
        "-vframes", "1", "-vf", f"scale={width}:-2", "-q:v", "2", out_path,
    ]
    subprocess.run(cmd, capture_output=True, creationflags=CREATE_NO_WINDOW)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return True
    # 回退：抽第 0 秒（适合 <1 秒的短视频）
    cmd[5] = "0"
    subprocess.run(cmd, capture_output=True, creationflags=CREATE_NO_WINDOW)
    return os.path.exists(out_path) and os.path.getsize(out_path) > 0


def temp_thumbnail(path, width=320):
    """在系统临时目录生成缩略图，返回图片路径或 None。"""
    fd, out = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    if make_thumbnail(path, out, width):
        return out
    return None


# ---- 转换 ----

FORMAT_PRESETS = {
    "MP4":  {"ext": ".mp4",  "acodec": "aac"},
    "MOV":  {"ext": ".mov",  "acodec": "aac"},
    "MKV":  {"ext": ".mkv",  "acodec": "aac"},
    "AVI":  {"ext": ".avi",  "acodec": "libmp3lame"},
    "WEBM": {"ext": ".webm", "acodec": "libopus"},
}

CODEC_PRESETS = {
    "H.264": "libx264",
    "H.265": "libx265",
    "VP9": "libvpx-vp9",
    "无损": "lossless",
}

# 编码提速参数：默认预设对慢编码不友好，转换器优先速度（质量损失很小）
SPEED_OPTS = {
    "H.264": ["-preset", "faster"],
    "H.265": ["-preset", "fast"],
    "VP9": ["-deadline", "good", "-cpu-used", "5"],
}

# 每种容器实际支持的编码（避免用户选中转必失败的组合）
FORMAT_CODECS = {
    "MP4":  ["H.264", "H.265", "无损"],
    "MOV":  ["H.264", "H.265", "无损"],
    "MKV":  ["H.264", "H.265", "VP9", "无损"],
    "AVI":  ["H.264"],
    "WEBM": ["VP9"],
}

# 界面上的格式小贴士
CODEC_HINTS = {
    "MP4":  "MP4 兼容性最好，推荐 H.264",
    "MOV":  "MOV 适合苹果设备，推荐 H.264",
    "MKV":  "MKV 容器自由，H.265 / VP9 更省空间",
    "AVI":  "AVI 是老容器，仅支持 H.264",
    "WEBM": "WEBM 只支持 VP9，适合网页播放",
}


def build_convert_args(src, dst, fmt, codec, scale=None, fps=None, abitrate=None):
    """构建 ffmpeg 转换参数（不含 -y / -progress，由调用方组装）。

    scale: -vf 缩放表达式（如 "-2:min(1080,ih)"），None 表示不缩放。
    fps / abitrate: 输出帧率 / 音频码率，None 表示保持默认。
    """
    acodec = FORMAT_PRESETS[fmt]["acodec"]
    args = ["-i", src]
    if scale:
        args += ["-vf", f"scale={scale}"]
    if fps:
        args += ["-r", fps]
    if abitrate:
        args += ["-b:a", abitrate]
    if codec == "无损":
        args += ["-c:v", "libx264", "-preset", "ultrafast", "-qp", "0"]
    else:
        args += ["-c:v", CODEC_PRESETS[codec]] + SPEED_OPTS.get(codec, [])
    args += ["-c:a", acodec, dst]
    return args


def build_output_path(src, fmt, out_dir=None):
    """根据源文件生成输出路径；同格式时加 _converted 后缀避免覆盖。

    out_dir 为 None 时输出到源文件同目录（保持旧行为）。
    """
    _, orig_ext = os.path.splitext(src)
    name = os.path.basename(os.path.splitext(src)[0])
    ext = FORMAT_PRESETS[fmt]["ext"]
    if orig_ext.lower() == ext.lower():
        name += "_converted"
    folder = out_dir or os.path.dirname(src)
    return os.path.join(folder, name + ext)