import asyncio
import os
import re
from typing import Tuple, Optional, List

def _find_latest_backup(candidates: List[str]) -> Optional[str]:
    latest_path = None
    latest_mtime = -1.0
    exts = (".tar.gz", ".tgz", ".zip")
    for root in candidates:
        if not root or not os.path.exists(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                if not name.endswith(exts):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    mtime = os.path.getmtime(path)
                    if mtime > latest_mtime:
                        latest_mtime = mtime
                        latest_path = path
                except Exception:
                    continue
    return latest_path


async def run_marzban_backup() -> Tuple[bool, str, Optional[str]]:
    try:
        # Run command; assume bot runs on same server and marzban in PATH or service.
        proc = await asyncio.create_subprocess_shell(
            "marzban backup",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = (stdout or b"").decode("utf-8", errors="ignore")
        # Try to extract path from output
        path: Optional[str] = None
        m = re.search(r"(/[^\s]+\.(?:tar\.gz|tgz|zip))", output)
        if m:
            path = m.group(1)
        if not path:
            # Fallback: search common locations
            candidates = [
                os.getcwd(),
                "/var/lib/marzban/backups",
                "/var/lib/marzban",
                "/opt/marzban/backups",
                "/opt/marzban",
                os.path.expanduser("~/backups"),
            ]
            path = _find_latest_backup(candidates)
        return (proc.returncode == 0, output, path)
    except Exception as e:
        return (False, str(e), None)
