"""视频预览播放器：独立对话框，用系统解码能力播放选中的视频。"""

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)


class PreviewDialog(QDialog):
    """弹窗播放视频：播放/暂停 + 错误兜底提示（解码不支持的容器）。"""

    def __init__(self, path, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"预览 · {title}")
        self.resize(760, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.video = QVideoWidget()
        self.video.setObjectName("playerSurface")
        root.addWidget(self.video, 1)

        bar_wrap = QWidget()
        bar_wrap.setObjectName("playerBar")
        bar = QHBoxLayout(bar_wrap)
        bar.setContentsMargins(14, 8, 14, 8)
        bar.setSpacing(12)
        self.play_btn = QPushButton("暂停")
        self.play_btn.setObjectName("ghostBtn")
        self.play_btn.clicked.connect(self._toggle_play)
        self.hint = QLabel("正在加载…")
        self.hint.setObjectName("playerHint")
        bar.addWidget(self.play_btn)
        bar.addWidget(self.hint, 1)
        root.addWidget(bar_wrap)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.errorOccurred.connect(self._on_error)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_state(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setText("暂停")
            self.hint.setText("正在播放")
        elif state == QMediaPlayer.StoppedState:
            self.play_btn.setText("重新播放")
            self.hint.setText("播放结束")

    def _on_error(self, *_args):
        self.play_btn.setEnabled(False)
        self.hint.setText("无法预览此格式，可在文件管理器中双击用系统播放器打开")

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)