from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QComboBox, QGroupBox, QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject

from app.core.config import load_config
from app.core.llm.registry import get_provider
from app.core.personality_analyzer import PersonalityAnalyzer, LLMCallConfig
from app.core.imitation_generator import ImitationGenerator
from app.core.evidence_parser import EvidenceSetup
from app.core.paths import PROFILES_DIR


class _Worker(QObject):
    log = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)


class _AnalysisWorker(_Worker):
    def __init__(self, setup: EvidenceSetup):
        super().__init__()
        self.setup = setup

    def run(self):
        try:
            cfg = load_config()
            if not cfg.api_key:
                raise RuntimeError("请先到「设置」Tab 填写 API Key")
            llm = get_provider(cfg.provider)
            analyzer = PersonalityAnalyzer(llm)
            llm_cfg = LLMCallConfig(
                api_key=cfg.api_key,
                model=cfg.model or None,
                base_url=cfg.base_url or None,
            )

            def cb(msg: str):
                self.log.emit(msg)

            path = analyzer.analyze(
                chat_turns=self.setup.turns,
                subject_alias=self.setup.subject_alias,
                llm_cfg=llm_cfg,
                subject_role=self.setup.subject_role,
                source_files=[Path(self.setup.file_path).name],
                progress_cb=cb,
            )
            self.finished_ok.emit(str(path))
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


class _GenSkillWorker(_Worker):
    def __init__(self, profile_path: str):
        super().__init__()
        self.profile_path = profile_path

    def run(self):
        try:
            gen = ImitationGenerator()
            def cb(msg: str):
                self.log.emit(msg)
            path = gen.generate(self.profile_path, progress_cb=cb)
            self.finished_ok.emit(str(path))
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


class _PreparationWorker(_Worker):
    def __init__(self, setup: EvidenceSetup):
        super().__init__()
        self.setup = setup

    def run(self):
        try:
            cfg = load_config()
            if not cfg.api_key:
                raise RuntimeError("请先到「设置」填写 API Key")
            llm = get_provider(cfg.provider)
            llm_cfg = LLMCallConfig(
                api_key=cfg.api_key,
                model=cfg.model or None,
                base_url=cfg.base_url or None,
            )
            self.log.emit("1/2 正在分析资料并生成关系画像...")
            profile_path = PersonalityAnalyzer(llm).analyze(
                chat_turns=self.setup.turns,
                subject_alias=self.setup.subject_alias,
                llm_cfg=llm_cfg,
                subject_role=self.setup.subject_role,
                source_files=[Path(self.setup.file_path).name],
                progress_cb=self.log.emit,
            )
            self.log.emit("2/2 正在整理对话风格...")
            skill_path = ImitationGenerator().generate(str(profile_path), progress_cb=self.log.emit)
            self.finished_ok.emit(str(skill_path))
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


class AnalysisTab(QWidget):
    skillGenerated = Signal(str)

    def __init__(self):
        super().__init__()
        self._setup: Optional[EvidenceSetup] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[_Worker] = None
        self._pending_profile: Optional[str] = None
        self._prepare_mode = False
        self._build_ui()
        self._refresh_profiles()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel("准备对话")
        title.setStyleSheet("font-size:18px; font-weight:600;")
        outer.addWidget(title)

        setup_box = QGroupBox("当前证据")
        sb = QVBoxLayout(setup_box)
        self.setup_label = QLabel("（在「证据管理」Tab 确认后会显示在这里）")
        self.setup_label.setStyleSheet("color:#6b7280;")
        sb.addWidget(self.setup_label)

        row = QHBoxLayout()
        self.analyze_btn = QPushButton("只生成关系画像")
        self.analyze_btn.clicked.connect(self._on_analyze)
        self.analyze_btn.setEnabled(False)
        row.addWidget(self.analyze_btn)
        row.addStretch(1)
        sb.addLayout(row)
        outer.addWidget(setup_box)

        self.prepare_btn = QPushButton("一键准备并开始对话")
        self.prepare_btn.setObjectName("primaryButton")
        self.prepare_btn.setToolTip("自动分析资料、生成技能，并在完成后打开对话")
        self.prepare_btn.clicked.connect(self._on_prepare)
        self.prepare_btn.setEnabled(False)
        outer.addWidget(self.prepare_btn)

        gen_box = QGroupBox("生成模仿 skill")
        gb = QVBoxLayout(gen_box)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("选择 profile.md:"))
        self.profile_combo = QComboBox()
        row2.addWidget(self.profile_combo, 1)
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self._on_browse_profile)
        row2.addWidget(self.browse_btn)
        self.refresh_profiles_btn = QPushButton("刷新")
        self.refresh_profiles_btn.clicked.connect(self._refresh_profiles)
        row2.addWidget(self.refresh_profiles_btn)
        gb.addLayout(row2)

        row3 = QHBoxLayout()
        self.gen_skill_btn = QPushButton("从画像生成对话风格")
        self.gen_skill_btn.clicked.connect(self._on_gen_skill)
        row3.addWidget(self.gen_skill_btn)
        row3.addStretch(1)
        gb.addLayout(row3)
        outer.addWidget(gen_box)

        outer.addWidget(QLabel("执行日志:"))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(320)
        self.log_view.setStyleSheet("font-family: 'SF Mono', Menlo, Consolas, monospace; font-size:12px;")
        outer.addWidget(self.log_view, 1)

    # ------------------ public API ------------------
    def set_evidence(self, setup: EvidenceSetup):
        self._setup = setup
        self.setup_label.setText(
            f"✅ 已就绪: 文件={Path(setup.file_path).name}  "
            f"用户别名={setup.user_alias}  "
            f"对象别名={setup.subject_alias}  "
            f"角色={setup.subject_role}  "
            f"turns={len(setup.turns)}"
        )
        self.analyze_btn.setEnabled(True)
        self.prepare_btn.setEnabled(True)

    def prepare_and_generate(self, setup: EvidenceSetup):
        self.set_evidence(setup)
        self._prepare_mode = False
        self.log_view.clear()
        self._log(f"[开始准备] {Path(setup.file_path).name}")
        self._start_worker(_PreparationWorker(setup))

    # ------------------ profile list ------------------
    def _refresh_profiles(self):
        self.profile_combo.clear()
        if not PROFILES_DIR.exists():
            return
        for f in sorted(PROFILES_DIR.iterdir()):
            if f.is_file() and f.name.endswith("_personality_profile.md"):
                self.profile_combo.addItem(f.name, str(f))

    def _on_browse_profile(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "选择 personality profile", str(PROFILES_DIR),
            "Markdown (*.md);;All (*.*)",
        )
        if f:
            self.profile_combo.addItem(Path(f).name, f)
            self.profile_combo.setCurrentIndex(self.profile_combo.count() - 1)

    def _current_profile(self) -> Optional[str]:
        idx = self.profile_combo.currentIndex()
        if idx < 0:
            return None
        return self.profile_combo.itemData(idx)

    # ------------------ run workers ------------------
    def _log(self, msg: str):
        self.log_view.appendPlainText(msg)

    def _start_worker(self, worker: _Worker):
        if self._thread is not None:
            QMessageBox.warning(self, "忙", "已有任务在运行，请等待结束")
            return
        self._thread = QThread(self)
        self._worker = worker
        worker.moveToThread(self._thread)
        self._thread.started.connect(worker.run)
        worker.log.connect(self._log)
        worker.finished_ok.connect(self._on_worker_ok)
        worker.failed.connect(self._on_worker_fail)
        worker.finished_ok.connect(self._thread.quit)
        worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()
        self.analyze_btn.setEnabled(False)
        self.gen_skill_btn.setEnabled(False)
        self.prepare_btn.setEnabled(False)

    def _cleanup_thread(self):
        if self._thread:
            self._thread.deleteLater()
        self._thread = None
        self._worker = None
        self.analyze_btn.setEnabled(self._setup is not None)
        self.gen_skill_btn.setEnabled(True)
        self.prepare_btn.setEnabled(self._setup is not None)
        if self._pending_profile:
            profile = self._pending_profile
            self._pending_profile = None
            self.log_view.appendPlainText("[继续] 正在生成 imitation skill...")
            self._start_worker(_GenSkillWorker(profile))

    def _on_worker_ok(self, result: str):
        self._log(f"✅ 完成: {result}")
        if "profile" in result and result.endswith(".md"):
            self._refresh_profiles()
            idx = self.profile_combo.findData(result)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
            if self._prepare_mode:
                self._pending_profile = result
        if "generated/skills" in result or "imitation-" in result:
            self.skillGenerated.emit(result)

    def _on_worker_fail(self, err: str):
        self._log(f"❌ 失败: {err}")
        QMessageBox.critical(self, "任务失败", err)

    # ------------------ buttons ------------------
    def _on_analyze(self):
        if self._setup is None:
            QMessageBox.warning(self, "提示", "请先在「证据管理」Tab 确认证据")
            return
        self.log_view.clear()
        self._log(f"[启动] 分析 {Path(self._setup.file_path).name}, alias={self._setup.subject_alias}")
        self._start_worker(_AnalysisWorker(self._setup))

    def _on_prepare(self):
        if self._setup is None:
            QMessageBox.warning(self, "提示", "请先在「资料」页选择并解析一份资料")
            return
        self._prepare_mode = True
        self.log_view.clear()
        self._log(f"[开始准备] {Path(self._setup.file_path).name}")
        self._start_worker(_AnalysisWorker(self._setup))

    def _on_gen_skill(self):
        profile = self._current_profile()
        if not profile:
            QMessageBox.warning(self, "提示", "请选择 profile.md")
            return
        self.log_view.clear()
        self._log(f"[启动] 生成 skill, profile={Path(profile).name}")
        self._start_worker(_GenSkillWorker(profile))
