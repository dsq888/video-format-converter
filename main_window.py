"""主窗口：顶栏 + 四步状态条 + 奶油工作台（左侧拖放/详情/列表 + 右侧控制面板）。

设计语言严格对齐官方项目 public/styles.css（新粗野主义：奶油底、纯黑描边、硬阴影、深绯红强调）。
"""

import os

from PySide6.QtCore import Qt, QEvent, QSettings, QTimer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QComboBox, QPushButton, QProgressBar,
    QFileDialog, QLineEdit, QFrame, QGraphicsDropShadowEffect, QSizePolicy,
)

import ffmpeg_pipeline as ff
from converter import ConvertWorker
from player import PreviewDialog


# 应用状态 -> (面板文案, 文案颜色 + 底色, 对应步骤)
STATE_STYLE = {
    "IDLE": ("把视频拖进来吧～", "#555555", "#f4f5f8", 0),
    "LOADING": ("正在读取视频信息…", "#555555", "#f4f5f8", 1),
    "CONVERTING": ("正在转换中…", "#555555", "#f4f5f8", 2),
    "DONE": ("批量转换完成！", "#176b3a", "#dff5ee", 3),
    "ERROR": ("哎呀，出错了…", "#b3261e", "#fdecec", None),
}

ITEM_STATUS_STYLE = {
    "待转换": ("#555555", "#ffffff"),
    "转换中": ("#8a6d00", "#fff2bc"),
    "完成": ("#176b3a", "#dff5ee"),
    "失败": ("#b3261e", "#fdecec"),
    "已取消": ("#555555", "#f4f5f8"),
}

# 拖放区内嵌渐变区：默认 / 拖拽悬停
DROP_NORMAL = (
    "#dropInner {"
    " background: qlineargradient(x1:0, y1:0, x2:0.2, y2:1,"
    " stop:0 #fff6d8, stop:1 #fffdf8);"
    " border: 2px dashed rgba(17,17,17,0.18); border-radius: 12px; }"
)
DROP_ACTIVE = (
    "#dropInner { background: #ffe9ec;"
    " border: 2px dashed #bd334c; border-radius: 12px; }"
)

STEP_NAMES = ["选择文件", "识别格式", "开始转换", "保存结果"]

# 步骤条样式：常规 / 紧凑（小屏幕收紧内边距）
STEP_PAD = {False: "padding:10px 12px; font-size:13px;",
            True: "padding:6px 10px; font-size:12px;"}
STEP_STYLES = {
    "normal": lambda c: f"background:#f4f5f8; color:#555555; border-radius:12px;"
                        f" {STEP_PAD[c]} font-weight:700;",
    "active": lambda c: f"background:#ffe0e4; color:#a62840; border-radius:12px;"
                        f" {STEP_PAD[c]} font-weight:800;",
    "error": lambda c: f"background:#fdecec; color:#b3261e; border-radius:12px;"
                       f" {STEP_PAD[c]} font-weight:800;",
}

CHIP_OK = ("background:#dff5ee; color:#176b3a; border:2px solid #111111;"
           " border-radius:12px; padding:8px 14px; font-size:13px; font-weight:700;")
CHIP_BAD = ("background:#fdecec; color:#b3261e; border:2px solid #111111;"
            " border-radius:12px; padding:8px 14px; font-size:13px; font-weight:700;")

VIDEO_EXT = (
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".gif",
    ".flv", ".wmv", ".m4v", ".ts", ".mpg", ".mpeg",
)
VIDEO_FILTER = "视频文件 (*.mp4 *.mov *.mkv *.avi *.webm *.gif *.flv *.wmv *.m4v *.ts);;所有文件 (*.*)"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._stacked = False   # 窄窗口：两栏是否已改为上下堆叠
        self._compact = False   # 矮窗口：是否已进入紧凑模式
        self._show_done = True  # 紧凑模式下是否仍显示成品预览块（高度>=600 时）
        self.setWindowTitle("视频格式转换器")
        self.resize(1100, 720)
        # 540 = 紧凑模式全部控件（含状态条 46px 下限）恰好放下的最小高度，杜绝状态条被压扁
        self.setMinimumSize(760, 540)
        self.videos = {}          # path -> info dict
        self.thumbs = {}          # path -> 缩略图文件路径
        self.status_labels = {}   # path -> 状态 QLabel
        self.cards = {}           # path -> 文件卡片 QWidget
        self.marks = {}           # path -> 当前状态文字
        self.current_path = None
        self.last_output = None   # 最近一次转换成功的输出文件
        self.outputs = {}         # path -> 输出文件路径（成品预览用）
        self.done_thumbs = {}     # 输出路径 -> 成品缩略图临时文件
        self._done_path = None    # 当前预览区展示的成品路径
        self.worker = None
        self._preview = None
        self._step = 0            # 当前步骤条位置
        self.queue = []
        self.total = 0
        self.done_count = 0
        self._canceled = False
        # 进度条平滑动画：真实进度写入目标值，QTimer 每 30ms 步进逼近
        self._progress_target = 0
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(30)
        self._progress_timer.timeout.connect(self._tick_progress)
        self._build_ui()
        self._load_settings()
        self.setAcceptDrops(True)
        self.set_state("IDLE")

    # ---------- 响应式适配 ----------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "columns"):
            return
        compact = self.height() < 740
        self._apply_stack_mode(self.width() < 880 and not compact)
        self._apply_compact_heights(compact)
        if not compact:
            self._apply_grow(self.height())
        if self._stacked:
            self.panel_widget.setFixedWidth(max(self.width() - 24 * 2 - 24 * 2, 0))

    def _apply_stack_mode(self, stacked):
        """窄窗口：右侧面板从右栏挪到左栏下方，改为通栏。"""
        if stacked == self._stacked:
            return
        self._stacked = stacked
        if stacked:
            self.columns.removeWidget(self.panel_widget)
            # 工作台内布局顺序固定为 [双栏]，面板插到其后
            self.ws.insertWidget(1, self.panel_widget)
            self.panel_widget.setFixedWidth(max(self.width() - 96, 0))
        else:
            self.ws.removeWidget(self.panel_widget)
            self.columns.addWidget(self.panel_widget, 1)
            self.panel_widget.setFixedWidth(360)

    def _apply_compact_heights(self, compact):
        """矮窗口：收紧留白、缩小图标/缩略图/面板，保证关键控件齐全可见。"""
        show_done = not compact or self.height() >= 660
        guarded = (compact == self._compact and show_done == self._show_done)
        if guarded or not hasattr(self, "drop_eyebrow") or not hasattr(self, "pv"):
            return
        self._compact = compact
        self._show_done = show_done
        if compact:
            self.root.setContentsMargins(24, 10, 24, 12)
            self.root.setSpacing(10)
            self.ws.setContentsMargins(12, 12, 12, 12)
            self.ws.setSpacing(10)
            self.left_col.setSpacing(8)
            self.drop_inner.layout().setContentsMargins(16, 6, 16, 6)
            self.choose_files_btn.setFixedHeight(30)
            self.thumb.setFixedSize(140, 78)
            self.detail_layout.setContentsMargins(14, 10, 14, 10)
            self.preview_btn.setFixedHeight(32)
            self.file_list.setMinimumHeight(72)
            self.panel_widget.setFixedWidth(300)
            self.pv.setContentsMargins(12, 12, 12, 12)
            self.pv.setSpacing(8)
            self.dir_edit.setFixedHeight(34)
            self.dir_choose_btn.setFixedHeight(34)
            self.dir_open_btn.setFixedHeight(34)
            self.convert_btn.setFixedHeight(40)
            self.cancel_btn.setFixedHeight(40)
            self.status_text.setMinimumHeight(46)
            self.hint.setVisible(False)
            self.adv_title.setVisible(False)
            self.adv_box.setVisible(False)
            self.div_adv.setVisible(False)
            self.div_done.setVisible(False)
            self.div_action.setVisible(False)
            # 三档响应式：紧凑窗口只保留"预览成品视频"按钮，黑框与标题在高度>=660 时显示
            self.done_title.setVisible(show_done)
            self.done_frame.setVisible(show_done)
            self.done_frame.setMinimumHeight(56)
            self.done_frame.setMaximumHeight(220)
            # 紧凑（含堆叠通栏）下黑框也吃富余高度，避免空白积在面板底部
            self.done_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            self.pv.setStretch(self.pv.indexOf(self.done_frame), 5)
            self.done_preview_btn.setVisible(True)
            self.done_preview_btn.setFixedHeight(32)
            for i in self.pv_stretches[:-1]:
                self.pv.setStretch(i, 0)
            self.pv.setStretch(self.pv_stretches[-1], 1)
        else:
            self.root.setContentsMargins(24, 18, 24, 26)
            self.root.setSpacing(14)
            self.ws.setContentsMargins(24, 24, 24, 24)
            self.ws.setSpacing(18)
            self.left_col.setSpacing(14)
            self.drop_inner.layout().setContentsMargins(16, 22, 16, 22)
            self.choose_files_btn.setFixedHeight(36)
            self.thumb.setFixedSize(208, 116)
            self.detail_layout.setContentsMargins(16, 14, 16, 14)
            self.preview_btn.setFixedHeight(32)
            self.file_list.setMinimumHeight(140)
            self.panel_widget.setFixedWidth(360)
            self.pv.setContentsMargins(18, 18, 18, 18)
            self.pv.setSpacing(16)
            self.dir_edit.setFixedHeight(38)
            self.dir_choose_btn.setFixedHeight(38)
            self.dir_open_btn.setFixedHeight(38)
            self.convert_btn.setFixedHeight(46)
            self.cancel_btn.setFixedHeight(46)
            self.status_text.setMinimumHeight(46)
            self.hint.setVisible(True)
            self.adv_title.setVisible(True)
            self.adv_box.setVisible(True)
            self.done_title.setVisible(True)
            self.done_frame.setVisible(True)
            self.done_preview_btn.setVisible(True)
            self.div_adv.setVisible(True)
            self.div_done.setVisible(True)
            self.div_action.setVisible(True)
            self.done_frame.setMinimumHeight(84)
            self.done_frame.setMaximumHeight(140)
            self.done_preview_btn.setFixedHeight(32)
            for i in self.pv_stretches[:-1]:
                self.pv.setStretch(i, 1)
            self.pv.setStretch(self.pv_stretches[-1], 2)
        self.eyebrow.setVisible(not compact)
        self.drop_eyebrow.setVisible(not compact)
        self.drop_sub.setVisible(not compact)
        self._set_step(self._step)

    def _apply_grow(self, h):
        """常规/大窗口：控件随窗口高度按比例放大、字段间空白均匀分散。
        以紧凑模式为标准 0 档，740 高度起线性放大，1180 高度封顶。"""
        t = min(max((h - 740) / (1180 - 740), 0.0), 1.0)

        def L(a, b):
            return int(round(a + (b - a) * t))

        self.drop_inner.layout().setSpacing(L(8, 20))
        self.choose_files_btn.setFixedHeight(L(36, 52))
        self.thumb.setFixedSize(L(208, 400), L(116, 224))
        self.preview_btn.setFixedHeight(L(32, 44))
        for b in (self.dir_edit, self.dir_choose_btn, self.dir_open_btn):
            b.setFixedHeight(L(38, 54))
        for c in (self.format_combo, self.codec_combo,
                  self.scale_combo, self.fps_combo, self.abitrate_combo):
            c.setFixedHeight(L(36, 56))
        self.convert_btn.setFixedHeight(L(46, 64))
        self.cancel_btn.setFixedHeight(L(46, 64))
        self.progress.setFixedHeight(L(18, 28))
        # 黑框直接按窗口高度线性取高（min=max 等价幂等固定），不再依赖弹性分配
        # 460 已接近面板富余极限（实测 slack≈20px），榨干到 480
        self.done_frame.setMinimumHeight(L(84, 480))
        self.done_frame.setMaximumHeight(L(84, 480))
        # 面板放大以不挤出窗口为限：给左栏（缩略图 + 详情边距 + 信息列）预留空间
        panel_target = L(360, 560)
        avail = self.width() - 96 - 16 - L(208, 400) - 70
        self.panel_widget.setFixedWidth(max(300, min(panel_target, avail)))
        # spacing 固定 12：不再随窗口膨胀，省下的高度全给成品预览黑框
        self.pv.setSpacing(12)
        self.ws.setSpacing(L(18, 30))
        self.left_col.setSpacing(L(14, 24))
        # 弹簧全部归零、黑框 Expanding：富余空间全给成品预览，字段区紧凑
        for i in self.pv_stretches:
            self.pv.setStretch(i, 0)
        self.done_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.pv.setStretch(self.pv.indexOf(self.done_frame), 5)
        if self.current_path:
            self._show_thumb(self.current_path)
        if self._done_path:
            self._show_done_thumb(self._done_path)

    # ---------- 构建界面 ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 18, 24, 26)
        root.setSpacing(14)
        self.root = root

        self._build_topbar(root)
        self._build_steps(root)

        # 奶油工作台：官方 --panel #fffdf8，圆角 16，硬阴影 6px 6px 0 #111
        workspace = QWidget()
        workspace.setObjectName("workspace")
        self._hard_shadow(workspace, 6)
        self.ws = QVBoxLayout(workspace)
        self.ws.setContentsMargins(24, 24, 24, 24)
        self.ws.setSpacing(18)
        self.workspace = workspace

        columns = QHBoxLayout()
        columns.setSpacing(16)
        self.columns = columns

        left = QVBoxLayout()
        left.setSpacing(14)
        self.left_col = left
        self._build_drop_zone(left)
        self._build_detail(left)
        self._build_file_list(left)
        columns.addLayout(left, 3)
        columns.addWidget(self._build_panel(), 1)
        self.ws.addLayout(columns, 1)
        root.addWidget(workspace, 1)

        # 点击拖放区选文件
        for w in (self.drop_panel, self.drop_inner,
                  self.drop_eyebrow, self.drop_title, self.drop_sub):
            w.installEventFilter(self)

    def _hard_shadow(self, widget, offset):
        """无模糊的硬偏移阴影（官方 --shadow: N px N px 0 #111 的 Qt 等价物）。"""
        eff = QGraphicsDropShadowEffect(widget)
        eff.setBlurRadius(0)
        eff.setOffset(offset, offset)
        eff.setColor(QColor("#111111"))
        widget.setGraphicsEffect(eff)

    def _build_topbar(self, parent):
        top = QHBoxLayout()
        top.setSpacing(10)
        lockup = QVBoxLayout()
        lockup.setSpacing(2)
        self.eyebrow = QLabel("本地离线 · 视频都在自己电脑上处理")
        self.eyebrow.setObjectName("eyebrow")
        lockup.addWidget(self.eyebrow)
        self.app_title = QLabel("视频格式转换器")
        self.app_title.setObjectName("appTitle")
        lockup.addWidget(self.app_title)
        top.addLayout(lockup)
        top.addStretch(1)
        self.engine_chip = QLabel("✓ 引擎已就绪")
        if os.path.exists(ff.ffmpeg_exe()) and os.path.exists(ff.ffprobe_exe()):
            self.engine_chip.setStyleSheet(CHIP_OK)
        else:
            self.engine_chip.setText("引擎缺失，请检查 bin 目录")
            self.engine_chip.setStyleSheet(CHIP_BAD)
        top.addWidget(self.engine_chip, 0, Qt.AlignVCenter)
        parent.addLayout(top)

    def _build_steps(self, parent):
        row = QHBoxLayout()
        row.setSpacing(10)
        self.step_labels = []
        for name in STEP_NAMES:
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignCenter)
            row.addWidget(lbl, 1)
            self.step_labels.append(lbl)
        parent.addLayout(row)

    def _set_step(self, index, error=False):
        self._step = index
        for i, lbl in enumerate(self.step_labels):
            if i == index and error:
                key = "error"
            elif i == index:
                key = "active"
            else:
                key = "normal"
            lbl.setStyleSheet(STEP_STYLES[key](self._compact))

    def _build_drop_zone(self, parent):
        # 外层面板：白卡 + 2px 黑描边；内嵌渐变拖放区（同官方 drop-panel/drop-zone 结构）
        self.drop_panel = QWidget()
        self.drop_panel.setObjectName("dropPanel")
        self.drop_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        outer = QVBoxLayout(self.drop_panel)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)

        self.drop_inner = QWidget()
        self.drop_inner.setObjectName("dropInner")
        self.drop_inner.setStyleSheet(DROP_NORMAL)
        dz = QVBoxLayout(self.drop_inner)
        dz.setContentsMargins(16, 22, 16, 22)
        dz.setSpacing(8)
        dz.setAlignment(Qt.AlignCenter)
        dz.addStretch(1)

        self.drop_eyebrow = QLabel("拖进来自动识别格式")
        self.drop_eyebrow.setObjectName("dropEyebrow")
        self.drop_eyebrow.setAlignment(Qt.AlignCenter)
        dz.addWidget(self.drop_eyebrow)

        self.drop_title = QLabel("拖入视频文件")
        self.drop_title.setObjectName("dropTitle")
        self.drop_title.setAlignment(Qt.AlignCenter)
        dz.addWidget(self.drop_title)

        self.drop_sub = QLabel("MP4、MOV、MKV、AVI、WEBM 都可以试")
        self.drop_sub.setObjectName("dropSub")
        self.drop_sub.setAlignment(Qt.AlignCenter)
        dz.addWidget(self.drop_sub)

        self.choose_files_btn = QPushButton("选择视频文件")
        self.choose_files_btn.setObjectName("ghostBtn")
        self.choose_files_btn.clicked.connect(self._choose_files)
        dz.addWidget(self.choose_files_btn, 0, Qt.AlignCenter)
        dz.addStretch(1)

        outer.addWidget(self.drop_inner)
        parent.addWidget(self.drop_panel)

    def _build_detail(self, parent):
        detail = QWidget()
        detail.setObjectName("detail")
        detail.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        dl = QHBoxLayout(detail)
        dl.setContentsMargins(16, 14, 16, 14)
        dl.setSpacing(14)
        self.detail_layout = dl

        thumb_col = QVBoxLayout()
        thumb_col.setSpacing(8)
        self.thumb = QLabel("缩略图")
        self.thumb.setObjectName("thumb")
        self.thumb.setFixedSize(208, 116)
        self.thumb.setAlignment(Qt.AlignCenter)
        thumb_col.addWidget(self.thumb)

        self.preview_btn = QPushButton("▶  预览视频")
        self.preview_btn.setObjectName("previewBtn")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._open_preview)
        thumb_col.addWidget(self.preview_btn)
        dl.addLayout(thumb_col)

        self.info = QLabel("拖入视频后，这里显示缩略图和视频信息")
        self.info.setObjectName("info")
        self.info.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.info.setWordWrap(True)
        dl.addWidget(self.info, 1)
        parent.addWidget(detail)

    def _build_file_list(self, parent):
        # 转换队列卡片：白卡 + 标题计数 + 排队列表 + 空状态引导，占住左下空白区
        card = QWidget()
        card.setObjectName("queuePanel")
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)
        head = QHBoxLayout()
        title = QLabel("转换队列")
        title.setObjectName("fieldLabel")
        head.addWidget(title)
        head.addStretch(1)
        self.queue_count = QLabel("0 个文件")
        self.queue_count.setObjectName("hint")
        head.addWidget(self.queue_count)
        v.addLayout(head)

        self.file_list = QListWidget()
        self.file_list.setSpacing(8)
        self.file_list.setMinimumHeight(140)
        self.file_list.currentItemChanged.connect(self._on_item_changed)
        v.addWidget(self.file_list, 1)

        self.queue_empty = QLabel("拖入视频后，文件会在这里排队等待转换")
        self.queue_empty.setObjectName("hint")
        self.queue_empty.setAlignment(Qt.AlignCenter)
        v.addWidget(self.queue_empty)
        parent.addWidget(card, 1)

    def _build_panel(self):
        self.panel_widget = QWidget()
        self.panel_widget.setObjectName("panel")
        self.panel_widget.setFixedWidth(360)
        pv = QVBoxLayout(self.panel_widget)
        pv.setContentsMargins(18, 18, 18, 18)
        pv.setSpacing(16)
        self.pv = pv

        # 输出目录
        pv.addWidget(self._field_label("输出目录"))
        dir_row = QHBoxLayout()
        dir_row.setSpacing(10)
        self.dir_row = dir_row
        self.dir_edit = QLineEdit()
        self.dir_edit.setObjectName("dirEdit")
        self.dir_edit.setReadOnly(True)
        self.dir_edit.setFixedHeight(38)
        self.dir_edit.setPlaceholderText("默认：与源视频同目录")
        self.dir_choose_btn = QPushButton("选择")
        self.dir_choose_btn.setObjectName("ghostBtn")
        self.dir_choose_btn.setFixedHeight(38)
        self.dir_choose_btn.setMinimumWidth(52)
        self.dir_choose_btn.clicked.connect(self._choose_out_dir)
        self.dir_open_btn = QPushButton("打开")
        self.dir_open_btn.setObjectName("ghostBtn")
        self.dir_open_btn.setFixedHeight(38)
        self.dir_open_btn.setMinimumWidth(52)
        self.dir_open_btn.setEnabled(False)
        self.dir_open_btn.clicked.connect(self._open_out_dir)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(self.dir_choose_btn)
        dir_row.addWidget(self.dir_open_btn)
        pv.addLayout(dir_row)
        pv.addStretch(1)

        pv.addWidget(self._field_label("目标格式"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(list(ff.FORMAT_PRESETS.keys()))
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        pv.addWidget(self.format_combo)
        pv.addStretch(1)

        pv.addWidget(self._field_label("视频编码"))
        self.codec_combo = QComboBox()
        pv.addWidget(self.codec_combo)
        pv.addStretch(1)

        self.hint = QLabel("")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        pv.addWidget(self.hint)
        self._on_format_changed(self.format_combo.currentText())

        # 高级参数（紧凑/小窗口下整体隐藏，避免挤压关键控件）
        self.div_adv = self._divider()
        pv.addWidget(self.div_adv)
        self.adv_title = self._field_label("高级参数（可选）")
        pv.addWidget(self.adv_title)
        self.adv_box = QWidget()
        av = QVBoxLayout(self.adv_box)
        av.setContentsMargins(0, 0, 0, 0)
        av.setSpacing(10)
        r1, self.scale_combo = self._adv_row("分辨率", [
            ("保持原样", ""),
            ("4K · 3840×2160", "-2:min(2160\\,ih)"),
            ("2K · 2560×1440", "-2:min(1440\\,ih)"),
            ("1080p · 1920×1080", "-2:min(1080\\,ih)"),
            ("720p · 1280×720", "-2:min(720\\,ih)"),
            ("480p · 854×480", "-2:min(480\\,ih)"),
        ])
        r2, self.fps_combo = self._adv_row("帧率", [
            ("保持原样", ""),
            ("60 fps", "60"),
            ("30 fps", "30"),
            ("25 fps", "25"),
            ("24 fps", "24"),
        ])
        r3, self.abitrate_combo = self._adv_row("音频码率", [
            ("自动", ""),
            ("320 kbps", "320k"),
            ("256 kbps", "256k"),
            ("192 kbps", "192k"),
            ("128 kbps", "128k"),
            ("96 kbps", "96k"),
        ])
        av.addLayout(r1)
        av.addLayout(r2)
        av.addLayout(r3)
        pv.addWidget(self.adv_box)

        # 成品预览：左边选中"完成"的视频后，这里显示输出视频缩略图，点击可播放成品
        self.div_done = self._divider()
        pv.addWidget(self.div_done)
        self.done_title = self._field_label("成品预览")
        pv.addWidget(self.done_title)
        self.done_frame = QLabel("转换完成后，这里预览成品视频")
        self.done_frame.setObjectName("doneFrame")
        self.done_frame.setAlignment(Qt.AlignCenter)
        self.done_frame.setWordWrap(True)   # 长文案自动换行，避免挤压
        self.done_frame.setMinimumHeight(64)
        pv.addWidget(self.done_frame, 1)
        self.done_preview_btn = QPushButton("▶ 预览成品视频")
        self.done_preview_btn.setObjectName("previewBtn")
        self.done_preview_btn.setEnabled(False)
        self.done_preview_btn.clicked.connect(self._open_done_preview)
        pv.addWidget(self.done_preview_btn)

        # 上半配置、下半操作：操作区锚定在面板底部，保证左右两栏底部齐平
        self.div_action = self._divider()
        pv.addWidget(self.div_action)
        pv.addStretch(2)

        self.convert_btn = QPushButton("开始转换")
        self.convert_btn.setObjectName("primaryBtn")
        self.convert_btn.setFixedHeight(46)
        self._hard_shadow(self.convert_btn, 3)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("ghostBtn")
        self.cancel_btn.setFixedHeight(46)
        self.cancel_btn.setMinimumWidth(88)
        self.cancel_btn.setEnabled(False)
        self.convert_btn.clicked.connect(self._start_convert)
        self.cancel_btn.clicked.connect(self._cancel_convert)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.btn_row = btn_row
        btn_row.addWidget(self.convert_btn, 2)
        btn_row.addWidget(self.cancel_btn, 1)
        pv.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        pv.addWidget(self.progress)

        self.status_text = QLabel("")
        self.status_text.setObjectName("statusBox")
        self.status_text.setAlignment(Qt.AlignCenter)
        self.status_text.setWordWrap(True)
        pv.addWidget(self.status_text)

        # 面板内 4 段伸缩弹簧的索引（前 3 段分散字段间距，最后 1 段把操作区压底）
        self.pv_stretches = [i for i in range(pv.count())
                             if pv.itemAt(i).spacerItem()]

        return self.panel_widget

    def _field_label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    def _adv_row(self, text, items):
        """高级参数行：固定宽标签 + 下拉框（数据挂在 UserData 上）。"""
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        lbl.setFixedWidth(64)
        row.addWidget(lbl)
        combo = QComboBox()
        for name, data in items:
            combo.addItem(name, data)
        row.addWidget(combo, 1)
        return row, combo

    def _divider(self):
        """分组分隔线：2px 纯黑横线，贴合飞鼠风格的描边语言。"""
        line = QFrame()
        line.setObjectName("divider")
        line.setFixedHeight(2)
        return line

    # ---------- 输出目录 ----------
    def _out_dir(self):
        text = self.dir_edit.text().strip()
        return text or None

    def _choose_out_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录", self._out_dir() or "")
        if folder:
            self.dir_edit.setText(os.path.normpath(folder))
            self._save_settings()

    def _open_out_dir(self):
        target = (os.path.dirname(self.last_output) if self.last_output
                  else self._out_dir())
        if target:
            os.startfile(target)  # noqa: S606 目标来自用户选择/转换结果

    # ---------- 格式/编码联动 ----------
    def _on_format_changed(self, fmt):
        allowed = ff.FORMAT_CODECS.get(fmt, [])
        current = self.codec_combo.currentText()
        self.codec_combo.blockSignals(True)
        self.codec_combo.clear()
        self.codec_combo.addItems(allowed)
        if current in allowed:
            self.codec_combo.setCurrentText(current)
        self.codec_combo.blockSignals(False)
        self.hint.setText(ff.CODEC_HINTS.get(fmt, ""))

    # ---------- 文件选择 / 拖拽 ----------
    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            if obj in (self.drop_panel, self.drop_inner,
                       self.drop_eyebrow, self.drop_title, self.drop_sub):
                self._choose_files()
                return True
        return super().eventFilter(obj, event)

    def _choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择视频文件", "", VIDEO_FILTER)
        if paths:
            self.load_videos(paths)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self.drop_inner.setStyleSheet(DROP_ACTIVE)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.drop_inner.setStyleSheet(DROP_NORMAL)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.drop_inner.setStyleSheet(DROP_NORMAL)
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        videos = [p for p in paths if p.lower().endswith(VIDEO_EXT)]
        if videos:
            self.load_videos(videos)

    def load_videos(self, paths):
        self.set_state("LOADING")
        try:
            for p in paths:
                if p in self.videos:
                    continue
                info = ff.probe_info(p)
                self.videos[p] = info
                self._add_file_card(p, info)
            if self.file_list.count() and self.file_list.currentRow() < 0:
                self.file_list.setCurrentRow(0)
            self.queue_empty.setVisible(self.file_list.count() == 0)
            self.queue_count.setText(f"{self.file_list.count()} 个文件")
            self.set_state("IDLE", f"已加载 {len(self.videos)} 个视频")
            self._set_step(1)   # 停留在"识别格式"步骤，展示识别完成
        except Exception as exc:  # noqa: BLE001
            self.set_state("ERROR", f"读取失败：{exc}")

    def _add_file_card(self, path, info):
        """添加一张文件卡片到列表：文件名 + 大小·编码 + 状态标签。"""
        card = QWidget()
        card.setObjectName("fileCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(10)

        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel(info["name"])
        name.setObjectName("fileName")
        col.addWidget(name)
        meta = QLabel(f"{ff.format_size(info['size_bytes'])} · {info['video_codec']}")
        meta.setObjectName("fileMeta")
        col.addWidget(meta)

        status = QLabel("待转换")
        status.setObjectName("fileStatus")
        self.status_labels[path] = status

        row.addLayout(col, 1)
        row.addWidget(status, 0, Qt.AlignVCenter)

        item = QListWidgetItem()
        item.setData(Qt.UserRole, path)
        item.setSizeHint(card.sizeHint())
        self.file_list.addItem(item)
        self.file_list.setItemWidget(item, card)

        self.cards[path] = card
        self.set_item_status(path, "待转换")

    # ---------- 预览 ----------
    def _open_preview(self):
        if not self.current_path or self.current_path not in self.videos:
            return
        if self._preview is not None and self._preview.isVisible():
            self._preview.close()
        self._preview = PreviewDialog(self.current_path,
                                      self.videos[self.current_path]["name"], self)
        self._preview.show()

    # ---------- 成品预览（右侧面板） ----------
    def _open_done_preview(self):
        """播放当前选中视频转换后的成品。"""
        if not self._done_path:
            return
        if self._preview is not None and self._preview.isVisible():
            self._preview.close()
        self._preview = PreviewDialog(self._done_path,
                                      os.path.basename(self._done_path), self)
        self._preview.show()

    def _show_done_thumb(self, dst):
        if dst not in self.done_thumbs:
            self.done_thumbs[dst] = ff.temp_thumbnail(dst)
        tp = self.done_thumbs[dst]
        if tp:
            pix = QPixmap(tp)
            pix = pix.scaled(self.done_frame.size(), Qt.KeepAspectRatio,
                             Qt.SmoothTransformation)
            self.done_frame.setPixmap(pix)
            self.done_frame.setText("")
        else:
            self.done_frame.setPixmap(QPixmap())
            self.done_frame.setText("成品缩略图生成失败，可直接点击下方按钮预览")
        self.done_preview_btn.setEnabled(True)

    def _update_done_preview(self, path):
        """按选中项刷新右侧成品预览区：有成品显示缩略图，否则显示占位提示。"""
        dst = self.outputs.get(path)
        if dst and os.path.exists(dst):
            self._done_path = dst
            self._show_done_thumb(dst)
        else:
            self._done_path = None
            self.done_frame.setPixmap(QPixmap())
            self.done_frame.setText("转换完成后，这里预览成品视频")
            self.done_preview_btn.setEnabled(False)

    # ---------- 选中项变化 ----------
    def _on_item_changed(self, current, _prev):
        if current is None:
            return
        path = current.data(Qt.UserRole)
        self.current_path = path
        for p in self.cards:
            self._refresh_card(p)
        info = self.videos.get(path)
        if info:
            self.preview_btn.setEnabled(True)
            self._show_info(info)
            self._show_thumb(path)
        self._update_done_preview(path)
        # 步骤条跟随选中文件：完成的文件高亮"保存结果"，否则回"识别格式"；
        # 转换进行中不打扰（保持"开始转换"步骤）
        if self.worker:
            self._set_step(2)
        elif self.marks.get(path) == "完成":
            self._set_step(3)
        else:
            self._set_step(1)

    def _show_info(self, info):
        fps = f"{info['fps']:.1f} fps" if info["fps"] else "未知"
        res = f"{info['width']} × {info['height']}" if info["width"] else "未知"
        bitrate = f"{info['bitrate']} kb/s" if info["bitrate"] else "未知"
        lines = [
            "时长    " + info["duration_str"],
            "分辨率  " + res,
            "编码    " + info["video_codec"],
            "帧率    " + fps,
            "大小    " + ff.format_size(info["size_bytes"]),
            "码率    " + bitrate,
            "音轨    " + info["audio_codec"],
        ]
        self.info.setText("\n".join(lines))

    def _show_thumb(self, path):
        if path not in self.thumbs:
            self.thumbs[path] = ff.temp_thumbnail(path)
        tp = self.thumbs[path]
        if tp:
            pix = QPixmap(tp)
            pix = pix.scaled(self.thumb.size(), Qt.KeepAspectRatio,
                             Qt.SmoothTransformation)
            self.thumb.setPixmap(pix)
        else:
            self.thumb.setText("无缩略图")

    def set_state(self, key, message: str = None):
        """更新状态文案/颜色与步骤条。"""
        msg, color, bg, step = STATE_STYLE[key]
        self.status_text.setText(message or msg)
        self.status_text.setStyleSheet(
            f"#statusBox {{ color: {color}; background: {bg};"
            f" border: 2px solid #111111; border-radius: 12px; padding: 14px 20px;"
            f" font-size: 13px; font-weight: 600; }}")
        if key == "ERROR":
            self._set_step(self._step, error=True)
        else:
            self._set_step(step)

    def _set_progress_color(self, color=None):
        """转换中默认渐变；完成后绿色；失败红色。"""
        if color:
            self.progress.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; }}")
        else:
            self.progress.setStyleSheet("")

    def _on_progress(self, value):
        self._progress_target = value
        if not self._progress_timer.isActive():
            self._progress_timer.start()

    def _tick_progress(self):
        cur, tgt = self.progress.value(), self._progress_target
        if cur == tgt:
            self._progress_timer.stop()
            return
        self.progress.setValue(cur + (1 if cur < tgt else -1))

    # ---------- 状态标记 & 设置记忆 ----------
    def set_item_status(self, path, mark):
        self.marks[path] = mark
        lbl = self.status_labels.get(path)
        if lbl:
            color, _bg = ITEM_STATUS_STYLE.get(mark, ("#555555", "#ffffff"))
            lbl.setText(mark)
            lbl.setStyleSheet(
                f"color: {color}; font-weight: 800; font-size: 12px;"
                f" background: transparent;")
        self._refresh_card(path)

    def _refresh_card(self, path):
        """按状态染整卡底色；当前选中的卡用绯红描边。"""
        card = self.cards.get(path)
        if not card:
            return
        _color, bg = ITEM_STATUS_STYLE.get(self.marks.get(path, "待转换"),
                                           ("#555555", "#ffffff"))
        if path == self.current_path:
            border = "2px solid #bd334c"
        else:
            border = "1px solid #111111"
        card.setStyleSheet(
            f"#fileCard {{ background: {bg}; border: {border}; border-radius: 12px; }}")

    def _clear_statuses(self, paths=None):
        """把本批待处理的文件复位为"待转换"；已完成的文件永远不动。"""
        for path in (paths if paths is not None else self.videos):
            if self.marks.get(path) != "完成":
                self.set_item_status(path, "待转换")

    def _save_settings(self):
        s = QSettings("VideoConverter", "VideoConverter")
        s.setValue("format", self.format_combo.currentText())
        s.setValue("codec", self.codec_combo.currentText())
        s.setValue("out_dir", self._out_dir() or "")
        s.setValue("scale", self.scale_combo.currentData())
        s.setValue("fps", self.fps_combo.currentData())
        s.setValue("abitrate", self.abitrate_combo.currentData())

    def _load_settings(self):
        s = QSettings("VideoConverter", "VideoConverter")
        out_dir = s.value("out_dir", "")
        if out_dir and os.path.isdir(out_dir):
            self.dir_edit.setText(out_dir)
        fmt = s.value("format", "MP4")
        idx = self.format_combo.findText(fmt)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)  # 会触发 _on_format_changed
        codec = s.value("codec", "H.264")
        idx = self.codec_combo.findText(codec)
        if idx >= 0:
            self.codec_combo.setCurrentIndex(idx)
        for combo, key in ((self.scale_combo, "scale"),
                           (self.fps_combo, "fps"),
                           (self.abitrate_combo, "abitrate")):
            idx = combo.findData(s.value(key, ""))
            if idx >= 0:
                combo.setCurrentIndex(idx)

    # ---------- 转换 ----------
    def _start_convert(self):
        if self.worker is not None:
            return
        paths = [self.file_list.item(i).data(Qt.UserRole)
                 for i in range(self.file_list.count())]
        # 批次筛选：状态为"完成"的文件直接跳过，只转换新放入（待转换/失败）的一批
        paths = [p for p in paths if self.marks.get(p) != "完成"]
        if not paths:
            if self.videos:
                self.set_state("ERROR", "没有待转换的文件，拖入新视频即可开始")
            else:
                self.set_state("ERROR", "请先拖入视频文件")
            return
        self._save_settings()
        self._clear_statuses(paths)
        self._canceled = False
        self.last_output = None
        # outputs 不清空：历史批次已完成文件的成品映射需要保留，
        # 点回第一个（已完成）仍能显示其成品预览
        self._update_done_preview(self.current_path)
        self.queue = list(paths)
        self.total = len(self.queue)
        self.done_count = 0
        self._process_next()

    def _process_next(self):
        if not self.queue:
            self._restore_controls()
            if self._canceled:
                self.set_state("IDLE", "已取消转换")
            elif self.total:
                self.set_state("DONE",
                               f"批量转换完成：成功 {self.done_count}/{self.total}")
            return
        src = self.queue.pop(0)
        self.current_path = src
        info = self.videos[src]
        fmt = self.format_combo.currentText()
        codec = self.codec_combo.currentText()
        dst = ff.build_output_path(src, fmt, self._out_dir())

        self.set_item_status(src, "转换中")
        self.worker = ConvertWorker(
            src, dst, fmt, codec, info.get("duration"),
            self.scale_combo.currentData() or None,
            self.fps_combo.currentData() or None,
            self.abitrate_combo.currentData() or None)
        self.worker.progress.connect(self._on_progress)
        self.worker.succeeded.connect(self._on_one_done)
        self.worker.failed.connect(self._on_one_failed)
        self.worker.finished.connect(self._on_worker_finished)

        self.convert_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self._set_progress_color(None)
        self.progress.setValue(0)
        self.set_state("CONVERTING",
                       f"正在转换 {info['name']}"
                       f"（{self.done_count + 1}/{self.total}）…")
        self.worker.start()

    def _cancel_convert(self):
        self._canceled = True
        self.queue = []
        if self.worker and self.worker.isRunning():
            self.worker.cancel()

    def _on_one_done(self, dst):
        self.done_count += 1
        self.last_output = dst
        self.outputs[self.worker.src] = dst
        self.dir_open_btn.setEnabled(True)
        self.set_item_status(self.worker.src, "完成")
        if self.worker.src == self.current_path:
            self._update_done_preview(self.current_path)
        self._set_progress_color("#176b3a")
        self._progress_target = 100
        self.progress.setValue(100)

    def _on_one_failed(self, msg):
        mark = "已取消" if msg.strip() == "已取消" else "失败"
        self.set_item_status(self.worker.src, mark)
        if mark == "失败":
            tail = msg.strip().splitlines()[-1] if msg.strip() else "未知原因"
            self.set_state("ERROR", f"转换失败：{tail[:100]}")
            print(f"[转换失败] {self.worker.src}\n{msg.strip()}", flush=True)
        # 失败/取消不顶满进度条：停在真实进度，与"完成"（绿色 100%）区分
        self._set_progress_color("#b3261e")

    def _on_worker_finished(self):
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        self._process_next()

    def _restore_controls(self):
        self._progress_timer.stop()
        self.convert_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)