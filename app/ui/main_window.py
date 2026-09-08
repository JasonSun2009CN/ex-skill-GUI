from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel, QHBoxLayout

from app.ui.evidence_tab import EvidenceTab
from app.ui.analysis_tab import AnalysisTab
from app.ui.chat_tab import ChatTab
from app.ui.settings_tab import SettingsTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ex-skill · 关系风格对话助手")
        self.resize(1080, 760)

        self.setStyleSheet("""
            QMainWindow { background: #f4f8f7; }
            QTabWidget::pane {
                border: 1px solid #d9e7e3;
                border-radius: 12px;
                top: -1px;
                background: #ffffff;
            }
            QTabBar::tab {
                background: transparent;
                color: #58716d;
                padding: 11px 20px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                margin-right: 2px;
                font-size: 14px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #087f73;
                border-bottom: 3px solid #12a594;
            }
            QWidget { color: #19332f; }
            QLabel#appTitle { color: #123c36; font-size: 24px; font-weight: 700; }
            QLabel#appSubtitle { color: #66817b; font-size: 13px; }
            QGroupBox {
                border: 1px solid #d9e7e3;
                border-radius: 10px;
                margin-top: 12px;
                padding: 10px;
                font-weight: 600;
                background: #ffffff;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #315b54; background: #ffffff; }
            QPushButton {
                background: #ffffff;
                color: #24534b;
                border: 1px solid #bfd7d1;
                border-radius: 7px;
                padding: 8px 15px;
                min-height: 18px;
            }
            QPushButton:hover { background: #edf8f5; border-color: #12a594; }
            QPushButton:pressed { background: #d8f1eb; }
            QPushButton:disabled { color: #9aada8; background: #f2f6f5; border-color: #dfe9e6; }
            QPushButton#primaryButton { background: #0d9488; color: #ffffff; border-color: #0d9488; font-weight: 600; }
            QPushButton#primaryButton:hover { background: #087f73; }
            QLineEdit, QComboBox, QPlainTextEdit {
                background: #ffffff;
                border: 1px solid #c9ddd8;
                border-radius: 7px;
                padding: 7px 10px;
                selection-background-color: #a7e3d7;
                selection-color: #123c36;
            }
            QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
                border: 1px solid #12a594;
            }
            QListWidget {
                background: #ffffff;
                border: 1px solid #c9ddd8;
                border-radius: 7px;
            }
            QListWidget::item:selected {
                background: #dff4ef;
                color: #123c36;
            }
            QLabel { color: #24443f; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 18, 24, 22)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("ex-skill")
        title.setObjectName("appTitle")
        subtitle = QLabel("把资料整理成一段可以自然对话的关系风格")
        subtitle.setObjectName("appSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(QLabel("本地运行 · 资料不会上传"))
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.evidence_tab = EvidenceTab()
        self.analysis_tab = AnalysisTab()
        self.chat_tab = ChatTab()
        self.settings_tab = SettingsTab()

        self.tabs.addTab(self.evidence_tab, "1 资料")
        self.tabs.addTab(self.analysis_tab, "2 准备")
        self.tabs.addTab(self.chat_tab, "3 对话")
        self.tabs.addTab(self.settings_tab, "设置")

        root.addWidget(self.tabs)

        self.evidence_tab.evidenceReady.connect(self._on_evidence_ready)
        self.analysis_tab.skillGenerated.connect(self._on_skill_generated)

    def _on_evidence_ready(self, setup):
        self.analysis_tab.prepare_and_generate(setup)
        self.tabs.setCurrentIndex(1)

    def _on_skill_generated(self, skill_dir: str):
        self.chat_tab.notify_skill_generated(skill_dir)
        self.tabs.setCurrentIndex(2)
