from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from hugo_blog.paths import CONTENT_DIR
from hugo_blog.pipeline.export import preprocess_content_dir


class MarkdownChangeHandler(FileSystemEventHandler):
    def __init__(self, *, delay: float = 1.0, base_path: Path = CONTENT_DIR):
        self.delay = delay
        self.base_path = base_path.resolve()
        self.timer: threading.Timer | None = None
        self.lock = threading.Lock()

    def _log(self, message: str) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _process_changes(self) -> None:
        with self.lock:
            self._log("检测到 Markdown 文件变化，开始预处理...")
            preprocess_content_dir(force=False)
            self._log("预处理完成")

    def _schedule_processing(self) -> None:
        with self.lock:
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(self.delay, self._process_changes)
            self.timer.start()

    def _should_process(self, event) -> bool:
        if event.is_directory or not str(event.src_path).endswith(".md"):
            return False
        try:
            Path(event.src_path).resolve().relative_to(self.base_path)
            return True
        except ValueError:
            return False

    def on_created(self, event) -> None:
        if self._should_process(event):
            self._schedule_processing()

    def on_modified(self, event) -> None:
        if self._should_process(event):
            self._schedule_processing()

    def on_deleted(self, event) -> None:
        if self._should_process(event):
            self._schedule_processing()

    def on_moved(self, event) -> None:
        if hasattr(event, "dest_path") and str(event.dest_path).endswith(".md"):
            self._schedule_processing()


def watch_content_dir(content_dir: Path = CONTENT_DIR) -> None:
    content_path = content_dir.resolve()
    if not content_path.exists():
        raise SystemExit(f"内容目录不存在: {content_path}")

    print(f"开始监听目录: {content_path}")
    handler = MarkdownChangeHandler(base_path=content_path)
    observer = Observer()
    observer.schedule(handler, str(content_path), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    finally:
        with handler.lock:
            if handler.timer:
                handler.timer.cancel()
    observer.join()


def main() -> int:
    watch_content_dir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
