#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件监听脚本：监听 content 目录的 Markdown 变化，自动重新预处理
检测到文件变化后，等待短暂延迟再处理，转化文件中的 Obsidian 图片链接
"""
import time
import sys
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 添加 scripts 目录到 Python 路径
script_dir = Path(__file__).parent
PROJECT_ROOT = script_dir.parent.resolve()
CONTENT_DIR = PROJECT_ROOT / 'content'

sys.path.insert(0, str(script_dir))

try:
    from preprocess_obsidian import preprocess_content_dir
except ImportError:
    print("错误: 无法导入 preprocess_obsidian 模块")
    sys.exit(1)

class MarkdownChangeHandler(FileSystemEventHandler):
    """监听 Markdown 变化并触发预处理"""

    def __init__(self, delay=1.0, base_path=None):
        self.delay = delay
        self.timer = None
        self.lock = threading.Lock()
        self.base_path = Path(base_path or CONTENT_DIR).resolve()

    def _log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def _process_changes(self):
        """处理文件变化：转化图片链接并更新临时目录"""
        with self.lock:
            self._log("检测到 Markdown 文件变化，开始预处理...")
            preprocess_content_dir(force=False)
            self._log("✓ 预处理完成\n")

    def _schedule_processing(self):
        """延迟调度处理，合并短时间内的多次事件"""
        with self.lock:
            # 取消之前的定时器
            if self.timer:
                self.timer.cancel()
            
            # 创建新的定时器，delay秒后执行
            self.timer = threading.Timer(self.delay, self._process_changes)
            self.timer.start()
    
    def _should_process(self, event):
        """判断是否应该处理 content 目录的事件"""
        if event.is_directory:
            return False
        
        # 只处理 Markdown 文件
        if not event.src_path.endswith('.md'):
            return False
        
        try:
            Path(event.src_path).resolve().relative_to(self.base_path)
            return True
        except ValueError:
            return False
    
    def on_created(self, event):
        """处理文件创建事件"""
        if self._should_process(event):
            self._schedule_processing()
    
    def on_modified(self, event):
        """处理文件修改事件"""
        if self._should_process(event):
            self._schedule_processing()
    
    def on_moved(self, event):
        """处理文件移动/重命名事件"""
        # 检查目标文件（新位置）
        if hasattr(event, 'dest_path') and event.dest_path:
            # 创建一个模拟事件来检查目标文件
            class MockEvent:
                def __init__(self, path):
                    self.src_path = path
                    self.is_directory = False
            mock_event = MockEvent(event.dest_path)
            if self._should_process(mock_event):
                self._schedule_processing()

    def on_deleted(self, event):
        """处理文件删除事件"""
        if self._should_process(event):
            self._schedule_processing()

def watch_content_dir(content_dir='content'):
    """
    监听 content 目录的变化
    当 Markdown 文件变化时，等待 delay 秒后自动重新预处理并转化图片链接
    """
    # 确保路径相对于项目根目录
    content_path = Path(content_dir).resolve() if content_dir != 'content' else CONTENT_DIR
    
    if not content_path.exists():
        print(f"错误: 内容目录不存在: {content_path}")
        sys.exit(1)
    
    print(f"\n开始监听目录:")
    print(f"  - {content_path} (Markdown 文件)")
    print("检测到文件变化后，等待1秒再处理...")
    print("按 Ctrl+C 停止监听\n")
    
    # 创建事件处理器和观察者
    content_handler = MarkdownChangeHandler(delay=1.0, base_path=content_path)
    
    observer = Observer()
    observer.schedule(content_handler, str(content_path), recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止监听...")
        # 取消待处理的定时器
        with content_handler.lock:
            if content_handler.timer:
                content_handler.timer.cancel()
        observer.stop()
    
    observer.join()

if __name__ == '__main__':
    # 检查是否安装了 watchdog
    try:
        import watchdog
    except ImportError:
        print("错误: 需要安装 watchdog 库")
        print("运行: pip install watchdog")
        sys.exit(1)
    
    watch_content_dir()

