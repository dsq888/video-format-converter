"""视频格式转换器 —— 入口。"""

import sys

from PySide6.QtWidgets import QApplication

from main_window import MainWindow


# 全局样式：对齐飞鼠格式官方 public/styles.css —— 奶油底 #f5f4f1、白卡片 + 2px 纯黑描边、
# 硬阴影 6px 6px 0 #111、深绯红强调 #bd334c、圆角 16px。
APP_STYLE = """
* { font-family: "Microsoft YaHei UI", "Segoe UI", Arial, sans-serif; }
QMainWindow {
    background:
        qradialgradient(cx:0.1, cy:0, radius:0.8, fx:0.1, fy:0,
            stop:0 rgba(255,224,228,0.85), stop:0.6 rgba(255,224,228,0)),
        qradialgradient(cx:1, cy:0.05, radius:0.72, fx:1, fy:0.05,
            stop:0 rgba(220,236,255,0.8), stop:0.58 rgba(220,236,255,0)),
        #f5f4f1;
}
QLabel { color: #111111; }

/* ---- 顶栏 ---- */
#eyebrow { font-size: 12px; font-weight: 800; color: #a62840; background: transparent; }
#appTitle { font-size: 24px; font-weight: 800; color: #111111; background: transparent; }

/* ---- 奶油工作台（硬阴影由代码里的 QGraphicsDropShadowEffect 实现） ---- */
#workspace {
    background: #fffdf8;
    border: 2px solid #111111;
    border-radius: 16px;
}

/* ---- 拖放区 ---- */
#dropPanel {
    background: #ffffff;
    border: 2px solid #111111;
    border-radius: 16px;
}
#dropEyebrow { font-size: 12px; font-weight: 800; color: #a62840; background: transparent; }
#dropTitle { font-size: 24px; font-weight: 800; color: #111111; background: transparent; }
#dropSub   { font-size: 13px; font-weight: 600; color: #555555; background: transparent; }

/* ---- 次按钮 ---- */
QPushButton#ghostBtn {
    background: #ffffff; color: #111111;
    border: 2px solid #111111; border-radius: 10px;
    padding: 5px 14px; font-size: 13px; font-weight: 800;
}
QPushButton#ghostBtn:hover { background: #ffe0e4; }
QPushButton#ghostBtn:pressed { background: #ffe0e4; }
QPushButton#ghostBtn:disabled { background: #d5d8de; color: #555b66; border-color: #d5d8de; }

/* ---- 主按钮 ---- */
QPushButton#primaryBtn {
    background: #bd334c; color: #ffffff;
    border: 2px solid #111111; border-radius: 12px;
    padding: 8px 20px; font-size: 15px; font-weight: 800;
}
QPushButton#primaryBtn:hover { background: #a62840; }
QPushButton#primaryBtn:pressed { background: #a62840; }
QPushButton#primaryBtn:disabled { background: #d5d8de; color: #555b66; border-color: #d5d8de; }

/* ---- 详情区（缩略图 + 信息 + 预览） ---- */
#detail {
    background: #ffffff;
    border: 2px solid #111111;
    border-radius: 16px;
}
#thumb {
    background: #f4f5f8; color: #555555;
    border: 1px dashed rgba(17,17,17,0.25); border-radius: 10px;
    font-size: 13px; font-weight: 600;
}
#info { background: transparent; color: #111111; font-size: 13px; font-weight: 600; }
#previewBtn {
    background: #ffffff; color: #111111;
    border: 2px solid #111111; border-radius: 10px;
    padding: 7px 12px; font-size: 13px; font-weight: 800;
}
#previewBtn:hover { background: #ffe0e4; }
#previewBtn:disabled { background: #d5d8de; color: #555b66; border-color: #d5d8de; }

/* ---- 文件列表（卡片式） ---- */
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { background: transparent; border: none; }
QListWidget::item:selected { background: transparent; }
#fileCard { background: #ffffff; border: 2px solid #111111; border-radius: 12px; }
#fileName { font-size: 14px; font-weight: 800; color: #111111; background: transparent; }
#fileMeta { font-size: 12px; font-weight: 500; color: #555555; background: transparent; }

/* ---- 滚动条 ---- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #d5d8de; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #b9bdc6; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

/* ---- 右侧控制面板 ---- */
#panel {
    background: #ffffff;
    border: 2px solid #111111;
    border-radius: 16px;
}

/* ---- 左侧转换队列卡片 ---- */
#queuePanel {
    background: #ffffff;
    border: 2px solid #111111;
    border-radius: 16px;
}
#fieldLabel { font-size: 13px; font-weight: 800; color: #111111; background: transparent; }

QComboBox {
    background: #ffffff; color: #111111;
    border: 2px solid #111111; border-radius: 10px;
    padding: 6px 10px; min-height: 22px;
    font-size: 14px; font-weight: 700;
}
QComboBox:hover { background: #ffe0e4; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView {
    background: #ffffff; color: #111111;
    border: 2px solid #111111; border-radius: 8px;
    selection-background-color: #ffe0e4; selection-color: #111111;
    outline: none; padding: 4px;
}

#dirEdit {
    background: #ffffff; color: #555555;
    border: 2px solid #111111; border-radius: 10px;
    padding: 6px 10px; font-size: 12px;
}
#hint { background: transparent; color: #555555; font-size: 12px; font-weight: 500; }

/* ---- 成品预览框 ---- */
#doneFrame {
    background: #1d1d1f; color: #9a9aa0;
    border: 2px solid #111111; border-radius: 12px;
    font-size: 12px; font-weight: 600;
}

/* ---- 分组分隔线 ---- */
#divider { background-color: #111111; border: none; }

/* ---- 进度条 ---- */
QProgressBar {
    background: #ffffff;
    border: 2px solid #111111; border-radius: 10px;
    height: 18px;
    text-align: center;
    font-size: 10px; font-weight: 700; color: #555555;
}
QProgressBar::chunk { border-radius: 7px; background: #bd334c; }

/* ---- 状态区（具体配色由 set_state 内联覆盖） ---- */
#statusBox {
    border: 2px solid #111111; border-radius: 12px;
    padding: 14px 18px; font-size: 13px; font-weight: 600;
}

/* ---- 预览播放器 ---- */
#playerSurface { background: #1d1d1f; }
#playerBar { background: #ffffff; border-top: 2px solid #111111; }
#playerHint { color: #555555; font-size: 12px; font-weight: 400; background: transparent; }
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("视频格式转换器")
    app.setStyleSheet(APP_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()