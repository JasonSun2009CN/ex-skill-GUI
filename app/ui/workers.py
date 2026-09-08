from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot


class Worker(QObject):
    """在子线程里执行 fn(progress)。progress 会转发为 progress 信号。"""

    progress = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[Callable[[str], None]], Any]):
        super().__init__()
        self._fn = fn

    @Slot()
    def run(self) -> None:
        try:
            result = self._fn(self.progress.emit)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.failed.emit(str(e) or type(e).__name__)
            return
        self.done.emit(result)


class _Relay(QObject):
    """驻留在 GUI 线程的小对象：把 worker 信号经排队连接转成普通回调执行。"""

    def __init__(
        self,
        on_done: Callable[[Any], None],
        on_fail: Callable[[str], None],
        on_progress: Callable[[str], None] | None,
        parent: QObject | None,
    ):
        super().__init__(parent)
        self._on_done = on_done
        self._on_fail = on_fail
        self._on_progress = on_progress

    @Slot(object)
    def done_slot(self, result: Any) -> None:
        self._on_done(result)

    @Slot(str)
    def fail_slot(self, err: str) -> None:
        self._on_fail(err)

    @Slot(str)
    def progress_slot(self, text: str) -> None:
        if self._on_progress:
            self._on_progress(text)


def run_in_thread(
    fn: Callable[[Callable[[str], None]], Any],
    on_done: Callable[[Any], None],
    on_fail: Callable[[str], None],
    on_progress: Callable[[str], None] | None = None,
    parent: QObject | None = None,
) -> QThread:
    """后台执行 fn(progress)；on_done/on_fail/on_progress 保证在 GUI 线程触发。

    返回持有的 QThread（调用方可保存引用或直接丢弃；线程结束即自动清理）。
    """
    thread = QThread(parent)
    worker = Worker(fn)
    worker.moveToThread(thread)

    relay = _Relay(on_done, on_fail, on_progress, parent)
    # 用对象属性保住 relay 引用，避免函数返回后被回收
    thread._relay = relay  # type: ignore[attr-defined]

    thread.started.connect(worker.run)
    worker.progress.connect(relay.progress_slot, Qt.QueuedConnection)
    worker.done.connect(relay.done_slot, Qt.QueuedConnection)
    worker.failed.connect(relay.fail_slot, Qt.QueuedConnection)

    # worker 一结束就停线程并清理（在 GUI 线程排队执行 quit/deleteLater 更稳妥）
    worker.done.connect(thread.quit, Qt.QueuedConnection)
    worker.failed.connect(thread.quit, Qt.QueuedConnection)
    thread.finished.connect(thread.deleteLater)
    thread.finished.connect(worker.deleteLater)

    thread.start()
    return thread
