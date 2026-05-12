"""
File tools — safe local file operations within a bounded root directory.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional


class FileTools:
    def __init__(self, root: str = "~/Documents"):
        self.root = Path(root).expanduser().resolve()
        if not self.root.exists():
            self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, path: str) -> Path:
        resolved = (self.root / path).resolve()
        if not str(resolved).startswith(str(self.root)):
            raise ValueError(f"Path escapes root directory: {path}")
        return resolved

    def list_dir(self, path: str = ".", show_hidden: bool = False) -> list[dict]:
        target = self._safe_path(path)
        if not target.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")
        results = []
        for item in sorted(target.iterdir()):
            if not show_hidden and item.name.startswith("."):
                continue
            stat = item.stat()
            results.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size_bytes": stat.st_size if item.is_file() else None,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "path": str(item.relative_to(self.root)),
            })
        return results

    def tree(self, path: str = ".", max_depth: int = 3) -> str:
        target = self._safe_path(path)
        lines = [str(target.relative_to(self.root)) + "/"]
        self._build_tree(target, "", max_depth, 0, lines)
        return "\n".join(lines)

    def _build_tree(self, directory: Path, prefix: str, max_depth: int, depth: int, lines: list):
        if depth >= max_depth:
            return
        items = sorted(
            [i for i in directory.iterdir() if not i.name.startswith(".")],
            key=lambda x: (x.is_file(), x.name.lower()),
        )
        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{item.name}")
            if item.is_dir():
                extension = "    " if is_last else "│   "
                self._build_tree(item, prefix + extension, max_depth, depth + 1, lines)

    def file_info(self, path: str) -> dict:
        target = self._safe_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Not found: {path}")
        stat = target.stat()
        info = {
            "name": target.name,
            "path": str(target.relative_to(self.root)),
            "absolute_path": str(target),
            "type": "dir" if target.is_dir() else "file",
            "size_bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        }
        if target.is_file():
            info["extension"] = target.suffix
            info["size_human"] = self._human_size(stat.st_size)
        if target.is_dir():
            contents = list(target.iterdir())
            info["num_files"] = sum(1 for c in contents if c.is_file())
            info["num_dirs"] = sum(1 for c in contents if c.is_dir())
        return info

    def move(self, source: str, destination: str) -> dict:
        src = self._safe_path(source)
        dst = self._safe_path(destination)
        if not src.exists():
            raise FileNotFoundError(f"Source not found: {source}")
        if dst.is_dir():
            dst = dst / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return {"action": "moved", "from": str(src.relative_to(self.root)), "to": str(dst.relative_to(self.root))}

    def rename(self, path: str, new_name: str) -> dict:
        target = self._safe_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Not found: {path}")
        if "/" in new_name or "\\" in new_name:
            raise ValueError("new_name should be a filename, not a path. Use move() instead.")
        new_path = target.parent / new_name
        target.rename(new_path)
        return {"action": "renamed", "from": target.name, "to": new_name, "path": str(new_path.relative_to(self.root))}

    def copy(self, source: str, destination: str) -> dict:
        src = self._safe_path(source)
        dst = self._safe_path(destination)
        if not src.exists():
            raise FileNotFoundError(f"Source not found: {source}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
        return {"action": "copied", "from": str(src.relative_to(self.root)), "to": str(dst.relative_to(self.root))}

    def mkdir(self, path: str) -> dict:
        target = self._safe_path(path)
        target.mkdir(parents=True, exist_ok=True)
        return {"action": "created_directory", "path": str(target.relative_to(self.root))}

    def delete(self, path: str) -> dict:
        target = self._safe_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Not found: {path}")
        if target.is_dir():
            contents = list(target.iterdir())
            if contents:
                raise OSError(f"Directory is not empty ({len(contents)} items).")
            target.rmdir()
        else:
            target.unlink()
        return {"action": "deleted", "path": str(target.relative_to(self.root))}

    def find_files(self, pattern: str = "*", path: str = ".", max_results: int = 50) -> list[dict]:
        target = self._safe_path(path)
        results = []
        for match in target.rglob(pattern):
            if match.name.startswith("."):
                continue
            if len(results) >= max_results:
                break
            results.append({
                "name": match.name,
                "path": str(match.relative_to(self.root)),
                "type": "dir" if match.is_dir() else "file",
                "size_bytes": match.stat().st_size if match.is_file() else None,
                "modified": datetime.fromtimestamp(match.stat().st_mtime).isoformat(),
            })
        return results

    def search_content(self, query: str, path: str = ".", extensions: Optional[list[str]] = None, max_results: int = 20) -> list[dict]:
        if extensions is None:
            extensions = [".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
                          ".toml", ".cfg", ".ini", ".csv", ".log", ".html", ".css", ".sh", ".bat", ".ps1"]
        target = self._safe_path(path)
        query_lower = query.lower()
        results = []
        for filepath in target.rglob("*"):
            if len(results) >= max_results:
                break
            if not filepath.is_file() or filepath.suffix.lower() not in extensions or filepath.name.startswith("."):
                continue
            try:
                text = filepath.read_text(encoding="utf-8", errors="ignore")
            except (PermissionError, OSError):
                continue
            if query_lower in text.lower():
                matching_lines = []
                for i, line in enumerate(text.splitlines(), 1):
                    if query_lower in line.lower():
                        matching_lines.append({"line_number": i, "text": line.strip()[:200]})
                        if len(matching_lines) >= 3:
                            break
                results.append({"path": str(filepath.relative_to(self.root)), "name": filepath.name, "matches": matching_lines})
        return results

    def organize_by_extension(self, path: str = ".") -> dict:
        target = self._safe_path(path)
        moved = {}
        for item in target.iterdir():
            if item.is_dir() or item.name.startswith("."):
                continue
            ext = item.suffix.lower().lstrip(".") or "no_extension"
            dest_dir = target / ext
            dest_dir.mkdir(exist_ok=True)
            dest_file = dest_dir / item.name
            if dest_file.exists():
                dest_file = dest_dir / f"{item.stem}_{int(item.stat().st_mtime)}{item.suffix}"
            shutil.move(str(item), str(dest_file))
            moved.setdefault(ext, []).append(item.name)
        return {"action": "organized_by_extension", "path": str(target.relative_to(self.root)), "moved": moved, "total_files": sum(len(v) for v in moved.values())}

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
