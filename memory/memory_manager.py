"""
Persistent memory — saved to JSON file.
https://github.com/bnsware
"""

import json
import re
import unicodedata
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent
MEMORY_FILE = BASE_DIR / "memory" / "memory.json"


def load_memory() -> dict:
    try:
        if MEMORY_FILE.exists():
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def update_memory(data: dict):
    mem = load_memory()
    _deep_merge(mem, data)
    _write_memory(mem)


def _write_memory(mem: dict):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, indent=2, ensure_ascii=False)


def _deep_merge(base: dict, update: dict):
    for k, v in update.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def _normalize_text(text: str) -> str:
    text = (text or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ı", "i")
    return " ".join(text.split())


def _entry_value_text(value) -> str:
    if isinstance(value, dict):
        base = value.get("value")
        if base is not None:
            return str(base)
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _tokenize_text(text: str) -> list[str]:
    normalized = _normalize_text(text)
    return [token for token in re.split(r"[^a-z0-9]+", normalized) if token]


def _entry_matches(needle: str, category: str, item_key: str, item_value) -> bool:
    haystacks = [
        _normalize_text(category),
        _normalize_text(item_key),
        _normalize_text(_entry_value_text(item_value)),
    ]
    if any(needle in hay for hay in haystacks):
        return True

    tokens = [tok for tok in _tokenize_text(needle) if len(tok) >= 3]
    if not tokens:
        return False

    entry_tokens: list[str] = []
    for hay in haystacks:
        entry_tokens.extend(_tokenize_text(hay))

    matched = 0
    for token in tokens:
        if any(token in entry_token or entry_token in token for entry_token in entry_tokens):
            matched += 1

    if len(tokens) == 1:
        return matched == 1
    return matched >= min(2, len(tokens))


def delete_memory(category: str = "", key: str = "", match_text: str = "") -> str:
    mem = load_memory()
    if not mem:
        return "No records in memory to delete."

    category = (category or "").strip()
    key = (key or "").strip()
    match_text = (match_text or "").strip()

    if category and key:
        bucket = mem.get(category)
        if isinstance(bucket, dict) and key in bucket:
            del bucket[key]
            if not bucket:
                mem.pop(category, None)
            _write_memory(mem)
            return f"{category}/{key} removed from memory."
        return "Could not find this memory record."

    needle = _normalize_text(match_text or key)
    if not needle:
        return "category/key or match_text is required to delete."

    for cat, bucket in list(mem.items()):
        if not isinstance(bucket, dict):
            if _entry_matches(needle, cat, cat, bucket):
                del mem[cat]
                _write_memory(mem)
                return f"{cat} removed from memory."
            continue

        for item_key, item_value in list(bucket.items()):
            if _entry_matches(needle, cat, item_key, item_value):
                del bucket[item_key]
                if not bucket:
                    mem.pop(cat, None)
                _write_memory(mem)
                return f"{cat}/{item_key} removed from memory."

    return "Could not find a matching memory record."


def format_memory_for_prompt(memory: dict) -> str:
    if not memory:
        return ""
    lines = ["[USER INFORMATION]"]
    for category, items in memory.items():
        if isinstance(items, dict):
            for key, val in items.items():
                if category == "whatsapp_contacts" and isinstance(val, dict):
                    display_name = val.get("display_name", key)
                    value = val.get("value", "")
                    aliases = val.get("aliases", [])
                    alias_str = ""
                    if isinstance(aliases, list) and aliases:
                        alias_str = f" aliases={', '.join(str(a) for a in aliases)}"
                    lines.append(f"  {category}/{display_name}: {value}{alias_str}")
                else:
                    value = val.get("value", val) if isinstance(val, dict) else val
                    lines.append(f"  {category}/{key}: {value}")
        else:
            lines.append(f"  {category}: {items}")
    return "\n".join(lines)
