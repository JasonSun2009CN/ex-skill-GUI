from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import config as config_mod
from ..core import paths, persona_store
from ..core.chat_session import ChatSession
from ..core.models import RoleMeta
from .avatar import Avatar
from .role_dialog import RoleDialog
from .settings_dialog import SettingsDialog
from .theme import Theme, apply_theme, get_theme
from .widgets import ChatInput, ChatView
from .workers import run_in_thread


class RoleListItem(QWidget):
    """侧边栏角色列表的自定义项。"""

    def __init__(self, meta: RoleMeta, theme: Theme | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.meta = meta
        self.theme = theme

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(10)

        self.avatar = Avatar(meta.display_name or meta.alias, meta.role_id, size=40)
        self.avatar.set_image_path(meta.avatar_path if meta.avatar_path else None)
        root.addWidget(self.avatar, 0, Qt.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self.name_label = QLabel(meta.display_name or meta.alias)
        self.name_label.setFont(QFont("PingFang SC", 13, QFont.Medium))
        self.name_label.setStyleSheet(f"color: {theme.text_primary if theme else '#1d1d1f'};")
        text_col.addWidget(self.name_label)

        self.sub_label = QLabel(meta.label())
        self.sub_label.setStyleSheet(f"color: {theme.text_muted if theme else '#8e8e93'}; font-size: 11px;")
        text_col.addWidget(self.sub_label)

        root.addLayout(text_col, 1)

        # 状态指示器
        self.status_dot = QLabel("●")
        self.status_dot.setFont(QFont("PingFang SC", 8))
        if meta.persona_status == "ready":
            self.status_dot.setStyleSheet("color: transparent;")
        elif meta.persona_status == "failed":
            self.status_dot.setStyleSheet(f"color: {theme.error if theme else '#ff3b30'};")
        else:
            self.status_dot.setStyleSheet(f"color: {theme.warning if theme else '#ff9500'};")
        root.addWidget(self.status_dot, 0, Qt.AlignVCenter)

    def set_theme(self, theme: Theme) -> None:
        self.name_label.setStyleSheet(f"color: {theme.text_primary};")
        self.sub_label.setStyleSheet(f"color: {theme.text_muted}; font-size: 11px;")
        if self.meta.persona_status == "failed":
            self.status_dot.setStyleSheet(f"color: {theme.error};")
        elif self.meta.persona_status == "pending":
            self.status_dot.setStyleSheet(f"color: {theme.warning};")


class GenerationPanel(QFrame):
    """侧边栏底部的画像生成状态面板。"""

    def __init__(self, display_name: str, theme: Theme | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {theme.card_bg if theme else '#ffffff'};
                border: 1px solid {theme.border if theme else '#d1d1d6'};
                border-radius: 10px;
            }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel(f"正在生成：{display_name}")
        title.setStyleSheet(f"color: {theme.text_primary if theme else '#1d1d1f'}; font-weight: 600;")
        header.addWidget(title)
        header.addStretch(1)
        root.addLayout(header)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            f"""
            QProgressBar {{
                background: {theme.divider if theme else '#e5e5ea'};
                border-radius: 3px;
                height: 6px;
            }}
            QProgressBar::chunk {{
                background: {theme.accent if theme else '#0d9488'};
                border-radius: 3px;
            }}
            """
        )
        root.addWidget(self.progress)

        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumBlockCount(100)
        self.log_area.setFixedHeight(80)
        root.addWidget(self.log_area)

    def append_log(self, text: str) -> None:
        self.log_area.appendPlainText(text)

    def set_done(self, success: bool, theme: Theme) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1 if success else 0)
        if not success:
            self.progress.setStyleSheet(
                f"""
                QProgressBar {{ background: {theme.divider}; border-radius: 3px; height: 6px; }}
                QProgressBar::chunk {{ background: {theme.error}; border-radius: 3px; }}
                """
            )


class ChatPanel(QWidget):
    """单个角色的聊天面板：头部 + 消息区 + 输入。"""

    def __init__(self, meta: RoleMeta, theme: Theme, parent=None):
        super().__init__(parent)
        self.meta = meta
        self.theme = theme
        self.session: ChatSession | None = None
        self._busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 头部
        self.head = QFrame()
        hl = QHBoxLayout(self.head)
        hl.setContentsMargins(16, 10, 16, 10)

        self.avatar = Avatar(meta.display_name or meta.alias, meta.role_id, size=36)
        self.avatar.set_image_path(meta.avatar_path if meta.avatar_path else None)
        hl.addWidget(self.avatar)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title = QLabel(meta.display_name)
        self.title.setFont(QFont("PingFang SC", 15, QFont.Medium))
        title_col.addWidget(self.title)

        self.sub = QLabel(f"{meta.label()} · 记录中对方：{meta.alias}｜我：{meta.me_alias or '我'}")
        title_col.addWidget(self.sub)
        hl.addLayout(title_col, 1)
        root.addWidget(self.head)

        # 聊天视图
        self.view = ChatView(meta=meta, theme=theme)
        root.addWidget(self.view, 1)

        # 状态提示
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.hide()
        root.addWidget(self.status)

        # 输入区
        self.input_frame = QFrame()
        in_row = QHBoxLayout(self.input_frame)
        in_row.setContentsMargins(16, 10, 16, 12)
        in_row.setSpacing(10)

        self.input = ChatInput()
        self.input.setPlaceholderText(f"对「{meta.display_name}」说点什么…")
        self.input.send_clicked.connect(self._send)
        in_row.addWidget(self.input, 1)

        send_btn = QPushButton("发送")
        send_btn.setFixedSize(64, 36)
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.clicked.connect(self._send)
        in_row.addWidget(send_btn, 0, Qt.AlignBottom)
        root.addWidget(self.input_frame)

        self._apply_styles()

        persona = persona_store.load_persona(meta.role_id)
        if persona:
            self.session = ChatSession(config_mod.make_client(), meta, persona)
        else:
            self.input.setEnabled(False)
            self.status.setText("该角色还没有可用画像（可能生成失败或数据缺失），请删除后重新创建。")
            self.status.show()
        self._load_history()

    def _apply_styles(self) -> None:
        t = self.theme
        self.head.setStyleSheet(
            f"QFrame {{ background: {t.window_bg}; border-bottom: 1px solid {t.divider}; }}"
        )
        self.input_frame.setStyleSheet(
            f"QFrame {{ background: {t.window_bg}; border-top: 1px solid {t.divider}; }}"
        )
        self.title.setStyleSheet(f"color: {t.text_primary};")
        self.sub.setStyleSheet(f"color: {t.text_muted}; font-size: 11px;")
        self.status.setStyleSheet(f"color: {t.error}; font-size: 12px; padding: 4px 16px;")

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.view.set_theme(theme)
        self._apply_styles()

    def _load_history(self) -> None:
        for h in persona_store.read_history(self.meta.role_id):
            self.view.add_message(h["role"], h["content"], h.get("ts"))

    def set_status(self, text: str) -> None:
        if text:
            self.status.setText(text)
            self.status.show()
        else:
            self.status.hide()

    def _send(self) -> None:
        if self._busy or self.session is None:
            return
        text = self.input.text_value()
        if not text:
            return
        self.input.clear_input()
        ts = persona_store.now_iso()
        self.view.add_message("user", text, ts)
        self._set_busy(True)
        self.view.show_typing()

        def task(progress):
            return self.session.send(text)

        def on_done(reply) -> None:
            try:
                self.view.hide_typing()
                self._set_busy(False)
                if reply:
                    self.view.add_message("assistant", reply)
            except RuntimeError:
                pass

        def on_fail(err: str) -> None:
            try:
                self.view.hide_typing()
                self._set_busy(False)
                self.set_status(f"回复失败：{err}")
            except RuntimeError:
                pass

        run_in_thread(task, on_done, on_fail, parent=self.window())

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.input.setEnabled(not busy)
        self.set_status("对方正在回复…" if busy else "")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = config_mod.load_config()
        self.theme = get_theme(self.cfg.theme_mode)

        self.setWindowTitle("ex-skill 角色聊天")
        self.resize(1080, 720)

        self._panels: dict[str, ChatPanel] = {}
        self._current_role_id: str | None = None
        self._generation_panel: GenerationPanel | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 左侧边栏 ----
        self.sidebar = QWidget()
        self.sidebar.setMinimumWidth(200)
        self.sidebar.setMaximumWidth(400)
        self.sidebar.setFixedWidth(max(200, min(400, self.cfg.sidebar_width)))
        self.sidebar.setStyleSheet(f"background: {self.theme.sidebar_bg};")
        sv = QVBoxLayout(self.sidebar)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)

        # 顶部工具栏
        self.toolbar = QFrame()
        thl = QHBoxLayout(self.toolbar)
        thl.setContentsMargins(12, 10, 12, 10)

        self.app_title = QLabel("我的角色")
        self.app_title.setFont(QFont("PingFang SC", 15, QFont.Bold))
        thl.addWidget(self.app_title)
        thl.addStretch(1)

        settings_btn = QPushButton("设置")
        settings_btn.setObjectName("toolButton")
        settings_btn.setFixedSize(48, 30)
        settings_btn.clicked.connect(self._on_settings)
        thl.addWidget(settings_btn)

        new_btn = QPushButton("＋")
        new_btn.setObjectName("toolButton")
        new_btn.setToolTip("新建角色")
        new_btn.setFixedSize(30, 30)
        new_btn.clicked.connect(self._on_new_role)
        thl.addWidget(new_btn)
        sv.addWidget(self.toolbar)
        self._style_sidebar_chrome()

        # 角色列表
        self.role_list = QListWidget()
        self.role_list.setSpacing(2)
        self.role_list.itemClicked.connect(self._on_select_role)
        self.role_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.role_list.customContextMenuRequested.connect(self._on_context_menu)
        sv.addWidget(self.role_list, 1)

        # 生成状态面板占位
        self.generation_container = QWidget()
        gvl = QVBoxLayout(self.generation_container)
        gvl.setContentsMargins(10, 10, 10, 10)
        sv.addWidget(self.generation_container)
        self.generation_container.hide()

        # ---- 右侧内容区 ----
        self.stack = QStackedWidget()
        self.empty = QLabel(
            "还没有角色。\n\n"
            "点击左上角「＋」新建一个角色：选关系、导入聊天记录，生成画像后就能和它聊天了。\n\n"
            "聊天记录与画像都保存在本机（~/.ex-skill）。"
        )
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet(f"color: {self.theme.text_muted}; font-size: 14px; background: {self.theme.chat_bg};")
        self.stack.addWidget(self.empty)

        # 可拖拽分隔
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.stack)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setHandleWidth(1)
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        root.addWidget(self.splitter, 1)

        # 侧边栏宽度持久化防抖
        self._sidebar_save_timer = QTimer(self)
        self._sidebar_save_timer.setSingleShot(True)
        self._sidebar_save_timer.setInterval(500)
        self._sidebar_save_timer.timeout.connect(self._persist_sidebar_width)

        paths.ensure_layout()
        self._reload_roles()
        if not self.cfg.is_configured():
            self.empty.setText(
                self.empty.text() + "\n\n提示：首次使用请先在「设置」里填写 API Key 与模型名。"
            )

        # 定时检查系统主题变化
        self._theme_check_timer = QTimer(self)
        self._theme_check_timer.timeout.connect(self._check_system_theme)
        if self.cfg.theme_mode == "system":
            self._theme_check_timer.start(2000)
        self._last_system_dark = self.theme.is_dark

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------
    def _style_sidebar_chrome(self) -> None:
        """更新侧边栏容器 / 工具栏 / 标题的配色（主题切换时调用）。"""
        t = self.theme
        self.sidebar.setStyleSheet(f"background: {t.sidebar_bg};")
        self.toolbar.setStyleSheet(
            f"background: {t.sidebar_bg}; border-bottom: 1px solid {t.divider};"
        )
        self.app_title.setStyleSheet(f"color: {t.text_primary};")

    def apply_current_theme(self) -> None:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self.theme)
        self._style_sidebar_chrome()
        self._reload_roles()
        for panel in self._panels.values():
            panel.set_theme(self.theme)
        self._update_empty_style()

    def _update_empty_style(self) -> None:
        self.empty.setStyleSheet(f"color: {self.theme.text_muted}; font-size: 14px; background: {self.theme.chat_bg};")

    def _check_system_theme(self) -> None:
        from .theme import system_is_dark
        is_dark = system_is_dark()
        if is_dark != self._last_system_dark:
            self._last_system_dark = is_dark
            self.theme = get_theme("system")
            self.apply_current_theme()

    # ------------------------------------------------------------------
    # 角色列表
    # ------------------------------------------------------------------
    def _reload_roles(self) -> None:
        self.role_list.clear()
        for meta in persona_store.list_roles():
            item = QListWidgetItem()
            item.setData(Qt.UserRole, meta.role_id)
            widget = RoleListItem(meta, theme=self.theme)
            item.setSizeHint(widget.sizeHint())
            self.role_list.addItem(item)
            self.role_list.setItemWidget(item, widget)
        # 重建选择
        if self._current_role_id:
            for i in range(self.role_list.count()):
                if self.role_list.item(i).data(Qt.UserRole) == self._current_role_id:
                    self.role_list.setCurrentRow(i)
                    break

    def _selected_role_id(self) -> str | None:
        item = self.role_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _on_select_role(self, item: QListWidgetItem) -> None:
        role_id = item.data(Qt.UserRole)
        self._open_role(role_id)

    def _open_role(self, role_id: str) -> None:
        meta = persona_store.get_role(role_id)
        if meta is None:
            return
        self._current_role_id = role_id
        panel = self._panels.get(role_id)
        if panel is None:
            panel = ChatPanel(meta, self.theme, self)
            self._panels[role_id] = panel
            self.stack.addWidget(panel)
        self.stack.setCurrentWidget(panel)

    # ------------------------------------------------------------------
    # 新建角色
    # ------------------------------------------------------------------
    def _on_new_role(self) -> None:
        dlg = RoleDialog(self.theme, self)
        if dlg.exec() and dlg.result_meta and dlg.result_draft:
            meta = dlg.result_meta
            draft = dlg.result_draft
            # 如果有头像文件待保存
            if dlg.pending_avatar_path:
                try:
                    persona_store.save_avatar(meta.role_id, dlg.pending_avatar_path)
                    meta.avatar_path = str(persona_store.avatar_path(meta.role_id))
                    persona_store.upsert_role(meta)
                except Exception as e:
                    QMessageBox.warning(self, "头像保存失败", f"角色已创建，但头像保存失败：{e}")
            self._reload_roles()
            # 定位新角色
            rid = meta.role_id
            for i in range(self.role_list.count()):
                if self.role_list.item(i).data(Qt.UserRole) == rid:
                    self.role_list.setCurrentRow(i)
                    break
            # 开始生成画像
            self._start_generation(draft, meta)

    def _start_generation(self, draft, meta: RoleMeta) -> None:
        cfg = config_mod.load_config()
        if not cfg.is_configured():
            QMessageBox.information(self, "提示", "尚未配置模型。请先在「设置」里填写 API Key 与模型名。")
            return

        display_name = draft.display_name or draft.alias
        role_id = meta.role_id
        # 显示生成面板
        if self._generation_panel is not None:
            self._generation_panel.deleteLater()
        self._generation_panel = GenerationPanel(display_name, self.theme)
        layout = self.generation_container.layout()
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        layout.addWidget(self._generation_panel)
        self.generation_container.show()

        def task(progress):
            from ..core.config import make_client
            from ..core.pipeline import build_role

            return build_role(make_client(), draft, progress_cb=progress)

        def on_progress(text: str) -> None:
            if self._generation_panel is not None:
                self._generation_panel.append_log(text)

        def on_done(updated_meta: RoleMeta) -> None:
            if self._generation_panel is not None:
                self._generation_panel.set_done(True, self.theme)
                self._generation_panel.append_log("生成完成")
            self._reload_roles()
            self._open_role(updated_meta.role_id)
            QTimer.singleShot(1500, self._hide_generation_panel)

        def on_fail(err: str) -> None:
            if self._generation_panel is not None:
                self._generation_panel.set_done(False, self.theme)
                self._generation_panel.append_log(f"失败：{err}")
            # 标记失败
            m = persona_store.get_role(role_id)
            if m:
                m.persona_status = "failed"
                persona_store.upsert_role(m)
            self._reload_roles()

        run_in_thread(task, on_done, on_fail, on_progress, parent=self.window())

    def _hide_generation_panel(self) -> None:
        if self._generation_panel is not None:
            self._generation_panel.deleteLater()
            self._generation_panel = None
        self.generation_container.hide()

    # ------------------------------------------------------------------
    # 设置
    # ------------------------------------------------------------------
    def _on_settings(self) -> None:
        dlg = SettingsDialog(self.theme, self)
        if dlg.exec():
            self.cfg = config_mod.load_config()
            self.theme = get_theme(self.cfg.theme_mode)
            self.apply_current_theme()
            if self.cfg.theme_mode == "system":
                self._theme_check_timer.start(2000)
            else:
                self._theme_check_timer.stop()
            if self.cfg.is_configured() and not persona_store.list_roles():
                self.empty.setText(
                    "还没有角色。\n\n"
                    "点击左上角「＋」新建一个角色：选关系、导入聊天记录，生成画像后就能和它聊天了。\n\n"
                    "聊天记录与画像都保存在本机（~/.ex-skill）。"
                )
                self._update_empty_style()

    # ------------------------------------------------------------------
    # 上下文菜单 / 删除
    # ------------------------------------------------------------------
    def _on_context_menu(self, pos) -> None:
        item = self.role_list.itemAt(pos)
        if item is None:
            return
        role_id = item.data(Qt.UserRole)
        meta = persona_store.get_role(role_id)
        if meta is None:
            return

        menu = QMenu(self)
        upload_avatar = QAction("更换头像", self)
        upload_avatar.triggered.connect(lambda: self._on_upload_avatar(role_id))
        menu.addAction(upload_avatar)

        remove_avatar = QAction("移除头像", self)
        remove_avatar.triggered.connect(lambda: self._on_remove_avatar(role_id))
        remove_avatar.setEnabled(bool(meta.avatar_path) or persona_store.has_avatar(role_id))
        menu.addAction(remove_avatar)

        menu.addSeparator()

        del_action = QAction("删除该角色", self)
        del_action.triggered.connect(lambda: self._on_delete_role(role_id))
        menu.addAction(del_action)
        menu.exec(self.role_list.viewport().mapToGlobal(pos))

    def _on_upload_avatar(self, role_id: str) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self, "选择头像", "", "图片 (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        try:
            # 在 UI 层用 QImage 裁剪缩放
            from PySide6.QtGui import QImage

            img = QImage(path)
            if img.isNull():
                raise ValueError("无法读取图片")
            size = min(img.width(), img.height())
            x = (img.width() - size) // 2
            y = (img.height() - size) // 2
            cropped = img.copy(x, y, size, size)
            scaled = cropped.scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            tmp_path = persona_store.role_dir(role_id) / "avatar_tmp.png"
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            if not scaled.save(str(tmp_path), "PNG"):
                raise ValueError("保存头像失败")
            persona_store.save_avatar(role_id, tmp_path)
            tmp_path.unlink(missing_ok=True)

            meta = persona_store.get_role(role_id)
            if meta:
                meta.avatar_path = str(persona_store.avatar_path(role_id))
                persona_store.upsert_role(meta)
            self._reload_roles()
            if self._current_role_id == role_id:
                self._open_role(role_id)
        except Exception as e:
            QMessageBox.warning(self, "头像上传失败", str(e))

    def _on_remove_avatar(self, role_id: str) -> None:
        persona_store.remove_avatar(role_id)
        meta = persona_store.get_role(role_id)
        if meta:
            meta.avatar_path = ""
            persona_store.upsert_role(meta)
        self._reload_roles()
        if self._current_role_id == role_id:
            self._open_role(role_id)

    def _on_delete_role(self, role_id: str) -> None:
        meta = persona_store.get_role(role_id)
        if meta is None:
            return
        ret = QMessageBox.question(
            self,
            "删除角色",
            f"确定删除角色「{meta.display_name}」吗？\n其聊天记录与画像将从本机删除，无法恢复。",
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        persona_store.delete_role(role_id)
        panel = self._panels.pop(role_id, None)
        if panel is not None:
            self.stack.removeWidget(panel)
            panel.deleteLater()
        if self._current_role_id == role_id:
            self._current_role_id = None
        self._reload_roles()
        if self.stack.count() == 1:
            self.stack.setCurrentWidget(self.empty)

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------
    def _on_splitter_moved(self, _pos: int, _idx: int) -> None:
        width = self.sidebar.width()
        if 200 <= width <= 400:
            self.cfg.sidebar_width = width
            self._sidebar_save_timer.start()

    def _persist_sidebar_width(self) -> None:
        try:
            config_mod.save_config(self.cfg)
        except Exception:
            pass
