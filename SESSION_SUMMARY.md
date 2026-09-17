# 视频格式转换器 —— 开发会话总结（决策 + 反馈）

> 本文件为任务 B 交付物：记录开发过程中的技术决策、踩坑修复与可交付结论。

## 1. 项目背景

HR 限时试题：实现一个 **Windows 桌面客户端视频格式转换器**。考察点：客户端界面选型、ffmpeg 命令行集成、视频信息/缩略图展示、可交付性（安装包）。

## 2. 技术决策与理由

| 决策 | 选择 | 理由 |
|---|---|---|
| GUI 框架 | PySide6 | Qt 官方 Python 绑定，成熟稳定、控件丰富；相比 Tkinter 现代，相比 Electron 无 Node 运行时负担 |
| 视频处理 | 便携版 ffmpeg/ffprobe 二进制 + `subprocess` | 二进制随项目打包在 `bin/`，用户机器无需安装任何环境；命令行集成直观、参数可控 |
| 信息探测 | `ffprobe -print_format json` | JSON 字段稳定，直接解析比逐行正则健壮；对损坏文件安全兜底（缺失字段置"未知"） |
| 缩略图 | ffmpeg 抽帧（先 1 秒处，失败回退 0 秒） | 避开片头黑帧；`-ss` 前置实现快速 seek |
| 后台转换 | `QThread`（ConvertWorker）+ 信号槽 | 转换是长任务，放主线程会冻结 UI；信号槽上报进度、完成、取消、错误 |
| 转换进度 | 解析 ffmpeg `-progress` 输出 | 标准化的 `out_time_ms` 等键值对，按总时长换算百分比 |
| exe 打包 | PyInstaller `--onefile --windowed` | 单文件交付、无控制台窗口；`bin/` 以 `--add-data` 打入，运行时经 `sys._MEIPASS` 定位 |
| 安装包 | Inno Setup 7 | 安装路径选择向导、中文界面、桌面/开始菜单快捷方式、标准卸载器 |

## 3. 踩坑与修复

1. **stdout/stderr 互塞阻塞**：ffmpeg 的日志（stderr）与 `-progress`（stdout）同时大流量输出，双向用管道捕获会互相填满缓冲区导致卡死 → stderr 重定向到 `TemporaryFile`，stdout 单独管道读取。
2. **缩放表达式逗号转义**：`scale=-2:min(1080,ih)` 中逗号是滤镜参数分隔符，必须写成 `min(1080\,ih)`，代码/QSS 中呈现为 `\\,`。
3. **黑窗**：打包成 `--windowed` 后，`subprocess` 调 ffmpeg 会弹出黑色控制台窗口 → 所有子进程加 `CREATE_NO_WINDOW`（`ffmpeg_pipeline.py` 统一定义）。
4. **进度虚满**：VP9 等慢编码下音频先写完，ffmpeg 上报的时间参数提前走满，进度条红着满格 → 进度封顶 99%，100% 只由成功信号给出；失败/取消不顶满进度条。
5. **慢编码**：默认 preset 转换太慢 → 提速预设：H.264→`faster`、H.265→`fast`、VP9→`deadline good + cpu-used 5`（质量损失很小）。
6. **同格式覆盖源文件**：输出与源同格式同名时自动加 `_converted` 后缀防覆盖。
7. **格式-编码兼容矩阵**：AVI 仅支持 H.264、WEBM 仅 VP9 等，界面按矩阵联动，避免用户选中必然失败的组合。

## 4. 测试与验证

- 功能链路 57 项 PASS：探测、缩略图、转换、取消（清理半截文件）、批量队列、成品预览、QSettings 记忆
- 安装包静默安装 / 启动 / 卸载自测通过
- 打包 exe 运行无黑窗、无报错

## 5. 交付物

| 交付物 | 位置 |
|---|---|
| GitHub 仓库（公开） | https://github.com/dsq888/video-format-converter |
| 安装包 | `installer_out\视频格式转换器-安装包-v1.0.0.exe`（本地，未入库） |
| 源码运行 | 项目根 `python main.py` |
| 打包命令 | `python -m PyInstaller --onefile --windowed --name "视频格式转换器" --icon app.ico --add-data "bin/*;bin" main.py --clean --noconfirm` |
| 安装包编译 | `"C:\Program Files\Inno Setup 7\ISCC.exe" installer.iss` |

> 详细文件职责与实现细节见同目录 `HANDOFF.md`。