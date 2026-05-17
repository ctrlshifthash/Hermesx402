"""Best-effort sandboxed Python execution for the agent's `code` tool.

ISOLATION (honest scope):
- Separate `python -I` (isolated) subprocess — no site, no env-derived paths.
- Fresh temp working dir as cwd; deleted after.
- **Stripped environment**: only PATH/SystemRoot pass through, so the app's
  secrets (OPENROUTER/PRIVY/x402 keys, DB URL) are NOT reachable from agent
  code.
- Hard wall-clock timeout; output capped.

NOT guaranteed: full OS/network isolation. True hardening = a container
(Docker/gVisor) — tracked as the production follow-up. Adequate for local,
single-user, budget-bounded use; labelled as such in the UI/README.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from dataclasses import dataclass

_TIMEOUT = 15
_MAX_OUT = 4000
_SAFE_ENV_KEYS = ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "LANG")


@dataclass
class CodeResult:
    ok: bool
    stdout: str
    stderr: str
    timed_out: bool = False


async def run_python(code: str) -> CodeResult:
    workdir = tempfile.mkdtemp(prefix="al_sbx_")
    env = {k: os.environ[k] for k in _SAFE_ENV_KEYS if k in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-I", "-c", code,
            cwd=workdir,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(
                proc.communicate(), timeout=_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return CodeResult(False, "", "execution timed out", True)
        return CodeResult(
            proc.returncode == 0,
            out.decode(errors="replace")[:_MAX_OUT],
            err.decode(errors="replace")[:_MAX_OUT],
        )
    except Exception as exc:  # noqa: BLE001
        return CodeResult(False, "", f"sandbox error: {exc}")
    finally:
        import shutil  # noqa: PLC0415

        shutil.rmtree(workdir, ignore_errors=True)
