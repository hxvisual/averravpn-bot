import asyncio
from typing import Tuple

async def run_marzban_backup() -> Tuple[bool, str]:
    try:
        # Run command; assume bot runs on same server and marzban in PATH or service.
        proc = await asyncio.create_subprocess_shell(
            "marzban backup",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = (stdout or b"").decode("utf-8", errors="ignore")
        return (proc.returncode == 0, output)
    except Exception as e:
        return (False, str(e))
