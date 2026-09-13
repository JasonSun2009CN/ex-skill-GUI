from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
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
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import config as config_mod
from ..core import paths, persona_store
from ..core.models import CATEGORIES, RoleMeta, make_role_id, subtype_options
from ..core.pipeline import NewRoleDraft, PipelineError, preview
from .avatar import Avatar
from .theme import Theme


class RoleDialog(QDialog):
    """新建角色分步骤向导：基本信息 → 文件 → 预览 → 创建。"""

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.setWindowTitle("新建角色")
        self.setModal(True)
        self.resize(640, 520)

        self.result_meta: RoleMeta | None = None
        self.result_draft: NewRoleDraft | None = None
        self.pending_avatar_path: str | None = None

        self._files: list[str] = []
        self._preview_data: dict | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 步骤标题栏
        header = QWidget()
        header.setStyleSheet(
            f"background: {theme.sidebar_bg}; border-bottom: 1px solid {theme.divider};"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 12, 20, 12)
        self.step_label = QLabel("步骤 1/3：基本信息")
        self.step_label.setFont(QFont("PingFang SC", 15, QFont.Bold))
        self.step_label.setStyleSheet(f"color: {theme.text_primary};")
        hl.addWidget(self.step_label)
        root.addWidget(header)

        # 步骤内容
        self.stack = QStackedWidget()
        self._build_step_basic()
        self._build_step_files()
        self._build_step_preview()
        root.addWidget(self.stack, 1)

        # 底部按钮
        footer = QWidget()
        footer.setStyleSheet(f"background: {theme.window_bg}; border-top: 1px solid {theme.divider};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 12, 20, 12)
        fl.addStretch(1)

        self.back_btn = QPushButton("上一步")
        self.back_btn.setObjectName("secondaryButton")
        self.back_btn.clicked.connect(self._go_back)
        fl.addWidget(self.back_btn)

        self.next_btn = QPushButton("下一步")
        self.next_btn.clicked.connect(self._go_next)
        fl.addWidget(self.next_btn)

        self.create_btn = QPushButton("创建并生成画像")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self._on_create)
        fl.addWidget(self.create_btn)
        root.addWidget(footer)

        self._update_buttons()

    # ------------------------------------------------------------------
    # 步骤 1：基本信息
    # ------------------------------------------------------------------
    def _build_step_basic(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 头像
        avatar_row = QHBoxLayout()
        avatar_row.addStretch(1)
        self.avatar_preview = Avatar("?", "?", size=80)
        avatar_row.addWidget(self.avatar_preview)
        avatar_btn = QPushButton("上传头像")
        avatar_btn.setObjectName("secondaryButton")
        avatar_btn.clicked.connect(self._on_upload_avatar)
        avatar_row.addWidget(avatar_btn)
        avatar_row.addStretch(1)
        layout.addLayout(avatar_row)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(12)

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
        layout.addLayout(form)
        layout.addStretch(1)

        # 更新头像预览
        self.display_edit.textChanged.connect(self._update_avatar_preview)
        self.alias_edit.textChanged.connect(self._update_avatar_preview)

        self.stack.addWidget(page)

    def _update_avatar_preview(self) -> None:
        name = self.display_edit.text().strip() or self.alias_edit.text().strip() or "?"
        self.avatar_preview.set_name(name)
        self.avatar_preview.set_seed(name)
        if self.pending_avatar_path:
            self.avatar_preview.set_image_path(self.pending_avatar_path)

    def _on_upload_avatar(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择头像", "", "图片 (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        self.pending_avatar_path = path
        self.avatar_preview.set_image_path(path)

    # ------------------------------------------------------------------
    # 步骤 2：文件
    # ------------------------------------------------------------------
    def _build_step_files(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        hint = QLabel("导入聊天记录文件（.txt / .md / .log），支持多选。")
        hint.setStyleSheet(f"color: {self.theme.text_muted}; font-size: 12px;")
        layout.addWidget(hint)

        file_row = QHBoxLayout()
        add_btn = QPushButton("添加文件…")
        add_btn.clicked.connect(self._on_add_files)
        rm_btn = QPushButton("移除选中")
        rm_btn.setObjectName("secondaryButton")
        rm_btn.clicked.connect(self._on_remove_files)
        file_row.addWidget(add_btn)
        file_row.addWidget(rm_btn)
        file_row.addStretch(1)
        layout.addLayout(file_row)

        self.file_list = QListWidget()
        layout.addWidget(self.file_list, 1)
        self.stack.addWidget(page)

    # ------------------------------------------------------------------
    # 步骤 3：预览
    # ------------------------------------------------------------------
    def _build_step_preview(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.preview_label = QLabel("点击「解析预览」查看聊天记录统计。")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 13px;")
        layout.addWidget(self.preview_label)

        preview_btn = QPushButton("解析预览")
        preview_btn.clicked.connect(self._on_preview)
        layout.addWidget(preview_btn, 0, Qt.AlignLeft)

        layout.addStretch(1)
        self.stack.addWidget(page)

    # ------------------------------------------------------------------
    # 导航
    # ------------------------------------------------------------------
    def _current_index(self) -> int:
        return self.stack.currentIndex()

    def _update_buttons(self) -> None:
        idx = self._current_index()
        self.back_btn.setVisible(idx > 0)
        self.next_btn.setVisible(idx < 2)
        self.create_btn.setVisible(idx == 2)
        self.create_btn.setEnabled(idx == 2 and self._preview_data is not None)

        labels = ["步骤 1/3：基本信息", "步骤 2/3：导入聊天记录", "步骤 3/3：预览与创建"]
        self.step_label.setText(labels[idx])

    def _go_next(self) -> None:
        idx = self._current_index()
        if idx == 0:
            if not self._validate_basic():
                return
        elif idx == 1:
            if not self._files:
                QMessageBox.warning(self, "提示", "请先添加聊天记录文件。")
                return
        self.stack.setCurrentIndex(idx + 1)
        self._update_buttons()

    def _go_back(self) -> None:
        idx = self._current_index()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_buttons()

    def _validate_basic(self) -> bool:
        if not self.alias_edit.text().strip():
            QMessageBox.warning(self, "提示", "请填写「对方在记录里的名字」。")
            return False
        return True

    # ------------------------------------------------------------------
    # 文件操作
    # ------------------------------------------------------------------
    def _on_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择聊天记录文件", "", "聊天记录 (*.txt *.md *.log);;所有文件 (*)"
        )
        for p in paths:
            if p not in self._files:
                self._files.append(p)
                self.file_list.addItem(Path(p).name)

    def _on_remove_files(self) -> None:
        for item in self.file_list.selectedItems():
            idx = self.file_list.row(item)
            self.file_list.takeItem(idx)
            if 0 <= idx < len(self._files):
                self._files.pop(idx)

    # ------------------------------------------------------------------
    # 预览
    # ------------------------------------------------------------------
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

    def _update_subtype(self) -> None:
        category = self.category_combo.currentData()
        opts = subtype_options(category)
        self.subtype_combo.clear()
        if opts:
            for label, value in opts:
                self.subtype_combo.addItem(label, value)
        self.subtype_combo.setVisible(bool(opts))

    def _on_preview(self) -> None:
        try:
            pv = preview(self._draft())
        except PipelineError as e:
            self.preview_label.setText(str(e))
            self.preview_label.setStyleSheet(f"color: {self.theme.error};")
            self._preview_data = None
            self.create_btn.setEnabled(False)
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

        self.preview_label.setText("\n".join(lines))
        self.preview_label.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 13px;")
        self._preview_data = pv
        self.create_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # 创建
    # ------------------------------------------------------------------
    def _on_create(self) -> None:
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

        # 创建 pending 状态的 RoleMeta
        meta = RoleMeta(
            role_id=make_role_id(draft.display_name or draft.alias),
            display_name=draft.display_name or draft.alias,
            category=draft.category,
            subtype=draft.subtype,
            alias=draft.alias,
            me_alias=draft.me_alias or (self._preview_data.get("me_alias") if self._preview_data else "") or "",
            source_files=[Path(f).name for f in draft.files],
            persona_status="pending",
        )
        paths.ensure_layout()
        persona_store.create_role(meta, "")

        self.result_meta = meta
        self.result_draft = draft
        self.accept()
