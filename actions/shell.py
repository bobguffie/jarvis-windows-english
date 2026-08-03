"""
Run terminal commands — Windows PowerShell.
"""

import subprocess


BLOCKED = [
    "format c:",
    "format /q",
    "del /f /s /q c:\\",
    "rd /s /q c:\\",
    "rmdir /s /q c:\\",
    "shutdown",
    "logoff",
    "diskpart",
    "cipher /w:",
    "fsutil file setzerodata",
    "reg delete hklm",
    "bcdedit",
]

# Standalone commands that leave a mark (actually delete / change permissions)
_PREFIX_BLOCK = (
    "del ", "erase ", "rd ", "rmdir ", "format ",
    "takeown ", "icacls ", "attrib +s",
    "remove-item ", "rm ", "ri ",
)


def shell_run(command: str, timeout: int = 30) -> str:
    if not command:
        return "No command specified."

    cmd_lower = command.lower().strip()

    if cmd_lower.startswith(_PREFIX_BLOCK):
        return (
            "Security: Commands that modify files or permissions are not executed directly. "
            "Try a safer, more specific command."
        )

    for blocked in BLOCKED:
        if blocked in cmd_lower:
            return f"Security: This command is blocked -> {blocked}"

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=timeout,
        )
        output = (result.stdout + result.stderr).strip()
        if not output:
            return "Command executed successfully (no output)."
        if len(output) > 800:
            output = output[:800] + "\n... (output truncated)"
        return output
    except subprocess.TimeoutExpired:
        return f"Command timed out ({timeout}s)."
    except Exception as e:
        return f"Error: {e}"
