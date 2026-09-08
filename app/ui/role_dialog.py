from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ..core import config as config_mod
from ..core.models import CATEGORIES, RoleMeta, subtype_options
from ..core.pipeline import NewRoleDraft, PipelineError, build_role, preview
from .workers import run_in_thread


class RoleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建角色")
        self.setModal(True)
        self.resize(620, 560)
        self.result_meta: RoleMeta | None = None
        self._files: list[str] = []
        self._busy = False

        root = QVBoxLayout(self)

        # ---- 基本信息 ----
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.display_edit = QLineEdit()
        self.display_edit.setPlaceholderText("给对方起的显示名（默认取对方名字）")

        self.category_combo = QComboBox()
        for label, value in CATEGORIES.items():
            self.category_combo.addItem(label, value)
        self.category_combo.currentIndexChanged.connect(self._update_subtype)

        self.subtype_combo = QComboBox()
        self._update_subtype()

        self.alias_edit = QLineEdit()
        self.alias_edit.setPlaceholderText("如：Joanna —— 对方在聊天导出里显示的名字")

        self.me_edit = QLineEdit()
        self.me_edit.setPlaceholderText("留空自动识别为记录里的另一方")

        form.addRow("显示名", self.display_edit)
        form.addRow("关系类别", self.category_combo)
        form.addRow("", self.subtype_combo)
        form.addRow("对方在记录里的名字", self.alias_edit)
        form.addRow("我的昵称(可选)", self.me_edit)
        root.addLayout(form)

        # ---- 文件 ----
        file_row = QHBoxLayout()
        add_btn = QPushButton("添加聊天记录文件…")
        add_btn.clicked.connect(self._on_add_files)
        rm_btn = QPushButton("移除选中")
        rm_btn.clicked.connect(self._on_remove_files)
        file_row.addWidget(add_btn)
        file_row.addWidget(rm_btn)
        file_row.addStretch(1)
        root.addLayout(file_row)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(90)
        root.addWidget(self.file_list)

        # ---- 预览与生成 ----
        btn_row = QHBoxLayout()
        self.preview_btn = QPushButton("解析预览")
        self.preview_btn.clicked.connect(self._on_preview)
        btn_row.addWidget(self.preview_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color:#445;")
        root.addWidget(self.status_label)

        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(110)
        self.log_area.setPlaceholderText("生成画像的进度会显示在这里…")
        root.addWidget(self.log_area)

        btn_row = QHBoxLayout()
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.generate_btn = QPushButton("创建并生成画像")
        self.generate_btn.setEnabled(False)
        self.generate_btn.clicked.connect(self._on_generate)
        btn_row.addStretch(1)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.generate_btn)
        root.addLayout(btn_row)

        # 变化即重置生成按钮
        for w in (self.category_combo, self.alias_edit, self.me_edit, self.display_edit):
            sig = w.textChanged if isinstance(w, QLineEdit) else w.currentIndexChanged
            sig.connect(lambda *_: self._invalidate())

    def reject(self) -> None:
        # 生成画像进行中不允许关闭（线程仍在跑）
        if self._busy:
            return
        super().reject()

    # ------------------------------------------------------------------
    def _update_subtype(self) -> None:
        category = self.category_combo.currentData()
        opts = subtype_options(category)
        self.subtype_combo.clear()
        if opts:
            for label, value in opts:
                self.subtype_combo.addItem(label, value)
        self.subtype_combo.setVisible(bool(opts))
        if not opts:
            # 给布局占位避免跳动（隐藏时保留）
            self.subtype_combo.setMaximumWidth(1)
        else:
            self.subtype_combo.setMaximumWidth(16777215)

    def _invalidate(self) -> None:
        self.generate_btn.setEnabled(False)
        self.status_label.setText("")

    def _draft(self) -> NewRoleDraft:
        category = self.category_combo.currentData()
        subtype = None
        if subtype_options(category):
            subtype = self.subtype_combo.currentData()
        display = self.display_edit.text().strip()
        return NewRoleDraft(
            display_name=display,
            category=category,
            subtype=subtype,
            alias=self.alias_edit.text().strip(),
            me_alias=self.me_edit.text().strip(),
            files=list(self._files),
        )

    # ------------------------------------------------------------------
    def _on_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择聊天记录文件", "", "聊天记录 (*.txt *.md *.log);;所有文件 (*)"
        )
        if not paths:
            return
        for p in paths:
            if p not in self._files:
                self._files.append(p)
                self.file_list.addItem(Path(p).name)
        self._invalidate()

    def _on_remove_files(self) -> None:
        for item in self.file_list.selectedItems():
            idx = self.file_list.row(item)
            self.file_list.takeItem(idx)
            self._files.pop(idx)
        self._invalidate()

    # ------------------------------------------------------------------
    def _on_preview(self) -> None:
        try:
            pv = preview(self._draft())
        except PipelineError as e:
            self.status_label.setText(str(e))
            self.generate_btn.setEnabled(False)
            return
        me = pv["me_alias"]
        if not self.me_edit.text().strip() and me:
            self.me_edit.setText(me)
        counts = "、".join(f"{k}×{v}" for k, v in sorted(pv["speaker_counts"].items(), key=lambda x: -x[1]))
        lines = [
            f"共 {pv['turn_count']} 条消息；说话人：{counts}",
            f"对方「{pv['subject_writename']}」发言 {pv['subject_count']} 条",
        ]
        if me:
            lines.append(f"「我」在记录里被识别为：{me}")
        if pv["third_parties"]:
            lines.append(f"⚠ 检测到第三方说话人（{'、'.join(pv['third_parties'])}）共 {pv['dropped_count']} 条，将被忽略。")
        if pv["subject_count"] <= 5:
            lines.append("提示：对方发言较少，画像可信度会偏低。")
        self.status_label.setText("\n".join(lines))
        self.generate_btn.setEnabled(True)

    # ------------------------------------------------------------------
    def _on_generate(self) -> None:
        if self._busy:
            return
        draft = self._draft()
        if not draft.files:
            QMessageBox.warning(self, "提示", "请先添加聊天记录文件。")
            return
        if not draft.alias:
            QMessageBox.warning(self, "提示", "请填写「对方在记录里的名字」。")
            return
        cfg = config_mod.load_config()
        if not cfg.is_configured():
            QMessageBox.information(self, "提示", "尚未配置模型。请先在主界面「设置」里填写 API Key 与模型名。")
            return

        self._busy = True
        self.generate_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.log_area.clear()
        self._log(f"开始为「{draft.display_name or draft.alias}」生成画像…")

        def task(progress):
            from ..core.config import make_client

            return build_role(make_client(), draft, progress_cb=progress)

        def on_progress(text: str) -> None:
            self._log(text)

        def on_done(meta: RoleMeta) -> None:
            self._log("创建成功，即将进入对话。")
            self._busy = False
            self.result_meta = meta
            self.accept()

        def on_fail(err: str) -> None:
            self._busy = False
            self.cancel_btn.setEnabled(True)
            self.preview_btn.setEnabled(True)
            self._log("失败：" + err)
            self.generate_btn.setEnabled(False)
            self.status_label.setText(f"生成失败：{err}")

        run_in_thread(task, on_done, on_fail, on_progress, parent=self.window())

    def _log(self, text: str) -> None:
        self.log_area.appendPlainText(text)
