"""
Send WhatsApp messages — Windows version.

- Opens WhatsApp Desktop via URL scheme (whatsapp://send?phone=...&text=...).
- Sends automatically with pyautogui Enter key press.
- Falls back to WhatsApp Web in the default browser.
- Frequently used contacts are saved to persistent memory.
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
import urllib.parse
import webbrowser
from pathlib import Path

from memory.memory_manager import load_memory, update_memory


AUTO_SEND_DELAY_SECONDS = 2.4
BASE_DIR = Path(__file__).resolve().parent.parent
PHONEBOOK_FILE = BASE_DIR / "memory" / "phone_book.json"


def _normalize_phone(phone_number: str) -> str:
    digits = re.sub(r"\D+", "", phone_number or "")
    if len(digits) == 11 and digits.startswith("0"):
        digits = "90" + digits[1:]
    elif len(digits) == 10:
        digits = "90" + digits
    if len(digits) < 8 or len(digits) > 15:
        raise ValueError(
            "Phone number must be in international format. "
            "E.g.: +905551112233"
        )
    return digits


def _normalize_lookup(text: str) -> str:
    text = (text or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ı", "i")
    text = re.sub(r"\s+", " ", text)
    return text


def _contact_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _normalize_lookup(name)).strip("_") or "contact"


def _load_contacts() -> dict:
    memory = load_memory()
    contacts = memory.get("whatsapp_contacts", {})
    return contacts if isinstance(contacts, dict) else {}


def _load_phone_book() -> dict:
    try:
        if PHONEBOOK_FILE.exists():
            return json.loads(PHONEBOOK_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_phone_book(phone_book: dict):
    PHONEBOOK_FILE.parent.mkdir(parents=True, exist_ok=True)
    PHONEBOOK_FILE.write_text(
        json.dumps(phone_book, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _contact_candidates() -> list[dict]:
    candidates = []
    for source_name, source in (("whatsapp", _load_contacts()), ("phone_book", _load_phone_book())):
        if not isinstance(source, dict):
            continue
        for key, entry in source.items():
            if not isinstance(entry, dict):
                continue
            item = dict(entry)
            item.setdefault("display_name", key)
            item["_source"] = source_name
            item["_key"] = key
            candidates.append(item)
    return candidates


def _match_score(needle: str, candidate: str) -> int:
    candidate_norm = _normalize_lookup(candidate)
    if not candidate_norm:
        return 0
    if candidate_norm == needle:
        return 300
    if candidate_norm.startswith(needle) or needle.startswith(candidate_norm):
        return 220
    if needle in candidate_norm:
        return 160
    needle_parts = needle.split()
    if needle_parts and all(part in candidate_norm for part in needle_parts):
        return 120
    return 0


def _find_contact(recipient_name: str) -> dict | None:
    needle = _normalize_lookup(recipient_name)
    if not needle:
        return None

    best_match = None
    best_score = 0
    for entry in _contact_candidates():
        names = [entry.get("display_name", ""), entry.get("_key", "")]
        aliases = entry.get("aliases", [])
        if isinstance(aliases, list):
            names.extend(str(alias) for alias in aliases)
        elif aliases:
            names.append(str(aliases))
        for name in names:
            score = _match_score(needle, name)
            if score > best_score:
                best_score = score
                best_match = entry
    return best_match


def save_whatsapp_contact(display_name: str, phone_number: str, aliases: str = "") -> str:
    if not display_name or not display_name.strip():
        return "Contact name cannot be empty."
    try:
        normalized_phone = _normalize_phone(phone_number)
    except ValueError as exc:
        return str(exc)

    alias_list = []
    if aliases and aliases.strip():
        alias_list = [part.strip() for part in aliases.split(",") if part.strip()]

    key = _contact_key(display_name)
    update_memory({
        "whatsapp_contacts": {
            key: {
                "value": f"+{normalized_phone}",
                "display_name": display_name.strip(),
                "aliases": alias_list,
            }
        }
    })
    if alias_list:
        return f"{display_name.strip()} saved to WhatsApp contacts. Aliases: {', '.join(alias_list)}"
    return f"{display_name.strip()} saved to WhatsApp contacts."


def _unfold_vcf_lines(text: str) -> list[str]:
    unfolded = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def import_phone_book_from_vcf(vcf_path: str) -> str:
    source = Path(vcf_path).expanduser()
    if not source.exists():
        return f"Phone book file not found: {source}"
    try:
        text = source.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return f"Could not read phone book file: {exc}"

    entries = {}
    current_lines: list[str] = []
    imported = 0
    skipped = 0

    def _flush_card(lines: list[str]):
        nonlocal imported, skipped
        if not lines:
            return
        display_name = ""
        aliases = []
        numbers = []
        for line in lines:
            upper = line.upper()
            if upper.startswith("FN:"):
                display_name = line.split(":", 1)[1].strip()
            elif upper.startswith("N:") and not display_name:
                parts = [p.strip() for p in line.split(":", 1)[1].split(";") if p.strip()]
                if parts:
                    display_name = " ".join(reversed(parts[:2])).strip()
            elif "TEL" in upper and ":" in line:
                number = line.split(":", 1)[1].strip()
                if number:
                    numbers.append(number)
        if not display_name or not numbers:
            skipped += 1
            return
        normalized_numbers = []
        for raw_number in numbers:
            try:
                normalized_numbers.append("+" + _normalize_phone(raw_number))
            except ValueError:
                continue
        if not normalized_numbers:
            skipped += 1
            return
        if " " in display_name:
            aliases.extend(part for part in display_name.split() if len(part) > 1)
        key = _contact_key(display_name)
        entries[key] = {
            "display_name": display_name,
            "value": normalized_numbers[0],
            "numbers": normalized_numbers,
            "aliases": sorted({alias for alias in aliases if _normalize_lookup(alias) != _normalize_lookup(display_name)}),
            "source": "vcf_import",
        }
        imported += 1

    for line in _unfold_vcf_lines(text):
        if line.upper() == "BEGIN:VCARD":
            current_lines = []
        elif line.upper() == "END:VCARD":
            _flush_card(current_lines)
            current_lines = []
        else:
            current_lines.append(line)

    phone_book = _load_phone_book()
    phone_book.update(entries)
    _save_phone_book(phone_book)
    return f"{imported} phone book contacts imported, {skipped} records skipped."


def _open_uri(uri: str) -> tuple[bool, str]:
    try:
        os.startfile(uri)
        return True, "ok"
    except OSError as exc:
        return False, str(exc)


def _open_browser(url: str) -> tuple[bool, str]:
    try:
        if webbrowser.open(url, new=2):
            return True, "default browser"
        os.startfile(url)
        return True, "default browser"
    except Exception as exc:
        return False, f"Could not open browser: {exc}"


def _auto_send_with_pyautogui() -> tuple[bool, str]:
    try:
        import pyautogui  # type: ignore
    except Exception as exc:
        return False, f"pyautogui not found: {exc}"
    try:
        time.sleep(AUTO_SEND_DELAY_SECONDS)
        pyautogui.press("enter")
        return True, "ok"
    except Exception as exc:
        return False, f"pyautogui error: {exc}"


def _open_whatsapp_desktop(phone_number: str, message: str) -> tuple[bool, str]:
    encoded = urllib.parse.quote(message.strip())
    url = f"whatsapp://send?phone={phone_number}&text={encoded}"
    ok, detail = _open_uri(url)
    if not ok:
        return False, f"Could not open WhatsApp Desktop: {detail}"
    return True, "WhatsApp Desktop chat opened."


def _open_whatsapp_web(phone_number: str, message: str) -> tuple[bool, str]:
    encoded = urllib.parse.quote(message.strip())
    url = f"https://web.whatsapp.com/send?phone={phone_number}&text={encoded}"
    return _open_browser(url)


def send_whatsapp_message(
    message: str,
    phone_number: str = "",
    recipient_name: str = "",
    send_now: bool = False,
    app_target: str = "auto",
) -> str:
    if not message or not message.strip():
        return "Message cannot be empty."

    app_target = (app_target or "auto").strip().lower()
    if app_target not in {"auto", "desktop", "web"}:
        app_target = "auto"

    normalized_phone = ""
    if phone_number and phone_number.strip():
        try:
            normalized_phone = _normalize_phone(phone_number)
        except ValueError as exc:
            return str(exc)

    resolved_name = recipient_name.strip() if recipient_name else ""
    contact = _find_contact(resolved_name) if resolved_name else None

    if contact and not normalized_phone:
        stored_phone = str(contact.get("value", "")).strip()
        try:
            normalized_phone = _normalize_phone(stored_phone)
        except ValueError:
            normalized_phone = ""
        resolved_name = str(contact.get("display_name", resolved_name)).strip() or resolved_name
        contact_source = contact.get("_source", "")
    else:
        contact_source = ""

    if resolved_name and normalized_phone and (contact is None or contact.get("_source") == "phone_book"):
        alias_list = contact.get("aliases", []) if isinstance(contact, dict) else []
        aliases = ", ".join(str(a) for a in alias_list) if alias_list else ""
        save_whatsapp_contact(resolved_name, normalized_phone, aliases=aliases)

    if not normalized_phone:
        if resolved_name:
            return (
                f"Could not find a saved phone number for '{resolved_name}'. "
                "Save the contact with their number first."
            )
        return "A contact name or phone number is required for WhatsApp messages."

    source_note = " (found from phone book)" if contact_source == "phone_book" else ""

    if app_target in {"auto", "desktop"}:
        ok, detail = _open_whatsapp_desktop(normalized_phone, message)
        if ok:
            label = resolved_name or f"+{normalized_phone}"
            if not send_now:
                return f"Draft message opened in WhatsApp Desktop for {label}{source_note}."
            ok_send, send_detail = _auto_send_with_pyautogui()
            if ok_send:
                return f"Message sent to {label}{source_note} via WhatsApp Desktop."
            return (
                "WhatsApp Desktop chat opened but auto-send could not complete. "
                f"{send_detail}. pyautogui must be installed and the WhatsApp window must be in the foreground."
            )
        if app_target == "desktop":
            # Don't fall back to web
            return f"Error opening WhatsApp Desktop: {detail}"

    ok, browser_label = _open_whatsapp_web(normalized_phone, message)
    if not ok:
        return browser_label
    if not send_now:
        return (
            f"WhatsApp chat opened in {browser_label} "
            f"with a draft message for {resolved_name or f'+{normalized_phone}'}{source_note}. "
            "Press Enter to send."
        )
    ok_send, send_detail = _auto_send_with_pyautogui()
    if ok_send:
        label = resolved_name or f"+{normalized_phone}"
        return f"Message sent to {label}{source_note} via WhatsApp Web."
    return (
        "WhatsApp Web chat opened but auto-send could not complete. "
        f"{send_detail}. pyautogui must be installed."
    )
