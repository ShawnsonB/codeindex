from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class _Handler(FileSystemEventHandler):
    def __init__(self, indexer, extensions: tuple[str, ...]):
        self._indexer = indexer
        self._extensions = extensions

    def _is_target(self, path: str) -> bool:
        return any(path.endswith(ext) for ext in self._extensions)

    def on_created(self, event):
        if not event.is_directory and self._is_target(event.src_path):
            self._indexer.index_file(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory and self._is_target(event.src_path):
            self._indexer.index_file(Path(event.src_path))

    def on_deleted(self, event):
        if not event.is_directory and self._is_target(event.src_path):
            self._indexer.delete_file(Path(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            if self._is_target(event.src_path):
                self._indexer.delete_file(Path(event.src_path))
            if self._is_target(event.dest_path):
                self._indexer.index_file(Path(event.dest_path))


class FileWatcher:
    def __init__(self, indexer, root: Path, extensions: tuple[str, ...] = (".cs",)):
        self._observer = Observer()
        self._observer.schedule(_Handler(indexer, extensions), str(root), recursive=True)

    def start(self):
        self._observer.start()

    def stop(self):
        self._observer.stop()
        self._observer.join()
