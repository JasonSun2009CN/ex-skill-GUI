from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import config as config_mod
from ..core import paths, persona_store
from ..core.chat_session import ChatSession
from ..core.models import RoleMeta
from .role_dialog import RoleDialog
from .settings_dialog import SettingsDialog
from .widgets import ChatView
from .workers import run_in_thread


class ChatPanel(QWidget):
    """单个角色的聊天面板：头部 + 消息区 + 输入。"""

    def __init__(self, meta: RoleMeta, parent=None):
        super().__init__(parent)
        self.meta = meta
        self.session: ChatSession | None = None
        self._busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # 头部
        head = QHBoxLayout()
        title = QLabel(f"{meta.display_name}  ·  {meta.label()}")
        title.setStyleSheet("font-size:15px;font-weight:600;color:#19332f;")
        sub = QLabel(f"记录中的对方：{meta.alias}｜我：{meta.me_alias}")
        sub.setStyleSheet("color:#8aa;font-size:11px;")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(sub)
        root.addLayout(head)

        self.view = ChatView()
        root.addWidget(self.view, 1)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#c0532f;font-size:11px;")
        self.status.hide()
        root.addWidget(self.status)

        # 输入行
        in_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText(f"对「{meta.display_name}」说点什么…（Enter 发送）")
        self.input.returnPressed.connect(self._send)
        send_btn = QPushButton("发送")
        send_btn.clicked.connect(self._send)
        in_row.addWidget(self.input, 1)
        in_row.addWidget(send_btn)
        root.addLayout(in_row)

        persona = persona_store.load_persona(meta.role_id)
        if persona:
            self.session = ChatSession(config_mod.make_client(), meta, persona)
        else:
            self.input.setEnabled(False)
            self.status.setText("该角色还没有可用画像（可能生成失败或数据缺失），请删除后重新创建。")
            self.status.show()
        self._load_history()

    def _load_history(self) -> None:
        for h in persona_store.read_history(self.meta.role_id):
            self.view.add_message(h["role"], h["content"])

    def set_status(self, text: str) -> None:
        if text:
            self.status.setText(text)
            self.status.show()
        else:
            self.status.hide()

    # ------------------------------------------------------------------
    def _send(self) -> None:
        if self._busy or self.session is None:
            return
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.view.add_message("user", text)
        self._set_busy(True)
        self.view.show_typing()

        def task(progress):
            return self.session.send(text)  # type: ignore[union-attr]

        def on_done(reply) -> None:
            try:
                self.view.hide_typing()
                self._set_busy(False)
                if reply:
                    self.view.add_message("assistant", reply)
            except RuntimeError:
                pass  # 面板在请求期间被删除

        def on_fail(err: str) -> None:
            try:
                self.view.hide_typing()
                self._set_busy(False)
                self.set_status(f"回复失败：{err}")
            except RuntimeError:
                pass  # 面板在请求期间被删除

        run_in_thread(task, on_done, on_fail, parent=self.window())

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.input.setEnabled(not busy)
        self.set_status("对方正在回复…" if busy else "")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ex-skill 角色聊天")
        self.resize(980, 680)
        self._panels: dict[str, ChatPanel] = {}
        self._current_role_id: str | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 左侧角色列表 ----
        left = QWidget()
        left.setFixedWidth(240)
        left.setStyleSheet("background:#eef2f1;")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(8, 8, 8, 8)

        top = QHBoxLayout()
        app = QLabel("我的角色")
        app.setStyleSheet("font-size:14px;font-weight:600;")
        new_btn = QPushButton("＋")
        new_btn.setToolTip("新建角色")
        new_btn.setFixedSize(30, 30)
        new_btn.clicked.connect(self._on_new_role)
        settings_btn = QPushButton("设置")
        settings_btn.clicked.connect(self._on_settings)
        top.addWidget(app)
        top.addStretch(1)
        top.addWidget(settings_btn)
        top.addWidget(new_btn)
        lv.addLayout(top)

        self.role_list = QListWidget()
        self.role_list.itemClicked.connect(self._on_select_role)
        self.role_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.role_list.customContextMenuRequested.connect(self._on_context_menu)
        lv.addWidget(self.role_list, 1)
        root.addWidget(left)

        # ---- 右侧聊天区 / 空状态 ----
        self.stack = QStackedWidget()
        self.empty = QLabel("还没有角色。\n\n点击左侧「＋」新建一个角色：选关系、导入聊天记录，生成画像后就能和它聊天了。\n\n聊天记录与画像都保存在本机（~/.ex-skill）。")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("color:#8aa;font-size:13px;")
        self.stack.addWidget(self.empty)
        root.addWidget(self.stack, 1)

        paths.ensure_layout()
        self._reload_roles()
        cfg = config_mod.load_config()
        if not cfg.is_configured():
            self.empty.setText(
                self.empty.text()
                + "\n\n提示：首次使用请先在「设置」里填写 API Key 与模型名。"
            )

    # ------------------------------------------------------------------
    def _reload_roles(self) -> None:
        self.role_list.clear()
        for meta in persona_store.list_roles():
            item = QListWidgetItem(f"{meta.display_name}\n{meta.label()}")
            item.setData(Qt.UserRole, meta.role_id)
            item.setToolTip(f"记录中的对方：{meta.alias}")
            f = QFont()
            f.setPointSize(11)
            item.setFont(f)
            self.role_list.addItem(item)
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
            panel = ChatPanel(meta, self)
            self._panels[role_id] = panel
            self.stack.addWidget(panel)
        self.stack.setCurrentWidget(panel)

    # ------------------------------------------------------------------
    def _on_new_role(self) -> None:
        dlg = RoleDialog(self)
        if dlg.exec() and dlg.result_meta:
            self._reload_roles()
            # 定位并打开新角色
            rid = dlg.result_meta.role_id
            for i in range(self.role_list.count()):
                if self.role_list.item(i).data(Qt.UserRole) == rid:
                    self.role_list.setCurrentRow(i)
                    self._open_role(rid)
                    break

    def _on_settings(self) -> None:
        dlg = SettingsDialog(self)
        if dlg.exec():
            cfg = config_mod.load_config()
            if cfg.is_configured() and not persona_store.list_roles():
                self.empty.setText("还没有角色。\n\n点击左侧「＋」新建一个角色…\n\n聊天记录与画像都保存在本机（~/.ex-skill）。")
            # 已打开面板沿用旧 client 不影响；重新打开角色即可使用新配置

    def _on_context_menu(self, pos) -> None:
        item = self.role_list.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        del_action = QAction("删除该角色", self)
        del_action.triggered.connect(lambda: self._on_delete_role(item.data(Qt.UserRole)))
        menu.addAction(del_action)
        menu.exec(self.role_list.viewport().mapToGlobal(pos))

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
