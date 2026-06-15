"""Tool definitions with structured results for the desktop pet agent."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from utils.logger import logger


# ---------------------------------------------------------------------------
# Structured tool result
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    content: str
    is_error: bool = False
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Simple TTL cache for search results to avoid redundant network calls
_search_cache: dict[str, tuple[float, list[dict]]] = {}
_SEARCH_CACHE_TTL = 300  # 5 minutes

# Shared HTTP opener with connection pooling for all urllib requests
_http_opener = None


def _get_opener():
    global _http_opener
    if _http_opener is None:
        import urllib.request
        _http_opener = urllib.request.build_opener(
            urllib.request.HTTPHandler(),
            urllib.request.HTTPSHandler(),
        )
    return _http_opener


def _cached_search(query: str, max_results: int) -> list[dict] | None:
    """Return cached results if fresh, otherwise None."""
    key = f"{query}|{max_results}"
    entry = _search_cache.get(key)
    if entry:
        ts, results = entry
        if time.time() - ts < _SEARCH_CACHE_TTL:
            return results
        del _search_cache[key]
    return None


def _cache_search(query: str, max_results: int, results: list[dict]) -> None:
    key = f"{query}|{max_results}"
    _search_cache[key] = (time.time(), results)
    # Prune cache if too large
    if len(_search_cache) > 50:
        oldest = sorted(_search_cache.items(), key=lambda x: x[1][0])[:10]
        for k, _ in oldest:
            del _search_cache[k]

def _run_sync(func, *args):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, func, *args)


def _format_search_results(query: str, results: list[dict]) -> str:
    lines = [f"搜索 '{query}' 的结果:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   {r['url']}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet']}")
        lines.append("")
    return "\n".join(lines)


def _now_ms() -> float:
    return time.time() * 1000


def _check_executable(name: str) -> bool:
    return shutil.which(name) is not None


def _py_grep(pattern: str, root: str) -> str:
    """Python-native grep — handles UTF-8 properly on Windows."""
    import re as _re
    try:
        regex = _re.compile(pattern, _re.IGNORECASE)
    except _re.error:
        regex = _re.compile(_re.escape(pattern), _re.IGNORECASE)

    lines_out: list[str] = []
    file_count = 0
    match_count = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        # Skip hidden and binary-looking dirs/files
        _dirnames[:] = [d for d in _dirnames if not d.startswith(".") and d not in ("__pycache__", "node_modules", ".git", "venv", "env")]
        for fname in filenames:
            if match_count >= 30:
                break
            fpath = os.path.join(dirpath, fname)
            # Skip binary extensions
            if fname.endswith((".png", ".jpg", ".gif", ".ico", ".exe", ".dll", ".pyd", ".pyc", ".db", ".bin", ".zip", ".7z", ".pdf")):
                continue
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        if regex.search(line):
                            lines_out.append(f"{fpath}:{lineno}: {line.rstrip()[:200]}")
                            match_count += 1
                            if match_count >= 30:
                                break
                file_count += 1
            except (OSError, UnicodeError):
                continue
        if file_count > 500 or match_count >= 30:
            break

    if lines_out:
        return "\n".join(lines_out) + (f"\n\n(找到 {match_count} 处匹配)" if match_count >= 30 else f"\n\n(找到 {match_count} 处匹配)")
    return ""


# ---------------------------------------------------------------------------
# Search backends (module-level functions)
# ---------------------------------------------------------------------------

def _search_bing(query: str, max_results: int) -> list[dict]:
    """Scrape Bing search results. Tries cn.bing.com first, then www."""
    import urllib.parse
    import urllib.request

    encoded_q = urllib.parse.quote(query)
    domains = ["cn.bing.com", "www.bing.com"]
    opener = _get_opener()

    for domain in domains:
        try:
            url = f"https://{domain}/search?q={encoded_q}&count={max_results}&mkt=zh-CN"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept-Encoding": "gzip",
            })
            with opener.open(req, timeout=8) as resp:
                raw = resp.read()
                # Handle gzip
                if raw[:2] == b'\x1f\x8b':
                    import gzip
                    html = gzip.decompress(raw).decode("utf-8", errors="replace")
                else:
                    html = raw.decode("utf-8", errors="replace")

            # Extract results from <li class="b_algo"> blocks
            results = []
            blocks = re.split(r'<li[^>]*class="b_algo"[^>]*>', html)[1:]

            for block in blocks[:max_results]:
                title_m = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>', block, re.DOTALL)
                url_m = re.search(r'<a[^>]*href="(https?://[^"]+)"', block)
                cite_m = re.search(r'<cite[^>]*>(.*?)</cite>', block, re.DOTALL)
                snippet_m = re.search(r'<(?:p|div class="b_caption"[^>]*>)>(.*?)</(?:p|div)>', block, re.DOTALL)

                title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ""
                snippet = re.sub(r'<[^>]+>', '', snippet_m.group(1)).strip() if snippet_m else ""
                url_result = url_m.group(1) if url_m else ""
                if not url_result and cite_m:
                    url_result = re.sub(r'<[^>]+>', '', cite_m.group(1)).strip()
                    if not url_result.startswith("http"):
                        url_result = ""

                if title:
                    results.append({"title": title, "url": url_result, "snippet": snippet})

            if results:
                return results
        except Exception as e:
            logger.debug(f"Bing ({domain}) failed: {e}")
            continue

    return []


def _search_ddgs(query: str, max_results: int) -> list[dict]:
    """DuckDuckGo search (fallback)."""
    from ddgs import DDGS
    results = []
    with DDGS(timeout=8) as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            })
            if len(results) >= max_results:
                break
    return results


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Registry of tools available to the agent."""

    _store = None  # set by AgentExecutor

    @staticmethod
    def get_definitions() -> list[dict]:
        return [
            _def("read_file", "读取一个文本文件的内容",
                 {"path": {"type": "string", "description": "文件的绝对路径"}},
                 ["path"]),
            _def("write_file", "将文本内容写入文件",
                 {
                     "path": {"type": "string", "description": "文件的绝对路径"},
                     "content": {"type": "string", "description": "要写入的内容"},
                 }, ["path", "content"]),
            _def("list_directory", "列出目录中的文件和文件夹",
                 {"path": {"type": "string", "description": "目录路径", "default": "."}},
                 []),
            _def("grep_code", "在本地文件中搜索匹配的文本内容（基于 ripgrep）",
                 {
                     "pattern": {"type": "string", "description": "要搜索的正则表达式或文本"},
                     "path": {"type": "string", "description": "搜索目录路径", "default": "."},
                 }, ["pattern"]),
            _def("web_search", "使用 DuckDuckGo 搜索互联网，返回结构化结果",
                 {
                     "query": {"type": "string", "description": "搜索关键词"},
                     "max_results": {"type": "integer", "description": "最大结果数", "default": 5},
                 }, ["query"]),
            _def("fetch_url", "获取一个网页的文本正文内容",
                 {
                     "url": {"type": "string", "description": "网页 URL"},
                     "max_chars": {"type": "integer", "description": "最大字符数", "default": 6000},
                 }, ["url"]),
            _def("get_system_info", "获取操作系统、CPU、内存等系统信息", {}, []),
            _def("run_command", "执行一条 Shell 命令。请谨慎使用，不要执行危险操作",
                 {"command": {"type": "string", "description": "要执行的命令"}},
                 ["command"]),
            _def("schedule_reminder", "设置一个定时提醒。when 用自然语言描述时间，如 '5分钟后'、'明天上午9点'",
                 {
                     "title": {"type": "string", "description": "提醒标题"},
                     "when": {"type": "string", "description": "什么时候提醒，用中文自然语言描述"},
                     "message": {"type": "string", "description": "提醒时要说的内容"},
                 }, ["title", "when", "message"]),
            _def("list_reminders", "列出所有待执行的定时提醒", {}, []),
            _def("cancel_reminder", "取消一个定时提醒",
                 {"task_id": {"type": "integer", "description": "提醒的ID（从 list_reminders 获取）"}},
                 ["task_id"]),
            # ---- Local control tools ----
            _def("open_app", "打开本地应用程序，支持浏览器、编辑器、系统工具等",
                 {
                     "name": {
                         "type": "string",
                         "description": "应用名称，支持: chrome/edge/firefox(浏览器), vscode/cursor(编辑器), "
                                        "explorer(资源管理器), calculator/calc(计算器), notepad(记事本), "
                                        "terminal/cmd(命令提示符), settings(设置), taskmgr(任务管理器), "
                                        "spotify(音乐), wechat(微信), obsidian, typora 等。也可以是exe名称或路径",
                     },
                 }, ["name"]),
            _def("open_url", "在默认浏览器中打开一个网址",
                 {"url": {"type": "string", "description": "要打开的完整 URL，如 https://www.baidu.com"}},
                 ["url"]),
            _def("system_control",
                 "控制系统操作：关机、重启、睡眠、锁定、音量控制",
                 {
                     "action": {
                         "type": "string",
                         "description": "操作类型: lock(锁定), sleep(睡眠), volume_up(音量+), "
                                        "volume_down(音量-), mute(静音) — 仅限安全操作, 不含关机/重启",
                     },
                 }, ["action"]),
            _def("web_open",
                 "搜索网页内容并直接打开结果链接。不是打开浏览器界面，"
                 "而是直接解析网页HTML找到目标链接并打开。"
                 "适合 '搜xx视频并打开'、'打开B站xxx视频'、'找xxx文章' 等场景。"
                 "这是打开搜索结果最可靠的方式，优先使用",
                 {
                     "query": {"type": "string", "description": "搜索关键词"},
                     "site": {
                         "type": "string",
                         "description": "目标网站，支持: bilibili(b站视频搜索)、"
                                        "baidu(百度搜索)、bing(Bing搜索)、youtube",
                         "default": "baidu",
                     },
                 }, ["query"]),
            _def("research_trends",
                 "深度研究某个话题过去30天内的全网热门讨论。搜索 Reddit、X(Twitter)、YouTube、"
                 "Hacker News、GitHub、Bing 等多个平台，按互动热度排序返回摘要。"
                 "适合问'最近XX有什么热门讨论'、'XX趋势'这类问题",
                 {
                     "topic": {"type": "string", "description": "要研究的话题，如 'AI编程工具'、'中美关系最新动态'"},
                     "sources": {
                         "type": "string",
                         "description": "搜索源，逗号分隔。可选: reddit, x, youtube, hackernews, github, web。默认全选",
                         "default": "",
                     },
                 }, ["topic"]),
        ]

    @staticmethod
    async def execute(name: str, args: dict) -> ToolResult:
        tool_map = {
            "read_file": ToolRegistry._read_file,
            "write_file": ToolRegistry._write_file,
            "list_directory": ToolRegistry._list_directory,
            "grep_code": ToolRegistry._grep_code,
            "web_search": ToolRegistry._web_search,
            "fetch_url": ToolRegistry._fetch_url,
            "get_system_info": ToolRegistry._get_system_info,
            "run_command": ToolRegistry._run_command,
            "schedule_reminder": ToolRegistry._schedule_reminder,
            "list_reminders": ToolRegistry._list_reminders,
            "cancel_reminder": ToolRegistry._cancel_reminder,
            "open_app": ToolRegistry._open_app,
            "open_url": ToolRegistry._open_url,
            "system_control": ToolRegistry._system_control,
            "research_trends": ToolRegistry._research_trends,
            "web_open": ToolRegistry._web_open,
        }
        func = tool_map.get(name)
        if not func:
            return ToolResult(f"Error: Unknown tool '{name}'", is_error=True)
        try:
            return await func(args)
        except Exception as e:
            logger.error(f"Tool {name} exception: {e}")
            return ToolResult(f"Error executing {name}: {e}", is_error=True)

    # ------------------------------------------------------------------
    # read_file
    # ------------------------------------------------------------------

    @staticmethod
    async def _read_file(args: dict) -> ToolResult:
        path = args["path"]
        loop = asyncio.get_event_loop()

        def _read():
            st = os.stat(path)
            with open(path, "r", encoding="utf-8") as f:
                return f.read(), st.st_size, st.st_mtime

        try:
            content, size, mtime = await _run_sync(_read)
        except FileNotFoundError:
            return ToolResult(f"文件不存在: {path}", is_error=True)
        except PermissionError:
            return ToolResult(f"没有权限读取: {path}", is_error=True)

        truncated = False
        if len(content) > 8000:
            content = content[:8000] + "\n...(truncated)"
            truncated = True

        return ToolResult(
            content=content,
            metadata={"path": path, "size_bytes": size, "truncated": truncated}
        )

    # ------------------------------------------------------------------
    # write_file (with safety backup)
    # ------------------------------------------------------------------

    @staticmethod
    async def _write_file(args: dict) -> ToolResult:
        path = args["path"]
        content = args["content"]
        loop = asyncio.get_event_loop()

        def _write():
            meta = {"path": path, "bytes_written": len(content.encode("utf-8"))}
            old_exists = os.path.exists(path)
            old_size = os.path.getsize(path) if old_exists else 0

            if old_exists:
                # backup
                backup_dir = "storage/file_backups"
                os.makedirs(backup_dir, exist_ok=True)
                backup_name = f"{Path(path).stem}_{int(time.time())}{Path(path).suffix}"
                backup_path = os.path.join(backup_dir, backup_name)
                shutil.copy2(path, backup_path)
                meta["backup_path"] = backup_path
                meta["old_size_bytes"] = old_size

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            new_size = os.path.getsize(path)
            meta["new_size_bytes"] = new_size
            meta["size_change"] = new_size - old_size
            return meta

        meta = await _run_sync(_write)
        old_sz = meta.get("old_size_bytes", 0)
        new_sz = meta.get("new_size_bytes", 0)
        backup = meta.get("backup_path")
        lines = [
            f"已写入 {len(content.encode('utf-8'))} bytes 到 {path}",
            f"文件大小变化: {old_sz} → {new_sz} bytes",
        ]
        if backup:
            lines.append(f"原文件已备份到: {backup}")
        return ToolResult(content="\n".join(lines), metadata=meta)

    # ------------------------------------------------------------------
    # list_directory
    # ------------------------------------------------------------------

    @staticmethod
    async def _list_directory(args: dict) -> ToolResult:
        path = args.get("path", ".")

        def _list():
            entries = os.listdir(path)
            dirs, files = [], []
            for e in sorted(entries):
                full = os.path.join(path, e)
                if os.path.isdir(full):
                    dirs.append(f"📁 {e}/")
                else:
                    try:
                        sz = os.path.getsize(full)
                        files.append(f"📄 {e} ({_fmt_size(sz)})")
                    except OSError:
                        files.append(f"📄 {e}")
            return dirs + files

        entries = await _run_sync(_list)
        return ToolResult(
            content="\n".join(entries[:60]) if entries else f"目录 {path} 是空的",
            metadata={"path": path, "entry_count": len(entries)}
        )

    # ------------------------------------------------------------------
    # grep_code
    # ------------------------------------------------------------------

    @staticmethod
    async def _grep_code(args: dict) -> ToolResult:
        pattern = args["pattern"]
        path = args.get("path", ".")

        if _check_executable("rg"):
            process = await asyncio.create_subprocess_exec(
                "rg", "-H", "-n", "--max-count=3", pattern, path,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            output = stdout.decode("utf-8", errors="replace")
            if stderr:
                output += "\n" + stderr.decode("utf-8", errors="replace")
            engine = "ripgrep"
        else:
            # Python-native search — handles UTF-8/Unicode properly on Windows
            output = await _run_sync(_py_grep, pattern, path)
            engine = "python"

        if not output.strip():
            output = f"在 {path} 中没有找到匹配 '{pattern}' 的内容"

        if len(output) > 5000:
            output = output[:5000] + "\n...(结果过多已截断)"

        return ToolResult(
            content=output,
            metadata={"pattern": pattern, "path": path, "engine": engine}
        )

    # ------------------------------------------------------------------
    # web_search (Bing primary, DDGS fallback)
    # ------------------------------------------------------------------

    @staticmethod
    async def _web_search(args: dict) -> ToolResult:
        query = args["query"]
        max_results = args.get("max_results", 3)

        cached = _cached_search(query, max_results)
        if cached is not None:
            return ToolResult(
                content=_format_search_results(query, cached),
                metadata={"query": query, "result_count": len(cached),
                          "engine": "cache", "cached": True},
            )

        # Try Bing → DDGS
        for engine, searcher in [("Bing", _search_bing), ("DuckDuckGo", _search_ddgs)]:
            try:
                results = await asyncio.wait_for(
                    _run_sync(searcher, query, max_results), timeout=10.0
                )
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.warning(f"{engine} search failed: {e}")
                continue

            if results:
                _cache_search(query, max_results, results)
                return ToolResult(
                    content=_format_search_results(query, results),
                    metadata={"query": query, "result_count": len(results),
                              "engine": engine},
                )

        return ToolResult(
            "搜索失败：所有搜索引擎均超时，请检查网络连接后重试",
            is_error=True, metadata={"query": query},
        )

    # ------------------------------------------------------------------
    # fetch_url (with charset detection)
    # ------------------------------------------------------------------

    @staticmethod
    async def _fetch_url(args: dict) -> ToolResult:
        url = args["url"]
        max_chars = args.get("max_chars", 6000)

        def _ensure_ascii_url(raw_url: str) -> str:
            """Percent-encode non-ASCII chars in URL path/query to avoid ASCII encoding errors."""
            from urllib.parse import urlsplit, urlunsplit, quote
            parts = urlsplit(raw_url)
            # Only encode path, query, fragment — keep scheme+netloc as-is
            safe_parts = (
                parts.scheme,
                parts.netloc,
                quote(parts.path, safe="/@!$&'()*+,;=-._~"),
                quote(parts.query, safe="=&/:@!$'()*+,;=-._~?%"),
                quote(parts.fragment, safe=""),
            )
            return urlunsplit(safe_parts)

        def _fetch():
            import urllib.request

            safe_url = _ensure_ascii_url(url)
            req = urllib.request.Request(
                safe_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept-Encoding": "gzip",
                },
            )
            with _get_opener().open(req, timeout=15) as resp:
                raw = resp.read()
                content_type = resp.headers.get("Content-Type", "")
                final_url = resp.url  # after redirects
            return raw, content_type, final_url

        try:
            raw, content_type, final_url = await _run_sync(_fetch)
        except Exception as e:
            return ToolResult(f"获取网页失败: {e}", is_error=True, metadata={"url": url})

        # Detect charset from Content-Type header or <meta> tag
        charset = "utf-8"
        m = re.search(rb"charset=([\w-]+)", raw[:2048])
        if m:
            charset = m.group(1).decode("ascii", errors="replace")
        elif "charset=" in content_type:
            m2 = re.search(r"charset=([\w-]+)", content_type)
            if m2:
                charset = m2.group(1)

        try:
            html = raw.decode(charset, errors="replace")
        except LookupError:
            html = raw.decode("utf-8", errors="replace")

        # Extract title
        title = ""
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()

        # Strip HTML
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        # Decode HTML entities
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
        text = re.sub(r"&[#\w]+;", "", text)
        text = re.sub(r"\n\s*\n", "\n", text)
        text = re.sub(r" +", " ", text).strip()

        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars] + "\n...(已截断)"

        return ToolResult(
            content=f"标题: {title}\n\n{text}",
            metadata={
                "url": final_url, "title": title,
                "content_length": len(text), "truncated": truncated,
                "charset": charset,
            },
        )

    # ------------------------------------------------------------------
    # get_system_info
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_system_info(args: dict) -> ToolResult:
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "hostname": platform.node(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "cwd": os.getcwd(),
        }
        try:
            import psutil
            mem = psutil.virtual_memory()
            info["memory_total_gb"] = round(mem.total / (1024**3), 1)
            info["memory_used_gb"] = round(mem.used / (1024**3), 1)
            disk = psutil.disk_usage(os.getcwd())
            info["disk_total_gb"] = round(disk.total / (1024**3), 1)
            info["disk_free_gb"] = round(disk.free / (1024**3), 1)
        except ImportError:
            pass
        return ToolResult(
            content=json.dumps(info, ensure_ascii=False, indent=2),
            metadata=info,
        )

    # ------------------------------------------------------------------
    # run_command
    # ------------------------------------------------------------------

    @staticmethod
    async def _run_command(args: dict) -> ToolResult:
        command = args["command"]
        logger.warning(f"Agent executing command: {command}")

        process = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        result = stdout.decode("utf-8", errors="replace")
        if stderr:
            result += "\n[STDERR]\n" + stderr.decode("utf-8", errors="replace")
        if len(result) > 4000:
            result = result[:4000] + "\n...(输出过长已截断)"
        return ToolResult(
            content=result or f"命令执行完毕，返回码: {process.returncode}",
            metadata={"command": command, "exit_code": process.returncode},
        )

    # ------------------------------------------------------------------
    # open_app — launch local applications
    # ------------------------------------------------------------------

    @staticmethod
    async def _open_app(args: dict) -> ToolResult:
        name = args["name"].strip().lower()

        # Common Windows app shortcuts
        APP_MAP = {
            # Browsers
            "chrome": "start chrome",
            "edge": "start msedge",
            "firefox": "start firefox",
            "firefox developer": 'start "C:\\Program Files\\Firefox Developer Edition\\firefox.exe"',
            # Editors
            "vscode": "code",
            "cursor": "cursor",
            "notepad": "notepad",
            "notepad++": "start notepad++",
            "sublime": "subl",
            # System
            "explorer": "explorer",
            "calculator": "calc",
            "calc": "calc",
            "terminal": "start cmd",
            "cmd": "start cmd",
            "powershell": "start powershell",
            "settings": "start ms-settings:",
            "taskmgr": "taskmgr",
            "control panel": "control",
            "regedit": "regedit",
            # Media & comms
            "spotify": "start spotify",
            "wechat": 'start "C:\\Program Files (x86)\\Tencent\\WeChat\\WeChat.exe"',
            "qq": 'start "C:\\Program Files (x86)\\Tencent\\QQ\\Bin\\QQ.exe"',
            "qq音乐": 'start "" "D:\\QQ音乐\\QQMusic\\QQMusic.exe"',
            "qqmusic": 'start "" "D:\\QQ音乐\\QQMusic\\QQMusic.exe"',
            # Notes
            "obsidian": "obsidian",
            "typora": "typora",
            # Office
            "word": "start winword",
            "excel": "start excel",
            "powerpoint": "start powerpnt",
            "outlook": "start outlook",
        }

        cmd = APP_MAP.get(name)
        if cmd:
            process = await asyncio.create_subprocess_shell(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            await process.wait()
            return ToolResult(f"已打开 {name}", metadata={"app": name, "command": cmd})

        # Fallback: try directly as exe name or path
        fallback_cmd = f"start {name}" if not name.endswith(".exe") else name
        process = await asyncio.create_subprocess_shell(
            fallback_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        await process.wait()
        if process.returncode == 0:
            return ToolResult(f"已尝试打开 {name}", metadata={"app": name, "command": fallback_cmd})

        return ToolResult(
            f"无法打开 '{name}'，找不到该应用。试试: chrome, vscode, notepad, calculator, explorer 等",
            is_error=True,
        )

    # ------------------------------------------------------------------
    # open_url — open in default browser
    # ------------------------------------------------------------------

    @staticmethod
    async def _open_url(args: dict) -> ToolResult:
        url = args["url"].strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        process = await asyncio.create_subprocess_shell(
            f"start {url}", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        await process.wait()
        return ToolResult(f"已打开: {url}", metadata={"url": url})

    # ------------------------------------------------------------------
    # system_control — safe system operations
    # ------------------------------------------------------------------

    @staticmethod
    async def _system_control(args: dict) -> ToolResult:
        action = args["action"].strip().lower()

        ACTIONS = {
            "lock": "rundll32.exe user32.dll,LockWorkStation",
            "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            "volume_up": '(New-Object -ComObject WScript.Shell).SendKeys([char]175)',
            "volume_down": '(New-Object -ComObject WScript.Shell).SendKeys([char]174)',
            "mute": '(New-Object -ComObject WScript.Shell).SendKeys([char]173)',
        }

        cmd = ACTIONS.get(action)
        if not cmd:
            return ToolResult(
                f"不支持的操作: {action}。支持: {', '.join(ACTIONS.keys())}",
                is_error=True,
            )

        # Volume commands need PowerShell; others can use cmd
        if action.startswith("volume") or action == "mute":
            process = await asyncio.create_subprocess_shell(
                f"powershell -command \"{cmd}\"",
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            process = await asyncio.create_subprocess_shell(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        await process.wait()

        labels = {"lock": "已锁定电脑", "sleep": "电脑即将进入睡眠",
                  "volume_up": "音量已增加", "volume_down": "音量已降低", "mute": "已切换静音"}
        return ToolResult(labels.get(action, f"已执行: {action}"), metadata={"action": action})

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # web_open — search and open result link directly
    # ------------------------------------------------------------------

    @staticmethod
    async def _web_open(args: dict) -> ToolResult:
        query = args["query"]
        site = args.get("site", "baidu").strip().lower()

        # Build search URL based on site
        import urllib.parse
        encoded_q = urllib.parse.quote(query)

        SITES = {
            "bilibili": f"https://search.bilibili.com/all?keyword={encoded_q}&order=click",
            "baidu": f"https://www.baidu.com/s?wd={encoded_q}",
            "bing": f"https://cn.bing.com/search?q={encoded_q}",
            "youtube": f"https://www.youtube.com/results?search_query={encoded_q}",
        }

        search_url = SITES.get(site, SITES["baidu"])
        logger.info(f"web_open: searching {site} for '{query}' → {search_url}")

        # Step 1: fetch the search page to extract top result link
        target_url = ""
        if site == "bilibili":
            target_url = await ToolRegistry._extract_bilibili_video(search_url)

        # Step 2: if we found a target, open it directly
        if target_url:
            import subprocess
            subprocess.Popen(["cmd", "/c", "start", "", target_url],
                             shell=True)
            return ToolResult(
                f"已找到并打开: {target_url}",
                metadata={"query": query, "site": site, "opened": target_url},
            )

        # Step 3: fallback — just open the search page
        import subprocess
        subprocess.Popen(["cmd", "/c", "start", "", search_url], shell=True)
        return ToolResult(
            f"已打开 {site} 搜索页: {query}",
            metadata={"query": query, "site": site, "url": search_url},
        )

    @staticmethod
    async def _extract_bilibili_video(search_url: str) -> str:
        """Search B站 via API and return the most-played video URL."""
        try:
            import urllib.request, urllib.parse, json, ssl
            # Extract keyword from search_url
            kw = urllib.parse.parse_qs(urllib.parse.urlparse(search_url).query).get("keyword", [""])[0]
            if not kw:
                return ""

            api_url = f"https://api.bilibili.com/x/web-interface/search/all/v2?keyword={urllib.parse.quote(kw)}"
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.bilibili.com/",
            })
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                data = json.loads(resp.read())

            if data.get("code") != 0 or not data.get("data"):
                return ""

            # Find video results, sort by play count descending
            videos = []
            for r in data["data"].get("result", []):
                if r.get("result_type") == "video":
                    for v in r.get("data", []):
                        bvid = v.get("bvid", "")
                        play = v.get("play", 0) or 0
                        if bvid:
                            videos.append((play, bvid))

            if not videos:
                return ""

            # Sort by play count (highest first) and return the top video URL
            videos.sort(key=lambda x: x[0], reverse=True)
            top_bv = videos[0][1]
            return f"https://www.bilibili.com/video/{top_bv}"
        except Exception as e:
            logger.debug(f"B站 API 失败: {e}")
        return ""

    # ------------------------------------------------------------------
    # research_trends — last30days skill integration
    # ------------------------------------------------------------------

    LAST30DAYS_SCRIPT = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../.agents/skills/last30days/scripts/last30days.py")
    )

    @staticmethod
    def _find_python311() -> str | None:
        """Find a Python 3.11+ executable (last30days requirement)."""
        cur_dir = os.path.dirname(sys.executable)
        conda_base = os.path.normpath(os.path.join(cur_dir, "..", ".."))  # ~/anaconda3/
        candidates = [
            sys.executable,
            os.path.join(cur_dir, "python3.11"),
            os.path.join(cur_dir, "python3.12"),
            os.path.join(conda_base, "python.exe"),         # conda base env
            os.path.join(conda_base, "python3.11"),
            os.path.join(conda_base, "python3.12"),
            "python3.12", "python3.11", "python3",
        ]
        for candidate in candidates:
            if not candidate:
                continue
            try:
                import subprocess
                result = subprocess.run(
                    [candidate, "--version"],
                    capture_output=True, text=True, timeout=3,
                )
                ver = result.stdout.strip() or result.stderr.strip()
                if "Python 3." in ver:
                    parts = ver.split(".")
                    if len(parts) >= 2 and int(parts[1]) >= 11:
                        return candidate
            except Exception:
                continue
        return None

    @staticmethod
    async def _research_trends(args: dict) -> ToolResult:
        topic = args["topic"]
        sources = args.get("sources", "")

        # Try last30days engine first
        script = ToolRegistry.LAST30DAYS_SCRIPT
        python_bin = ToolRegistry._find_python311() if os.path.isfile(script) else None
        if python_bin:
            cmd = [python_bin, script, "--quick", "--emit", "compact", topic]
            if sources:
                cmd.insert(-1, "--search")
                cmd.insert(-1, sources)

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=os.path.dirname(script),
                )
                stdout, _stderr = await asyncio.wait_for(
                    process.communicate(), timeout=25.0
                )
                output = stdout.decode("utf-8", errors="replace")

                if process.returncode == 0 and output.strip():
                    return ToolResult(
                        content=output[:8000],
                        metadata={"topic": topic, "engine": "last30days", "source_count": 17},
                    )

                # Script ran but returned no useful output — fall through to web fallback
                logger.info(f"last30days returned empty (rc={process.returncode}), falling back to web")
            except (asyncio.TimeoutError, OSError) as e:
                logger.warning(f"last30days script failed: {e}")

        # Fallback: parallel multi-source search via Bing
        return await ToolRegistry._fallback_search(topic)

    @staticmethod
    async def _fallback_search(topic: str) -> ToolResult:
        """Fallback: search multiple queries in parallel using Bing."""
        queries = [
            topic,
            f"{topic} 2026年最新",
            f"{topic} news",
        ]

        async def _search(q: str):
            for searcher in (_search_bing, _search_ddgs):
                try:
                    result = await asyncio.wait_for(_run_sync(searcher, q, 5), timeout=8.0)
                    if result:
                        return result
                except Exception:
                    continue
            return []

        all_results = await asyncio.gather(*[_search(q) for q in queries])
        merged = []
        seen_urls = set()
        for results in all_results:
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    merged.append(r)

        if not merged:
            return ToolResult(
                f"研究 '{topic}' 时无法获取搜索结果，请检查网络后重试",
                is_error=True, metadata={"topic": topic},
            )

        lines = [f"📊 过去30天关于「{topic}」的热门讨论:\n"]
        for i, r in enumerate(merged[:15], 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   {r['url']}")
            if r.get("snippet"):
                lines.append(f"   {r['snippet']}")
            lines.append("")

        return ToolResult(
            content="\n".join(lines),
            metadata={"topic": topic, "result_count": len(merged), "engine": "bing_fallback"},
        )

    # ------------------------------------------------------------------
    # schedule_reminder
    # ------------------------------------------------------------------

    @staticmethod
    async def _schedule_reminder(args: dict) -> ToolResult:
        title = args["title"]
        when = args["when"]
        message = args["message"]

        # Parse 'when' to a unix ms timestamp
        trigger_at = await _run_sync(_parse_time_expression, when)
        if trigger_at is None:
            return ToolResult(
                f"无法解析时间表达式 '{when}'。请用更明确的表达，如 '5分钟后'、'明天上午9点'、'2026-05-22 14:30'",
                is_error=True,
            )

        store = ToolRegistry._store
        if not store:
            return ToolResult("内部错误：存储未初始化", is_error=True)

        prompt = f"[定时提醒] {title}: {message}"
        task = store.create_task(
            title=title,
            task_type="reminder",
            trigger_at=trigger_at,
            prompt=prompt,
        )

        now = int(time.time() * 1000)
        delta = (trigger_at - now) / 1000
        mins = int(delta // 60)
        secs = int(delta % 60)

        return ToolResult(
            content=f"已设置提醒 '{title}'，将在 {mins}分{secs}秒 后提醒你（ID: {task.id}）",
            metadata={"task_id": task.id, "trigger_at": trigger_at, "delta_seconds": delta},
        )

    # ------------------------------------------------------------------
    # list_reminders
    # ------------------------------------------------------------------

    @staticmethod
    async def _list_reminders(args: dict) -> ToolResult:
        store = ToolRegistry._store
        if not store:
            return ToolResult("内部错误：存储未初始化", is_error=True)

        tasks = store.get_pending_tasks()
        if not tasks:
            return ToolResult("当前没有待执行的提醒。")

        now = int(time.time() * 1000)
        lines = ["当前待执行的提醒:\n"]
        for t in tasks:
            delta = max(0, (t.trigger_at - now) // 1000)
            mins = delta // 60
            secs = delta % 60
            status = "单次" if t.interval_minutes == 0 else f"每{t.interval_minutes}分钟"
            lines.append(f"  [{t.id}] {t.title} — {mins}分{secs}秒后 ({status})")
        return ToolResult(content="\n".join(lines), metadata={"count": len(tasks)})

    # ------------------------------------------------------------------
    # cancel_reminder
    # ------------------------------------------------------------------

    @staticmethod
    async def _cancel_reminder(args: dict) -> ToolResult:
        task_id = args["task_id"]
        store = ToolRegistry._store
        if not store:
            return ToolResult("内部错误：存储未初始化", is_error=True)

        ok = store.cancel_task(task_id)
        if ok:
            return ToolResult(content=f"已取消提醒 ID={task_id}")
        else:
            return ToolResult(f"未找到 ID={task_id} 的提醒", is_error=True)


def _parse_time_expression(expr: str) -> int | None:
    """Parse a Chinese natural-language time expression to unix ms."""
    import re

    now = time.time()
    now_ms = int(now * 1000)
    expr = expr.strip()

    # "X分钟后" / "X分钟后提醒我"
    m = re.search(r"(\d+)\s*分[钟]?\s*[后以]?|in\s+(\d+)\s*min", expr, re.IGNORECASE)
    if m:
        minutes = int(m.group(1) or m.group(2))
        return now_ms + minutes * 60_000

    # "X秒后"
    m = re.search(r"(\d+)\s*秒[钟]?\s*[后以]?", expr)
    if m:
        seconds = int(m.group(1))
        return now_ms + seconds * 1000

    # "X小时后"
    m = re.search(r"(\d+)\s*[小]?时\s*[后以]?", expr)
    if m:
        hours = int(m.group(1))
        return now_ms + hours * 3600_000

    # "明天 上午/下午 X点" / "明天X点"
    m = re.search(r"明[天日]\s*(上[午午]|下[午午]|晚[上]|早[上晨])?\s*(\d+)\s*[点时]?", expr)
    if m:
        period = m.group(1) or ""
        hour = int(m.group(2))
        if "下" in period and hour != 12:
            hour += 12
        if "晚" in period and hour < 12:
            hour += 12
        if "上" in period and hour == 12:
            hour = 0
        if "早" in period and hour == 12:
            hour = 0
        # Start of tomorrow
        tm = list(time.localtime(now))
        tm[3:6] = [hour, 0, 0]
        tm[2] += 1  # tomorrow
        target = time.mktime(tuple(tm)) + 86400 if tm[2] > 31 else time.mktime(tuple(tm))
        # Actually, let's use a simpler approach
        from datetime import datetime, timedelta
        tomorrow = datetime.now() + timedelta(days=1)
        target_dt = tomorrow.replace(hour=hour, minute=0, second=0, microsecond=0)
        return int(target_dt.timestamp() * 1000)

    # "今天 上午/下午 X点" / "今天X点"
    m = re.search(r"今[天日]\s*(上[午午]|下[午午]|晚[上]|早[上晨])?\s*(\d+)\s*[点时]?", expr)
    if m:
        period = m.group(1) or ""
        hour = int(m.group(2))
        if "下" in period and hour != 12:
            hour += 12
        if "晚" in period and hour < 12:
            hour += 12
        from datetime import datetime
        target_dt = datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0)
        ts = int(target_dt.timestamp() * 1000)
        if ts <= now_ms:
            ts += 86400_000  # already past, move to tomorrow
        return ts

    # "周X 上午X点" / "下周X"
    day_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    m = re.search(r"(下?周[一二三四五六日天])\s*(上[午午]|下[午午]|晚[上])?\s*(\d+)?\s*[点时]?", expr)
    if m:
        day_str = m.group(1)
        hour = int(m.group(3) or 9)
        period = m.group(2) or ""
        if "下" in period and hour != 12:
            hour += 12
        from datetime import datetime, timedelta
        current_weekday = datetime.now().weekday()
        is_next = "下" in day_str
        target_wd = day_map.get(day_str[-1], 0)
        days_ahead = target_wd - current_weekday
        if days_ahead <= 0:
            days_ahead += 7
        if is_next:
            days_ahead += 7
        target_dt = datetime.now() + timedelta(days=days_ahead)
        target_dt = target_dt.replace(hour=hour, minute=0, second=0, microsecond=0)
        return int(target_dt.timestamp() * 1000)

    # Absolute date/time: "2026-05-22 14:30"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})", expr)
    if m:
        from datetime import datetime
        target_dt = datetime(
            int(m.group(1)), int(m.group(2)), int(m.group(3)),
            int(m.group(4)), int(m.group(5)),
        )
        return int(target_dt.timestamp() * 1000)

    return None


def _def(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def _fmt_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.0f}{unit}"
        size /= 1024
    return f"{size:.0f}TB"
