# 项目交接说明（供其他 AI / 后续维护者接手）

## 1. 项目是什么

一个 **Windows 桌面客户端**视频格式转换器（HR 限时试题：客户端界面选型 + ffmpeg 命令行集成 + 信息/缩略图展示 + 可交付性）。

## 2. 技术栈 / 工具

| 类别 | 工具 | 说明 |
|---|---|---|
| 语言 | Python 3.13 | — |
| GUI 框架 | PySide6 | Qt 官方 Python 绑定，客户端界面 |
| 视频探测 | ffprobe（便携版二进制） | `subprocess` 调 `-print_format json`，位于 `bin/ffprobe.exe` |
| 视频转换/抽帧 | ffmpeg（便携版二进制） | `subprocess` 命令行，位于 `bin/ffmpeg.exe` |
| exe 打包 | PyInstaller | `--onefile --windowed --icon app.ico --add-data "bin/*;bin"` |
| 安装包 | Inno Setup 7（ISCC 编译） | 脚本 `installer.iss`，产物在 `installer_out/` |
| 依赖 | requirements.txt | 仅 `PySide6` 相关 |

> ffmpeg/ffprobe 便携版直接提交在 `bin/`，运行时由代码定位，用户机器无需安装环境。打包后从 `sys._MEIPASS` 临时目录读取。

## 3. 文件结构

| 文件 | 职责 |
|---|---|
| `main.py` | 入口；全局 QSS 样式（飞鼠新粗野主义配色） |
| `main_window.py` | 主窗口 UI + 交互：拖放/多选、文件卡片列表、详情/缩略图、格式-编码联动、输出目录选择、批量转换队列、进度条、QSettings 记忆、成品预览 |
| `ffmpeg_pipeline.py` | 核心逻辑：`probe_info`（ffprobe JSON 解析）、`temp_thumbnail`（抽帧）、`build_convert_args`（转换参数 + 提速预设 SPEED_OPTS）、`build_output_path`、引擎定位 |
| `converter.py` | `ConvertWorker(QThread)`：后台执行 ffmpeg、解析 `-progress` 上报进度（封顶 99，成功才 100）、取消、错误信息提取 |
| `player.py` | 成品预览弹窗（QtMultimedia） |
| `installer.iss` | Inno Setup 7 安装脚本：可选路径向导、中文界面、桌面/开始菜单快捷方式、标准卸载器 |
| `app.ico` | 应用图标（新粗野主义风格） |
| `bin/ffmpeg.exe` + `bin/ffprobe.exe` | 便携版二进制 |
| `AGENTS.md` | 开发准则（Karpathy Guidelines 四条） |

> 无 `pet.py`、无第三方视频处理库。`requirements.txt` 见根目录。

## 4. 已完成（DONE）

- ✅ ffprobe JSON 解析（时长/分辨率/编码/帧率/码率/音轨），损坏文件安全兜底
- ✅ 缩略图抽帧（先取 1 秒避开黑帧，失败回退 0 秒）
- ✅ 格式-编码兼容矩阵（AVI 仅 H.264、WEBM 仅 VP9……）+ 界面联动
- ✅ 分辨率/帧率/音频码率可选项（缩放表达式逗号需转义 `\,`）
- ✅ QThread 后台转换 + 实时进度 + 取消（清理半截文件）
- ✅ 批量队列 + 每文件状态标签 + 成品预览
- ✅ QSettings 记忆（格式/编码/输出目录/分辨率/帧率/码率）
- ✅ 打包 exe：无命令窗口弹窗（所有 subprocess 加 `CREATE_NO_WINDOW`）
- ✅ 转换提速参数（H.264→faster、H.265→fast、VP9→good+cpu-used 5）
- ✅ 安装包：可选路径向导、静默安装/启动/卸载自测通过
- ✅ 测试：功能链路 57 项 PASS（测试脚本已按用户要求清理，需要时重建）

## 5. 未完成（TODO）

### 任务 A：Git 初始化 + 提交 GitHub ✅ 已完成
- 仓库：<https://github.com/dsq888/video-format-converter>（公开，main 分支）
- `git init` → `.gitignore`（`__pycache__/`、`build/`、`dist/`、`*.spec`、`installer_out/` 等）→ 提交 → 推送完成
- `bin/*.exe` 已确认入库（单个 <100MB GitHub 硬限制，推送时仅有 >50MB 建议性警告）

### 任务 B：生成会话总结 md（决策 + 反馈）✅ 已完成
- 见同目录 `SESSION_SUMMARY.md`（技术决策、7 条踩坑修复、交付物清单）

## 6. 实现细节（不要破坏的点）

1. **引擎定位**：一律走 `ffmpeg_pipeline.ffmpeg_exe()/ffprobe_exe()`，勿硬编码路径（打包兼容依赖 `sys._MEIPASS`）
2. **子进程一律带 `CREATE_NO_WINDOW`**（`ffmpeg_pipeline.CREATE_NO_WINDOW`）：打包成 `--windowed` 后缺失会弹黑窗
3. **stderr 写临时文件**：`converter.py` 中 stderr 进 `TemporaryFile` 而非管道，避免 stdout/stderr 互塞阻塞
4. **进度封顶 99**：编码中进度 max 99，100% 只由成功信号给出（慢编码 VP9 音频先写完会导致上报时间虚满）；失败/取消不顶满进度条
5. **缩放表达式**：`scale=-2:min(1080\,ih)` 逗号必须转义，QSS 与代码中呈现为 `\\,`
6. **输出路径**：同格式加 `_converted` 后缀防覆盖；输出目录由用户选择（QSettings 记忆）
7. **打包命令**（项目根）：`python -m PyInstaller --onefile --windowed --name "视频格式转换器" --icon app.ico --add-data "bin/*;bin" main.py --clean --noconfirm`
8. **安装包编译**：`"C:\Program Files\Inno Setup 7\ISCC.exe" installer.iss`，产物 `installer_out\视频格式转换器-安装包-v1.0.0.exe`
9. **运行自测**：`python main.py`（项目根 `d:\AI小项目\视频格式转换器`）