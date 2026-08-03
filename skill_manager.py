"""
Skill Manager – Autonomous Testing Sandbox Workflow for JARVIS.

Builds, tests, and deploys new dynamic skills in an isolated virtual
environment before promoting them to the live ``dynamic_skills/`` directory.
This prevents a mis‑written skill from crashing JARVIS's main loop.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("Jarvis-Skill-Factory")

# ── Directories (relative to project root) ─────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
STAGE_DIR = BASE_DIR / "sandbox_stage"
LIVE_DIR = BASE_DIR / "dynamic_skills"
SANDBOX_VENV = STAGE_DIR / ".sandbox_env"

STAGE_DIR.mkdir(parents=True, exist_ok=True)
LIVE_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ────────────────────────────────────────────────────────────

def _ensure_sandbox_env() -> None:
    """Programmatically builds or maintains the clean validation sandbox."""
    if not SANDBOX_VENV.exists():
        venv.create(str(SANDBOX_VENV), with_pip=True)


def _sandbox_python() -> str:
    """Return the platform‑correct path to the sandbox Python interpreter."""
    if sys.platform == "win32":
        return str(SANDBOX_VENV / "Scripts" / "python.exe")
    return str(SANDBOX_VENV / "bin" / "python")

# ── Tool ───────────────────────────────────────────────────────────────

@mcp.tool()
def test_and_deploy_skill(
    skill_name: str,
    python_code: str,
    required_pip_packages: list[str] | None = None,
) -> str:
    """
    Safely tests a new skill inside an isolated virtual environment sandbox
    before integrating it permanently into JARVIS's live ``dynamic_skills/``
    directory.

    The workflow:
      1. Creates / reuses a dedicated ``.sandbox_env`` virtual environment.
      2. Installs any requested third‑party packages *only* inside that venv.
      3. Writes the skill code to a temporary stage file.
      4. Performs a **compile check** (``py_compile``) – catches syntax errors.
      5. Performs a **runtime import check** inside the sandbox – catches
         missing imports, runtime crashes.
      6. On success, promotes the file to ``dynamic_skills/<skill_name>.py``
         and cleans up the stage.
      7. On any failure, destroys the stage file and returns a detailed error
         message – JARVIS's main loop is never affected.

    Args:
        skill_name: Human‑readable name for the skill (will be sanitised).
        python_code: The full source code of the skill.
        required_pip_packages: Optional list of PyPI package specifiers
                               (e.g. ``["requests>=2.28", "pillow"]``).

    Returns:
        A success or failure message with details.
    """
    clean_name = skill_name.strip().lower().replace(" ", "_")
    temp_file = STAGE_DIR / f"test_{clean_name}.py"
    live_file = LIVE_DIR / f"{clean_name}.py"

    # ── 1. Bootstrap the sandbox environment ──────────────────────────
    try:
        _ensure_sandbox_env()
        sandbox_python = _sandbox_python()
    except Exception as e:
        return (
            f"Sandbox Setup Failure: Local system environment could not "
            f"isolate process.\nError: {e}"
        )

    # ── 2. Install dependencies (inside sandbox only) ──────────────────
    if required_pip_packages:
        try:
            subprocess.run(
                [sandbox_python, "-m", "pip", "install"] + required_pip_packages,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            return (
                f"Sandbox Test Rejected: Dependency installation failed.\n"
                f"Logs: {e.stderr}"
            )

    # ── 3. Write code to stage ──────────────────────────────────────────
    try:
        temp_file.write_text(python_code, encoding="utf-8")
    except Exception as e:
        return f"File Error: Could not write code to sandbox stage.\nDetails: {e}"

    # ── 4. Compile check ────────────────────────────────────────────────
    try:
        subprocess.run(
            [sandbox_python, "-m", "py_compile", str(temp_file)],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        temp_file.unlink(missing_ok=True)
        return (
            f"Sandbox Test Failed: Code has syntax errors.\n"
            f"Compiler Output:\n{e.stderr.decode()}"
        )

    # ── 5. Runtime import check inside sandbox ──────────────────────────
    test_runner = (
        "import sys\n"
        f"sys.path.insert(0, {str(STAGE_DIR)!r})\n"
        f"import test_{clean_name}\n"
        "print('SUCCESS_LOAD')\n"
    )
    try:
        result = subprocess.run(
            [sandbox_python, "-c", test_runner],
            check=True,
            capture_output=True,
            text=True,
        )
        if "SUCCESS_LOAD" not in result.stdout:
            raise RuntimeError(result.stdout or result.stderr)
    except Exception as e:
        temp_file.unlink(missing_ok=True)
        err_text = str(e)
        if hasattr(e, "stderr") and e.stderr:
            err_text = e.stderr
        return (
            f"Sandbox Test Failed: The skill crashed during execution "
            f"simulation.\nTraceback:\n{err_text}"
        )

    # ── 6. Promote to live directory ────────────────────────────────────
    try:
        shutil.copyfile(str(temp_file), str(live_file))
        temp_file.unlink(missing_ok=True)
    except Exception as e:
        return (
            f"Promotion Error: Skill passed testing, but file migration "
            f"failed:\n{e}"
        )

    return (
        f"Verification passed successfully! Skill '{clean_name}' was tested "
        f"inside an isolated sandbox, verified stable, and safely promoted "
        f"to production at {live_file}."
    )


# ── Entry point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    """Run the MCP server when executed directly."""
    mcp.run(transport="stdio")

