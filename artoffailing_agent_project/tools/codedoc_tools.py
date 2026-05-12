"""
Code documentation tools — scan codebases and generate markdown documentation.

Supports Python (deep AST-based parsing), plus surface-level extraction for
JS/TS, Go, Rust, Java, C#, and other common languages via regex patterns.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import ast
import re
from pathlib import Path
from datetime import datetime

# ── Language detection ───────────────────────────────────────────────

LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".sh": "shell",
    ".bash": "shell",
    ".ps1": "powershell",
    ".sql": "sql",
    ".r": "r",
    ".R": "r",
    ".lua": "lua",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
}

# Directories to always skip
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", "egg-info",
    ".eggs", ".idea", ".vs", "bin", "obj", "target", "Lib", "Include",
    "Scripts", "site-packages", ".next", ".nuxt", "coverage",
}

SKIP_FILES = {
    ".DS_Store", "Thumbs.db", ".gitignore", ".gitattributes",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Pipfile.lock", "composer.lock", "Gemfile.lock", "Cargo.lock",
}

# Max file size to parse (500KB)
MAX_FILE_SIZE = 512_000


class CodeDocumentor:
    """Scans codebases and generates markdown documentation."""

    # ── Scanning ─────────────────────────────────────────────────────

    def scan_codebase(self, path: str, max_depth: int = 10) -> dict:
        """Scan a codebase and return a structural overview.

        Returns language breakdown, file counts, directory structure,
        and key files detected (README, config, entry points, etc.).
        """
        root = Path(path).expanduser().resolve()
        if not root.exists():
            return {"error": f"Path not found: {path}"}
        if not root.is_dir():
            return {"error": f"Not a directory: {path}"}

        lang_stats: dict[str, dict] = {}
        all_files: list[dict] = []
        key_files: list[str] = []
        total_lines = 0
        total_size = 0

        key_patterns = [
            "readme*", "license*", "changelog*", "contributing*",
            "makefile", "dockerfile", "docker-compose*",
            "setup.py", "setup.cfg", "pyproject.toml",
            "package.json", "cargo.toml", "go.mod", "pom.xml",
            "*.sln", "*.csproj", "requirements*.txt", "Pipfile",
            "manage.py", "app.py", "main.py", "server.py", "index.*",
        ]

        for file_path in self._walk_files(root, max_depth):
            rel = file_path.relative_to(root)
            ext = file_path.suffix.lower()
            lang = LANG_MAP.get(ext, None)
            size = file_path.stat().st_size
            total_size += size

            # Check key files
            name_lower = file_path.name.lower()
            for pattern in key_patterns:
                if self._glob_match(name_lower, pattern):
                    key_files.append(str(rel))
                    break

            lines = 0
            if lang and size <= MAX_FILE_SIZE:
                try:
                    lines = file_path.read_text(encoding="utf-8", errors="ignore").count("\n") + 1
                except Exception:
                    pass

            total_lines += lines

            if lang:
                if lang not in lang_stats:
                    lang_stats[lang] = {"files": 0, "lines": 0, "size_bytes": 0}
                lang_stats[lang]["files"] += 1
                lang_stats[lang]["lines"] += lines
                lang_stats[lang]["size_bytes"] += size

            all_files.append({
                "path": str(rel),
                "language": lang,
                "lines": lines,
                "size_bytes": size,
            })

        # Sort languages by lines desc
        sorted_langs = dict(sorted(lang_stats.items(), key=lambda x: x[1]["lines"], reverse=True))

        return {
            "root": str(root),
            "total_files": len(all_files),
            "total_lines": total_lines,
            "total_size_bytes": total_size,
            "total_size_human": self._human_size(total_size),
            "languages": sorted_langs,
            "key_files": sorted(key_files),
            "top_level_dirs": sorted([
                d.name for d in root.iterdir()
                if d.is_dir() and d.name not in SKIP_DIRS and not d.name.startswith(".")
            ]),
        }

    # ── Module documentation ─────────────────────────────────────────

    def document_module(self, file_path: str) -> dict:
        """Parse a single source file and extract documentation.

        For Python files, uses AST for deep extraction (classes, functions,
        decorators, type hints, docstrings). For other languages, uses
        regex-based surface extraction.
        """
        fp = Path(file_path).expanduser().resolve()
        if not fp.exists():
            return {"error": f"File not found: {file_path}"}
        if not fp.is_file():
            return {"error": f"Not a file: {file_path}"}
        if fp.stat().st_size > MAX_FILE_SIZE:
            return {"error": f"File too large ({self._human_size(fp.stat().st_size)})"}

        ext = fp.suffix.lower()
        lang = LANG_MAP.get(ext, "unknown")

        try:
            source = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return {"error": f"Could not read file: {e}"}

        result = {
            "file": fp.name,
            "path": str(fp),
            "language": lang,
            "lines": source.count("\n") + 1,
        }

        if lang == "python":
            result.update(self._parse_python(source))
        else:
            result.update(self._parse_generic(source, lang))

        return result

    # ── Generate full project documentation ──────────────────────────

    def generate_docs(
        self,
        path: str,
        title: str = "",
        include_private: bool = False,
        max_depth: int = 10,
    ) -> str:
        """Generate comprehensive markdown documentation for a codebase.

        Scans the project, then documents each source file with extracted
        classes, functions, and docstrings. Returns a single markdown string.
        """
        root = Path(path).expanduser().resolve()
        if not root.exists():
            return f"Error: Path not found: {path}"

        project_name = title or root.name
        scan = self.scan_codebase(path, max_depth)
        if "error" in scan:
            return f"Error: {scan['error']}"

        lines = [
            f"# {project_name}",
            "",
            f"*Auto-generated documentation — {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
            "## Overview",
            "",
            f"- **Files:** {scan['total_files']}",
            f"- **Lines of code:** {scan['total_lines']:,}",
            f"- **Size:** {scan['total_size_human']}",
            "",
        ]

        # Language breakdown
        if scan["languages"]:
            lines.append("### Languages")
            lines.append("")
            lines.append("| Language | Files | Lines | Size |")
            lines.append("|----------|------:|------:|-----:|")
            for lang, stats in scan["languages"].items():
                lines.append(
                    f"| {lang} | {stats['files']} | {stats['lines']:,} | {self._human_size(stats['size_bytes'])} |"
                )
            lines.append("")

        # Key files
        if scan["key_files"]:
            lines.append("### Key Files")
            lines.append("")
            for kf in scan["key_files"]:
                lines.append(f"- `{kf}`")
            lines.append("")

        # Directory structure
        if scan["top_level_dirs"]:
            lines.append("### Project Structure")
            lines.append("")
            lines.append("```")
            lines.append(f"{project_name}/")
            for d in scan["top_level_dirs"]:
                lines.append(f"├── {d}/")
            # Show top-level files
            for item in sorted(root.iterdir()):
                if item.is_file() and not item.name.startswith(".") and item.name not in SKIP_FILES:
                    lines.append(f"├── {item.name}")
            lines.append("```")
            lines.append("")

        # Document each source file
        lines.append("---")
        lines.append("")
        lines.append("## Module Reference")
        lines.append("")

        for file_path in sorted(self._walk_files(root, max_depth)):
            ext = file_path.suffix.lower()
            lang = LANG_MAP.get(ext)
            if not lang or lang in ("json", "yaml", "toml", "markdown", "html", "css", "scss", "sql"):
                continue
            if file_path.stat().st_size > MAX_FILE_SIZE:
                continue

            rel = file_path.relative_to(root)
            doc = self.document_module(str(file_path))
            if "error" in doc:
                continue

            module_lines = self._format_module_doc(str(rel), doc, include_private)
            if module_lines:
                lines.extend(module_lines)

        return "\n".join(lines)

    # ── Generate README skeleton ─────────────────────────────────────

    def generate_readme(
        self,
        path: str,
        project_name: str = "",
        description: str = "",
    ) -> str:
        """Generate a README.md skeleton from codebase analysis.

        Produces sections for description, installation, usage, project
        structure, and contributing. Fills in what it can detect and
        leaves [FILL: ...] placeholders for the rest.
        """
        root = Path(path).expanduser().resolve()
        if not root.exists():
            return f"Error: Path not found: {path}"

        name = project_name or root.name
        scan = self.scan_codebase(path)
        if "error" in scan:
            return f"Error: {scan['error']}"

        # Detect package manager / install method
        install_cmd = self._detect_install(root, scan)
        primary_lang = next(iter(scan["languages"]), "unknown") if scan["languages"] else "unknown"
        run_cmd = self._detect_run_command(root, primary_lang, scan)

        lines = [
            f"# {name}",
            "",
            description or "[FILL: One-line project description]",
            "",
            "## Features",
            "",
            "- [FILL: Key feature 1]",
            "- [FILL: Key feature 2]",
            "- [FILL: Key feature 3]",
            "",
            "## Prerequisites",
            "",
        ]

        # Language-specific prereqs
        prereqs = self._detect_prerequisites(primary_lang, scan)
        for p in prereqs:
            lines.append(f"- {p}")
        lines.append("")

        lines.append("## Installation")
        lines.append("")
        lines.append("```bash")
        lines.append("git clone [FILL: repo URL]")
        lines.append(f"cd {name}")
        for cmd in install_cmd:
            lines.append(cmd)
        lines.append("```")
        lines.append("")

        lines.append("## Usage")
        lines.append("")
        lines.append("```bash")
        lines.append(run_cmd)
        lines.append("```")
        lines.append("")

        # Project structure
        if scan["top_level_dirs"]:
            lines.append("## Project Structure")
            lines.append("")
            lines.append("```")
            lines.append(f"{name}/")
            for d in scan["top_level_dirs"]:
                lines.append(f"├── {d}/")
            lines.append("```")
            lines.append("")

        # Language breakdown
        if scan["languages"]:
            lines.append("## Tech Stack")
            lines.append("")
            for lang in scan["languages"]:
                lines.append(f"- {lang.capitalize()}")
            lines.append("")

        lines.extend([
            "## Contributing",
            "",
            "[FILL: Contributing guidelines or link to CONTRIBUTING.md]",
            "",
            "## License",
            "",
            "[FILL: License type — e.g. MIT, Apache 2.0]",
            "",
        ])

        return "\n".join(lines)

    # ── Document API endpoints ───────────────────────────────────────

    def document_api(self, path: str) -> str:
        """Extract and document API endpoints from a Python web framework project.

        Detects Flask, FastAPI, and Django URL patterns and produces a
        markdown endpoint reference.
        """
        root = Path(path).expanduser().resolve()
        if not root.exists():
            return f"Error: Path not found: {path}"

        endpoints: list[dict] = []

        for file_path in self._walk_files(root, max_depth=10):
            if file_path.suffix.lower() != ".py":
                continue
            if file_path.stat().st_size > MAX_FILE_SIZE:
                continue
            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            rel = str(file_path.relative_to(root))
            endpoints.extend(self._extract_api_endpoints(source, rel))

        if not endpoints:
            return "No API endpoints detected. Supports Flask, FastAPI, and Django patterns."

        lines = [
            "# API Reference",
            "",
            f"*Auto-generated — {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
            f"**{len(endpoints)} endpoint(s) found**",
            "",
            "| Method | Path | Function | File |",
            "|--------|------|----------|------|",
        ]

        for ep in sorted(endpoints, key=lambda x: (x["path"], x["method"])):
            lines.append(f"| `{ep['method']}` | `{ep['path']}` | `{ep['function']}` | `{ep['file']}` |")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Detailed docs
        for ep in sorted(endpoints, key=lambda x: (x["path"], x["method"])):
            lines.append(f"### `{ep['method']}` {ep['path']}")
            lines.append("")
            lines.append(f"**Function:** `{ep['function']}` in `{ep['file']}`")
            lines.append("")
            if ep.get("docstring"):
                lines.append(ep["docstring"])
                lines.append("")
            if ep.get("params"):
                lines.append("**Parameters:**")
                lines.append("")
                for p in ep["params"]:
                    lines.append(f"- `{p['name']}`: `{p['type']}` {p.get('description', '')}")
                lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════
    #  INTERNAL — Python AST parsing
    # ══════════════════════════════════════════════════════════════════

    def _parse_python(self, source: str) -> dict:
        """Deep-parse a Python file using AST."""
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return {"parse_error": str(e)}

        module_doc = ast.get_docstring(tree)
        imports = []
        classes = []
        functions = []
        constants = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
            elif isinstance(node, ast.ClassDef):
                classes.append(self._parse_class(node))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(self._parse_function(node))
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        constants.append(target.id)

        result = {}
        if module_doc:
            result["module_docstring"] = module_doc
        if imports:
            result["imports"] = imports
        if constants:
            result["constants"] = constants
        if classes:
            result["classes"] = classes
        if functions:
            result["functions"] = functions
        return result

    def _parse_class(self, node: ast.ClassDef) -> dict:
        """Extract class info from AST node."""
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(ast.unparse(base))

        decorators = [ast.unparse(d) for d in node.decorator_list]

        methods = []
        class_vars = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._parse_function(item))
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_vars.append(target.id)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                annotation = ast.unparse(item.annotation) if item.annotation else ""
                class_vars.append(f"{item.target.id}: {annotation}" if annotation else item.target.id)

        info: dict = {"name": node.name}
        if bases:
            info["bases"] = bases
        if decorators:
            info["decorators"] = decorators
        docstring = ast.get_docstring(node)
        if docstring:
            info["docstring"] = docstring
        if class_vars:
            info["class_variables"] = class_vars
        if methods:
            info["methods"] = methods
        return info

    def _parse_function(self, node) -> dict:
        """Extract function/method info from AST node."""
        info: dict = {"name": node.name}
        if isinstance(node, ast.AsyncFunctionDef):
            info["async"] = True

        decorators = [ast.unparse(d) for d in node.decorator_list]
        if decorators:
            info["decorators"] = decorators

        # Parameters
        params = []
        args = node.args
        defaults_offset = len(args.args) - len(args.defaults)

        for i, arg in enumerate(args.args):
            if arg.arg == "self" or arg.arg == "cls":
                continue
            p: dict = {"name": arg.arg}
            if arg.annotation:
                p["type"] = ast.unparse(arg.annotation)
            default_idx = i - defaults_offset
            if default_idx >= 0 and default_idx < len(args.defaults):
                try:
                    p["default"] = ast.unparse(args.defaults[default_idx])
                except Exception:
                    pass
            params.append(p)

        # *args
        if args.vararg:
            p = {"name": f"*{args.vararg.arg}"}
            if args.vararg.annotation:
                p["type"] = ast.unparse(args.vararg.annotation)
            params.append(p)

        # **kwargs
        if args.kwarg:
            p = {"name": f"**{args.kwarg.arg}"}
            if args.kwarg.annotation:
                p["type"] = ast.unparse(args.kwarg.annotation)
            params.append(p)

        if params:
            info["params"] = params

        # Return type
        if node.returns:
            info["returns"] = ast.unparse(node.returns)

        # Docstring
        docstring = ast.get_docstring(node)
        if docstring:
            info["docstring"] = docstring

        return info

    # ══════════════════════════════════════════════════════════════════
    #  INTERNAL — Generic regex-based parsing
    # ══════════════════════════════════════════════════════════════════

    def _parse_generic(self, source: str, lang: str) -> dict:
        """Surface-level extraction for non-Python languages."""
        result: dict = {}
        functions = []
        classes = []

        if lang in ("javascript", "typescript"):
            # Functions: function name(...) and const name = (...) =>
            for m in re.finditer(
                r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
                source,
            ):
                functions.append({"name": m.group(1), "params_raw": m.group(2).strip()})
            for m in re.finditer(
                r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*\w+\s*)?=>',
                source,
            ):
                functions.append({"name": m.group(1), "params_raw": m.group(2).strip()})
            # Classes
            for m in re.finditer(
                r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?',
                source,
            ):
                c: dict = {"name": m.group(1)}
                if m.group(2):
                    c["bases"] = [m.group(2)]
                classes.append(c)
            # Interfaces (TS)
            if lang == "typescript":
                for m in re.finditer(
                    r'(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+(\w+))?',
                    source,
                ):
                    c = {"name": m.group(1), "type": "interface"}
                    if m.group(2):
                        c["bases"] = [m.group(2)]
                    classes.append(c)

        elif lang == "go":
            for m in re.finditer(r'func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(([^)]*)\)', source):
                functions.append({"name": m.group(1), "params_raw": m.group(2).strip()})
            for m in re.finditer(r'type\s+(\w+)\s+struct\s*\{', source):
                classes.append({"name": m.group(1), "type": "struct"})
            for m in re.finditer(r'type\s+(\w+)\s+interface\s*\{', source):
                classes.append({"name": m.group(1), "type": "interface"})

        elif lang == "rust":
            for m in re.finditer(r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)', source):
                functions.append({"name": m.group(1), "params_raw": m.group(2).strip()})
            for m in re.finditer(r'(?:pub\s+)?struct\s+(\w+)', source):
                classes.append({"name": m.group(1), "type": "struct"})
            for m in re.finditer(r'(?:pub\s+)?trait\s+(\w+)', source):
                classes.append({"name": m.group(1), "type": "trait"})
            for m in re.finditer(r'(?:pub\s+)?enum\s+(\w+)', source):
                classes.append({"name": m.group(1), "type": "enum"})

        elif lang in ("java", "csharp", "kotlin"):
            for m in re.finditer(
                r'(?:public|private|protected|internal|static|async|override|\s)*\s+(\w+)\s+(\w+)\s*\(([^)]*)\)\s*(?:\{|=>)',
                source,
            ):
                if m.group(2) not in ("if", "for", "while", "switch", "catch"):
                    functions.append({
                        "name": m.group(2),
                        "return_type": m.group(1),
                        "params_raw": m.group(3).strip(),
                    })
            for m in re.finditer(
                r'(?:public|private|protected|internal|abstract|static|\s)*\s*class\s+(\w+)(?:\s*(?:extends|:)\s+(\w+))?',
                source,
            ):
                c = {"name": m.group(1)}
                if m.group(2):
                    c["bases"] = [m.group(2)]
                classes.append(c)

        elif lang == "ruby":
            for m in re.finditer(r'def\s+(?:self\.)?(\w+[?!]?)(?:\s*\(([^)]*)\))?', source):
                functions.append({"name": m.group(1), "params_raw": (m.group(2) or "").strip()})
            for m in re.finditer(r'class\s+(\w+)(?:\s*<\s*(\w+))?', source):
                c = {"name": m.group(1)}
                if m.group(2):
                    c["bases"] = [m.group(2)]
                classes.append(c)
            for m in re.finditer(r'module\s+(\w+)', source):
                classes.append({"name": m.group(1), "type": "module"})

        elif lang == "php":
            for m in re.finditer(
                r'(?:public|private|protected|static|\s)*\s*function\s+(\w+)\s*\(([^)]*)\)',
                source,
            ):
                functions.append({"name": m.group(1), "params_raw": m.group(2).strip()})
            for m in re.finditer(
                r'class\s+(\w+)(?:\s+extends\s+(\w+))?',
                source,
            ):
                c = {"name": m.group(1)}
                if m.group(2):
                    c["bases"] = [m.group(2)]
                classes.append(c)

        if functions:
            result["functions"] = functions
        if classes:
            result["classes"] = classes

        # Extract doc comments (/** ... */ or /// style)
        doc_comments = re.findall(r'/\*\*(.*?)\*/', source, re.DOTALL)
        line_comments = re.findall(r'^\s*///\s*(.+)$', source, re.MULTILINE)
        if doc_comments:
            result["doc_comment_count"] = len(doc_comments)
        if line_comments:
            result["line_doc_comment_count"] = len(line_comments)

        return result

    # ══════════════════════════════════════════════════════════════════
    #  INTERNAL — API endpoint extraction
    # ══════════════════════════════════════════════════════════════════

    def _extract_api_endpoints(self, source: str, file_path: str) -> list[dict]:
        """Extract API endpoints from Python web framework code."""
        endpoints = []

        # FastAPI patterns: @app.get("/path"), @router.post("/path")
        for m in re.finditer(
            r'@\w+\.(get|post|put|delete|patch|options|head)\s*\(\s*["\']([^"\']+)["\']',
            source,
            re.IGNORECASE,
        ):
            method = m.group(1).upper()
            path = m.group(2)
            # Find the function after the decorator
            func_match = re.search(
                r'(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)',
                source[m.end():m.end() + 500],
            )
            if func_match:
                ep: dict = {
                    "method": method,
                    "path": path,
                    "function": func_match.group(1),
                    "file": file_path,
                }
                # Try to grab docstring
                func_body_start = source.find(":", m.end() + func_match.end())
                if func_body_start != -1:
                    doc_match = re.search(
                        r'"""(.*?)"""',
                        source[func_body_start:func_body_start + 500],
                        re.DOTALL,
                    )
                    if doc_match:
                        ep["docstring"] = doc_match.group(1).strip()

                # Parse params
                params_raw = func_match.group(2)
                ep["params"] = self._parse_param_string(params_raw)
                endpoints.append(ep)

        # Flask patterns: @app.route("/path", methods=["GET"])
        for m in re.finditer(
            r'@\w+\.route\s*\(\s*["\']([^"\']+)["\'](?:.*?methods\s*=\s*\[([^\]]+)\])?',
            source,
            re.DOTALL,
        ):
            path = m.group(1)
            methods_str = m.group(2) or '"GET"'
            methods = re.findall(r'["\'](\w+)["\']', methods_str)

            func_match = re.search(
                r'def\s+(\w+)\s*\(([^)]*)\)',
                source[m.end():m.end() + 500],
            )
            if func_match:
                for method in methods:
                    endpoints.append({
                        "method": method.upper(),
                        "path": path,
                        "function": func_match.group(1),
                        "file": file_path,
                    })

        return endpoints

    def _parse_param_string(self, params_raw: str) -> list[dict]:
        """Parse a function parameter string into structured params."""
        params = []
        for part in params_raw.split(","):
            part = part.strip()
            if not part or part in ("self", "cls", "request", "response", "db"):
                continue
            p: dict = {}
            if ":" in part:
                name_part, type_part = part.split(":", 1)
                p["name"] = name_part.strip()
                type_str = type_part.split("=")[0].strip()
                p["type"] = type_str
            else:
                p["name"] = part.split("=")[0].strip()
                p["type"] = ""
            params.append(p)
        return params

    # ══════════════════════════════════════════════════════════════════
    #  INTERNAL — Formatting
    # ══════════════════════════════════════════════════════════════════

    def _format_module_doc(self, rel_path: str, doc: dict, include_private: bool) -> list[str]:
        """Format a module's parsed info as markdown lines."""
        lines = []
        has_content = False

        lines.append(f"### `{rel_path}`")
        lines.append("")

        if doc.get("module_docstring"):
            lines.append(f"> {doc['module_docstring'].split(chr(10))[0]}")
            lines.append("")
            has_content = True

        # Classes
        for cls in doc.get("classes", []):
            if not include_private and cls["name"].startswith("_"):
                continue
            has_content = True
            bases_str = f"({', '.join(cls.get('bases', []))})" if cls.get("bases") else ""
            type_label = cls.get("type", "class")
            lines.append(f"#### {type_label} `{cls['name']}{bases_str}`")
            lines.append("")
            if cls.get("decorators"):
                lines.append(f"*Decorators:* {', '.join(f'`@{d}`' for d in cls['decorators'])}")
                lines.append("")
            if cls.get("docstring"):
                lines.append(cls["docstring"])
                lines.append("")
            if cls.get("class_variables"):
                lines.append("**Class variables:** " + ", ".join(f"`{v}`" for v in cls["class_variables"]))
                lines.append("")
            for method in cls.get("methods", []):
                if not include_private and method["name"].startswith("_") and method["name"] != "__init__":
                    continue
                self._format_function_doc(method, lines, indent_level=1)

        # Module-level functions
        for func in doc.get("functions", []):
            if not include_private and func["name"].startswith("_"):
                continue
            has_content = True
            self._format_function_doc(func, lines, indent_level=0)

        if has_content:
            lines.append("---")
            lines.append("")
            return lines
        return []

    def _format_function_doc(self, func: dict, lines: list, indent_level: int = 0):
        """Format a single function/method as markdown."""
        prefix = "#####" if indent_level > 0 else "####"
        async_prefix = "async " if func.get("async") else ""
        name = func["name"]
        returns = f" → `{func['returns']}`" if func.get("returns") else ""

        # Build signature
        params_parts = []
        for p in func.get("params", []):
            s = p["name"]
            if p.get("type"):
                s += f": {p['type']}"
            if p.get("default"):
                s += f" = {p['default']}"
            params_parts.append(s)
        params_str = ", ".join(params_parts)

        lines.append(f"{prefix} `{async_prefix}{name}({params_str})`{returns}")
        lines.append("")

        if func.get("decorators"):
            lines.append(f"*Decorators:* {', '.join(f'`@{d}`' for d in func['decorators'])}")
            lines.append("")
        if func.get("docstring"):
            lines.append(func["docstring"])
            lines.append("")
        if func.get("params_raw"):
            lines.append(f"*Parameters:* `{func['params_raw']}`")
            lines.append("")
        if func.get("return_type"):
            lines.append(f"*Returns:* `{func['return_type']}`")
            lines.append("")

    # ══════════════════════════════════════════════════════════════════
    #  INTERNAL — Utilities
    # ══════════════════════════════════════════════════════════════════

    def _walk_files(self, root: Path, max_depth: int) -> list[Path]:
        """Walk directory tree, skipping ignored dirs, respecting depth."""
        files = []
        gitignore_patterns = self._load_gitignore(root)

        def _walk(directory: Path, depth: int):
            if depth > max_depth:
                return
            try:
                entries = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            except PermissionError:
                return
            for entry in entries:
                if entry.name.startswith(".") and entry.name != ".env.example":
                    continue
                if entry.is_dir():
                    if entry.name in SKIP_DIRS:
                        continue
                    rel = str(entry.relative_to(root))
                    if any(re.match(p, rel) for p in gitignore_patterns):
                        continue
                    _walk(entry, depth + 1)
                elif entry.is_file():
                    if entry.name in SKIP_FILES:
                        continue
                    files.append(entry)

        _walk(root, 0)
        return files

    def _load_gitignore(self, root: Path) -> list[str]:
        """Load .gitignore patterns and convert to simple regex patterns."""
        gitignore = root / ".gitignore"
        if not gitignore.exists():
            return []
        patterns = []
        try:
            for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Convert glob to simple regex
                pattern = line.rstrip("/")
                pattern = pattern.replace(".", r"\.")
                pattern = pattern.replace("*", ".*")
                pattern = pattern.replace("?", ".")
                patterns.append(pattern)
        except Exception:
            pass
        return patterns

    def _glob_match(self, name: str, pattern: str) -> bool:
        """Simple glob match for key file detection."""
        regex = pattern.replace(".", r"\.").replace("*", ".*")
        return bool(re.match(regex, name, re.IGNORECASE))

    def _detect_install(self, root: Path, scan: dict) -> list[str]:
        """Detect installation commands from project files."""
        key = {kf.lower() for kf in scan.get("key_files", [])}
        cmds = []

        if "pyproject.toml" in key:
            cmds.append("pip install -e .")
        elif "requirements.txt" in key:
            cmds.append("pip install -r requirements.txt")
        elif "setup.py" in key:
            cmds.append("pip install -e .")
        elif "pipfile" in key:
            cmds.append("pipenv install")

        if "package.json" in key:
            cmds.append("npm install")
        if "cargo.toml" in key:
            cmds.append("cargo build")
        if "go.mod" in key:
            cmds.append("go mod download")
        if "pom.xml" in key:
            cmds.append("mvn install")
        if "gemfile" in key:
            cmds.append("bundle install")

        return cmds or ["[FILL: install command]"]

    def _detect_run_command(self, root: Path, primary_lang: str, scan: dict) -> str:
        """Detect the main run command."""
        key = {kf.lower() for kf in scan.get("key_files", [])}

        if "manage.py" in key:
            return "python manage.py runserver"
        if "app.py" in key:
            return "python app.py"
        if "main.py" in key:
            return "python main.py"
        if "server.py" in key:
            return "python server.py"

        if primary_lang == "python":
            return "python [FILL: entry point]"
        if primary_lang in ("javascript", "typescript"):
            return "npm start"
        if primary_lang == "go":
            return "go run ."
        if primary_lang == "rust":
            return "cargo run"
        return "[FILL: run command]"

    def _detect_prerequisites(self, primary_lang: str, scan: dict) -> list[str]:
        """Detect prerequisites based on languages used."""
        prereqs = []
        langs = set(scan.get("languages", {}).keys())

        if "python" in langs:
            prereqs.append("Python 3.10+")
        if "javascript" in langs or "typescript" in langs:
            prereqs.append("Node.js 18+")
        if "go" in langs:
            prereqs.append("Go 1.21+")
        if "rust" in langs:
            prereqs.append("Rust / Cargo")
        if "java" in langs:
            prereqs.append("Java 17+ / JDK")
        if "csharp" in langs:
            prereqs.append(".NET 8+")
        if "ruby" in langs:
            prereqs.append("Ruby 3.2+")

        return prereqs or ["[FILL: prerequisites]"]

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
