from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QFileDialog, QMessageBox, QGroupBox, QFormLayout,
    QComboBox, QPlainTextEdit,
)
from PySide6.QtCore import Qt, Signal

from app.core.paths import EVIDENCE_DIR
from app.core.evidence_parser import parse_file, label_turns, EvidenceSetup


class EvidenceTab(QWidget):
    evidenceReady = Signal(object)

    def __init__(self):
        super().__init__()
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel("准备资料")
        title.setStyleSheet("font-size:18px; font-weight:600;")
        outer.addWidget(title)

        hint = QLabel("把聊天记录放进 evidence/ 后刷新列表，选中一份资料并开始准备。\n"
                  "也可以直接添加文件；首次使用建议先到「设置」保存 API Key。")
        hint.setStyleSheet("color:#6b7280;")
        outer.addWidget(hint)

        top_row = QHBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(220)
        self.list_widget.itemSelectionChanged.connect(self._on_select)
        top_row.addWidget(self.list_widget, 1)

        btn_col = QVBoxLayout()
        self.add_btn = QPushButton("添加文件...")
        self.add_btn.clicked.connect(self._on_add)
        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.clicked.connect(self._refresh_list)
        self.open_dir_btn = QPushButton("打开 evidence/")
        self.open_dir_btn.clicked.connect(self._open_evidence_dir)
        btn_col.addWidget(self.add_btn)
        btn_col.addWidget(self.refresh_btn)
        btn_col.addWidget(self.open_dir_btn)
        btn_col.addStretch(1)
        top_row.addLayout(btn_col)
        outer.addLayout(top_row, 1)

        form_box = QGroupBox("别名 & 角色设置")
        form = QFormLayout(form_box)
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("用户(上传者)的昵称/备注，例如: 我 / 小明")
        self.subject_edit = QLineEdit()
        self.subject_edit.setPlaceholderText("分析对象的别名，例如: Joanna / 前任")
        self.role_combo = QComboBox()
        self.role_combo.addItems(["ex-partner", "partner", "friend", "family", "colleague", "other"])
        self.parse_btn = QPushButton("预览解析结果")
        self.parse_btn.clicked.connect(self._on_parse)
        form.addRow("用户别名:", self.user_edit)
        form.addRow("对象别名:", self.subject_edit)
        form.addRow("对象角色:", self.role_combo)
        outer.addWidget(form_box)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("解析结果预览...")
        self.preview.setMinimumHeight(180)
        outer.addWidget(QLabel("预览 (speaker / time / 内容前 80 字):"))
        outer.addWidget(self.preview, 1)

        self.confirm_btn = QPushButton("开始准备")
        self.confirm_btn.setObjectName("primaryButton")
        self.confirm_btn.clicked.connect(self._on_confirm)
        self.confirm_btn.setEnabled(False)
        outer.addWidget(self.confirm_btn)

        self._last_setup: Optional[EvidenceSetup] = None

    def _refresh_list(self):
        self.list_widget.clear()
        if not EVIDENCE_DIR.exists():
            EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        for f in sorted(EVIDENCE_DIR.iterdir()):
            if f.is_file() and f.suffix.lower() in {".txt", ".md", ".log"}:
                item = QListWidgetItem(f"{f.name}  ({f.stat().st_size} bytes)")
                item.setData(Qt.UserRole, str(f))
                self.list_widget.addItem(item)

    def _on_add(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择聊天记录文件", str(Path.home()),
            "Text / Markdown (*.txt *.md *.log);;All (*.*)",
        )
        for f in files:
            src = Path(f)
            dst = EVIDENCE_DIR / src.name
            try:
                dst.write_bytes(src.read_bytes())
            except Exception as e:
                QMessageBox.critical(self, "复制失败", f"{src}: {e}")
        self._refresh_list()

    def _open_evidence_dir(self):
        import sys, subprocess, os
        path = str(EVIDENCE_DIR)
        try:
            if sys.platform.startswith("darwin"):
                subprocess.Popen(["open", path])
            elif os.name == "nt":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.information(self, "路径", path)

    def _on_select(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        name = items[0].data(Qt.UserRole)
        p = Path(name).name
        stem = Path(name).stem
        if not self.subject_edit.text().strip():
            self.subject_edit.setText(stem)
        self.confirm_btn.setEnabled(True)

    def _selected_path(self) -> Optional[str]:
        items = self.list_widget.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.UserRole)

    def _on_parse(self):
        path = self._selected_path()
        if not path:
            QMessageBox.warning(self, "提示", "请先选择 evidence 列表里的一个文件")
            return
        turns = parse_file(path)
        if not turns:
            QMessageBox.warning(self, "解析失败", "没有解析到任何对话回合，请检查文件格式")
            self.preview.setPlainText("(空)")
            self.confirm_btn.setEnabled(False)
            return
        user_alias = self.user_edit.text().strip() or "user"
        subject_alias = self.subject_edit.text().strip() or "subject"
        labeled = label_turns(turns, subject_alias, user_alias)
        preview_lines = []
        for t in labeled[:10]:
            c = t.content.replace("\n", " / ")[:80]
            preview_lines.append(f"{t.speaker:8s}  {t.timestamp or '':8s}  {c}")
        preview_lines.append(f"\n... 共 {len(labeled)} 条 turn，labeled user={labeled.count('user') if False else sum(1 for t in labeled if t.speaker=='user')} subject={sum(1 for t in labeled if t.speaker=='subject')}")
        self.preview.setPlainText("\n".join(preview_lines))
        self._last_setup = EvidenceSetup(
            file_path=path,
            user_alias=user_alias,
            subject_alias=subject_alias,
            subject_role=self.role_combo.currentText(),
            turns=labeled,
        )
        self.confirm_btn.setEnabled(True)

    def _on_confirm(self):
        if not self._last_setup or self._last_setup.file_path != self._selected_path():
            self._on_parse()
        if not self._last_setup or not self._last_setup.turns:
            return
        if not self.subject_edit.text().strip():
            QMessageBox.warning(self, "提示", "请填写对象别名")
            return
        self.evidenceReady.emit(self._last_setup)
