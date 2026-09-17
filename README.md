# 视频格式转换器

Windows 桌面客户端视频格式转换器：PySide6 桌面界面 + ffmpeg/ffprobe 便携版二进制集成。**开箱即用，机器无需预装 Python 或 ffmpeg。**

## 功能特性

- **拖放 / 多选**添加视频，自动解析时长、分辨率、视频/音频编码、帧率、码率、文件大小
- **自动抽帧缩略图**：优先取 1 秒处避开片头黑帧，失败回退 0 秒
- **格式-编码联动**：支持 MP4 / MOV / MKV / AVI / WEBM 与 H.264 / H.265 / VP9 / 无损编码，界面按容器自动过滤无效组合
- **可调参数**：目标分辨率（保持比例缩放）、帧率、音频码率
- **批量转换队列**：逐文件状态标签、实时进度（99% 封顶，成功才 100%）、取消自动清理半截文件
- **细节体验**：输出目录记忆（QSettings）、同格式自动加 `_converted` 防覆盖、成品一键预览
- 全中文界面

## 立即下载

[![下载安装包](https://img.shields.io/badge/%E4%B8%8B%E8%BD%BD-%E5%AE%89%E8%A3%85%E5%8C%85%20v1.0.0-brightgreen)](https://github.com/dsq888/video-format-converter/releases/download/v1.0.0/video-format-converter-setup-v1.0.0.exe)

| 平台 | 文件 | 说明 |
|---|---|---|
| Windows x64 | [video-format-converter-setup-v1.0.0.exe](https://github.com/dsq888/video-format-converter/releases/download/v1.0.0/video-format-converter-setup-v1.0.0.exe) | 标准安装包：可选安装路径、桌面/开始菜单快捷方式、标准卸载器 |

> 双击运行安装向导即可；若浏览器提示"可能有害"，选择保留即可（未做代码签名）。全部历史版本见 [Releases](https://github.com/dsq888/video-format-converter/releases)。

## 从源码运行

```bash
# 需要 Python 3.10+
pip install -r requirements.txt
python main.py
```

## 打包

```bash
# 单文件 exe（bin/ 下便携 ffmpeg/ffprobe 一并打入）
python -m PyInstaller --onefile --windowed --name "视频格式转换器" --icon app.ico --add-data "bin/*;bin" main.py --clean --noconfirm

# 安装包（Inno Setup 7）
"C:\Program Files\Inno Setup 7\ISCC.exe" installer.iss
```

## 技术栈

| 类别 | 工具 |
|---|---|
| 语言 | Python 3.13 |
| GUI | PySide6（Qt 官方 Python 绑定） |
| 视频探测 | ffprobe 便携版二进制（`-print_format json`） |
| 转换 / 抽帧 | ffmpeg 便携版二进制（`subprocess`） |
| 打包 | PyInstaller + Inno Setup 7 |

## 目录结构

| 文件 | 职责 |
|---|---|
| `main.py` | 入口；全局 QSS 样式 |
| `main_window.py` | 主窗口 UI + 交互（拖放、卡片列表、详情/缩略图、批量队列、进度） |
| `ffmpeg_pipeline.py` | 核心逻辑：ffprobe 解析、缩略图、转换参数构建、引擎定位 |
| `converter.py` | `ConvertWorker(QThread)`：后台执行、进度上报（99% 封顶）、取消、错误提取 |
| `player.py` | 成品预览弹窗（QtMultimedia） |
| `installer.iss` | Inno Setup 安装脚本 |
| `bin/` | ffmpeg.exe / ffprobe.exe 便携版二进制 |

> 开发决策、踩坑修复与维护注意事项见 [HANDOFF.md](HANDOFF.md)，开发会话总结见 [SESSION_SUMMARY.md](SESSION_SUMMARY.md)。