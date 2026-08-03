"""
Script to translate all Turkish text in ui.py to English.
Run: python translate_ui.py
"""
import re

with open("ui.py", "r", encoding="utf-8") as f:
    content = f.read()

replacements = [
    # ── Comments ─────────────────────────────────────────────────────────────
    ("# ── Boyutlar ─────────────────────────────────────────────────────────────────", "# ── Dimensions ─────────────────────────────────────────────────────────────────"),
    ("# ── Lokal font yukleyicisi ──────────────────────────────────────────────────", "# ── Local font loader ──────────────────────────────────────────────────────"),
    ("# Fonts/ klasorundeki tum .ttf dosyalarini *private* olarak yukleriz: sistem", "# We load all .ttf files in the Fonts/ folder as *private*: no system-wide"),
    ("# geneline kurulum gerekmez, sadece bu surec icinde gorunur olur. Boylece", "# installation needed, only visible within this process. This way,"),
    ("# Orbitron gibi futuristic fontlari sadece klasore birakmak yeterli.", "# futuristic fonts like Orbitron just need to be placed in the folder."),
    ("# ── Font sistemi ─────────────────────────────────────────────────────────────", "# ── Font system ─────────────────────────────────────────────────────────────"),
    ("# Govde icin Grift okunakli kaliyor; baslik/HUD icin Orbitron sci-fi hissi", "# Grift stays readable for body text; Orbitron gives a sci-fi feel for"),
    ("# veriyor. Orbitron yoksa Tk otomatik olarak varsayilana duser.", "# headings/HUD. If Orbitron is missing, Tk falls back to the default."),
    ("""\"\"\"create_text + hafif neon hale. glow_color daha sonuk bir tonda olmali.\"\"\"""", """\"\"\"create_text + slight neon glow. glow_color should be in a dimmer tone.\"\"\""""),
    ("# Windows MCI (winmm) ile MP3 calma — ek bagimlilik gerektirmez.", "# MP3 playback with Windows MCI (winmm) — no additional dependencies required."),
    ("\"\"\"Tek bir MCI MP3 calma instance'i.\"\"\"", "\"\"\"A single MCI MP3 playback instance.\"\"\""),
    ("# MCI dosya yolunun tek bir kelimede olmasi icin tirnaklarla sariyoruz.", "# We wrap the MCI file path in quotes to ensure it's treated as a single word."),
    ("raise RuntimeError(\"winmm yuklenemedi\")", "raise RuntimeError(\"winmm could not be loaded\")"),
    ("raise RuntimeError(f\"MCI dosyayi acamadi: {path}\")", "raise RuntimeError(f\"MCI could not open file: {path}\")"),
    ("raise RuntimeError(f\"MCI calma baslayamadi: {path}\")", "raise RuntimeError(f\"MCI could not start playback: {path}\")"),
    ("# macOS window manager bazen geometry'yi override eder, tekrar zorla.", "# macOS window manager sometimes overrides geometry, force it again."),
    ("# Birkaç saniye sonra topmost'u kapat (normal davranış)", "# Close topmost after a few seconds (normal behavior)"),
    ("# ── Partiküller (arka plan, az sayıda) ───────────────────────────────", "# ── Particles (background, small number) ───────────────────────────────"),
    ("# Orb tıklama = pause/resume", "# Orb click = pause/resume"),
    ("# ── Sağlık overlay ───────────────────────────────────────────────────", "# ── Health overlay ───────────────────────────────────────────────────"),
    ('"Hava durumu yükleniyor..."', '"Loading weather..."'),
    ('"Vitals yükleniyor..."', '"Loading vitals..."'),
    ("# ── Sağlık overlay (sol panel) ────────────────────────────────────────────", "# ── Health overlay (left panel) ────────────────────────────────────────────"),
    ("# ── Sol panel ─────────────────────────────────────────────────────────────", "# ── Left panel ─────────────────────────────────────────────────────────────"),
    ("# ── Sağ panel ─────────────────────────────────────────────────────────────", "# ── Right panel ─────────────────────────────────────────────────────────────"),
    ("# ── ORB (ana çizim) ───────────────────────────────────────────────────────", "# ── ORB (main drawing) ───────────────────────────────────────────────────────"),
    ("# ── Ana çizim ─────────────────────────────────────────────────────────────", "# ── Main drawing ─────────────────────────────────────────────────────────────"),
    ("# ── Arka plan ────────────────────────────────────────────────────────", "# ── Background ────────────────────────────────────────────────────────"),
    ("# Nokta ızgarası — çok ince", "# Dot grid — very subtle"),
    ("# Tarama çizgisi (yavaş, çok soluk)", "# Scan line (slow, very faint)"),
    ("# ── Bölücü çizgiler (ince, soluk) ────────────────────────────────────", "# ── Divider lines (thin, faint) ────────────────────────────────────"),
    ("# ── Yan paneller ──────────────────────────────────────────────────────", "# ── Side panels ──────────────────────────────────────────────────────"),
    ("# ── HEADER ───────────────────────────────────────────────────────────", "# ── HEADER ───────────────────────────────────────────────────────────"),
    ("# Alt çizgi — teal parlak", "# Bottom line — bright teal"),
    ("# Büyük başlık", "# Large title"),
    ("# Sol: model badge", "# Left: model badge"),
    ("# Sağ: durum indikatörü", "# Right: status indicator"),
    ("# ── FOOTER ───────────────────────────────────────────────────────────", "# ── FOOTER ───────────────────────────────────────────────────────────"),
    ("# ── State ────────────────────────────────────────────────────────────", "# ── State ────────────────────────────────────────────────────────────"),
    ("# ── Callbacks ────────────────────────────────────────────────────────", "# ── Callbacks ────────────────────────────────────────────────────────"),
    ("# ── Voice ────────────────────────────────────────────────────────────", "# ── Voice ────────────────────────────────────────────────────────────"),
    ("# ── Sound ────────────────────────────────────────────────────────────", "# ── Sound ────────────────────────────────────────────────────────────"),
    ("# ── Stats ────────────────────────────────────────────────────────────", "# ── Stats ────────────────────────────────────────────────────────────"),
    ("# ── Typing ───────────────────────────────────────────────────────────", "# ── Typing ───────────────────────────────────────────────────────────"),
    ("# ── Canvas ───────────────────────────────────────────────────────────", "# ── Canvas ───────────────────────────────────────────────────────────"),
    ("# ── Log ──────────────────────────────────────────────────────────────", "# ── Log ──────────────────────────────────────────────────────────────"),
    ("# ── Social bar ───────────────────────────────────────────────────────────", "# ── Social bar ───────────────────────────────────────────────────────────"),
    ("# ── Shutdown button (sağ alt, büyük) ────────────────────────────────────", "# ── Shutdown button (bottom right, large) ────────────────────────────────"),
    ("# Köşe braket stili", "# Corner bracket style"),
    ("# ── SFX toggle ───────────────────────────────────────────────────────────", "# ── SFX toggle ───────────────────────────────────────────────────────────"),
    ("# ── Voice selector ───────────────────────────────────────────────────────", "# ── Voice selector ───────────────────────────────────────────────────────"),
    ("# ── Mute button ──────────────────────────────────────────────────────────", "# ── Mute button ──────────────────────────────────────────────────────────"),
    ("# ── Pause button ─────────────────────────────────────────────────────────", "# ── Pause button ─────────────────────────────────────────────────────────"),
    ("# ── Orb tıklama = pause ──────────────────────────────────────────────────", "# ── Orb click = pause ──────────────────────────────────────────────────"),
    ("# ── Mini floating window ─────────────────────────────────────────────────", "# ── Mini floating window ─────────────────────────────────────────────────"),
    ("# ── State containers ─────────────────────────────────────────────", "# ── State containers ─────────────────────────────────────────────"),
    ("# ── Top bar: orb + state + pin + expand + drag + close ───────────", "# ── Top bar: orb + state + pin + expand + drag + close ───────────"),
    ("# ── Middle: state-aware animation strip ──────────────────────────", "# ── Middle: state-aware animation strip ──────────────────────────"),
    ("# ── Last message line ────────────────────────────────────────────", "# ── Last message line ────────────────────────────────────────────"),
    ("# ── Chat history (hidden until expanded) ─────────────────────────", "# ── Chat history (hidden until expanded) ─────────────────────────"),
    ("# ── Quick actions row ────────────────────────────────────────────", "# ── Quick actions row ────────────────────────────────────────────"),
    ("# ── Input row ────────────────────────────────────────────────────", "# ── Input row ────────────────────────────────────────────────────"),
    ("# ── Dragging ─────────────────────────────────────────────────────", "# ── Dragging ─────────────────────────────────────────────────────"),
    ("# ── Submit ───────────────────────────────────────────────────────", "# ── Submit ───────────────────────────────────────────────────────"),
    ("# ── Stash refs ───────────────────────────────────────────────────", "# ── Stash refs ───────────────────────────────────────────────────"),
    ("# ── Input bar ────────────────────────────────────────────────────────────", "# ── Input bar ────────────────────────────────────────────────────────────"),
    ("# ── State & callbacks ────────────────────────────────────────────────────", "# ── State & callbacks ────────────────────────────────────────────────────"),
    ("# ── Log ──────────────────────────────────────────────────────────────────", "# ── Log ──────────────────────────────────────────────────────────────────"),
    ("# ── Stats ────────────────────────────────────────────────────────────────", "# ── Stats ────────────────────────────────────────────────────────────────"),
    ("# ── Animation loop ───────────────────────────────────────────────────────", "# ── Animation loop ───────────────────────────────────────────────────────"),
    ("# ── Yardımcı ─────────────────────────────────────────────────────────────", "# ── Helper ─────────────────────────────────────────────────────────────"),
    ("# ── Health overlay (sol panel) ────────────────────────────────────────────", "# ── Health overlay (left panel) ────────────────────────────────────────────"),
    ("# ── Sol panel ─────────────────────────────────────────────────────────────", "# ── Left panel ─────────────────────────────────────────────────────────────"),
    ("# ── Sağ panel ─────────────────────────────────────────────────────────────", "# ── Right panel ─────────────────────────────────────────────────────────────"),
    ("# ── ORB (ana çizim) ───────────────────────────────────────────────────────", "# ── ORB (main drawing) ───────────────────────────────────────────────────────"),
    ("# ── Ana çizim ─────────────────────────────────────────────────────────────", "# ── Main drawing ─────────────────────────────────────────────────────────────"),
    ("# ── Arka plan ────────────────────────────────────────────────────────", "# ── Background ────────────────────────────────────────────────────────"),
    ("# ── Bölücü çizgiler (ince, soluk) ────────────────────────────────────", "# ── Divider lines (thin, faint) ────────────────────────────────────"),
    ("# ── Yan paneller ──────────────────────────────────────────────────────", "# ── Side panels ──────────────────────────────────────────────────────"),
    ("# ── HEADER ───────────────────────────────────────────────────────────", "# ── HEADER ───────────────────────────────────────────────────────────"),
    ("# ── FOOTER ───────────────────────────────────────────────────────────", "# ── FOOTER ───────────────────────────────────────────────────────────"),

    # ── String values (UI labels, status messages, etc.) ────────────────────
    ('"SYS: Mikrofon kapatıldı."', '"SYS: Microphone muted."'),
    ('"SYS: Mikrofon açık."', '"SYS: Microphone unmuted."'),
    ('"SYS: JARVIS duraklatıldı."', '"SYS: JARVIS paused."'),
    ('"SYS: JARVIS devam ediyor..."', '"SYS: JARVIS resuming..."'),
    ('"SYS: JARVIS kapatılıyor..."', '"SYS: JARVIS shutting down..."'),
    ('"SYS: JARVIS duraklatılmış durumda."', '"SYS: JARVIS is paused."'),
    ('"SYS: JARVIS duraklatılmış durumda. Devam etmek için pause\'u kapat."', '"SYS: JARVIS is paused. Unpause to continue."'),
    ('"SYS: ⏹ Ses kesildi."', '"SYS: ⏹ Voice stopped."'),
    ('"SYS: API ayarlari guncellendi."', '"SYS: API settings updated."'),
    ('"SYS: JARVIS hazır. Dinliyorum..."', '"SYS: JARVIS ready. Listening..."'),
    ('"Henüz not edilebilir hata yok.\\n"', '"No notable errors yet.\\n"'),
    ('"Gemini hazir"', '"Gemini ready"'),
    ('"Gemini API eksik"', '"Gemini API missing"'),
    ('"YouTube hazir"', '"YouTube ready"'),
    ('"YouTube ayari eksik"', '"YouTube config missing"'),
    ('"Kanal: {handle_text}"', '"Channel: {handle_text}"'),
    ('"@handle girilmedi"', '"@handle not set"'),

    # ── Weather/Health fallback strings ─────────────────────────────────────
    ('"alınamadı"', '"unavailable"'),
    ('"alınamadi"', '"unavailable"'),
    ('"Hava durumu alınamadı."', '"Weather data unavailable."'),
    ('"Sağlık verisi alınamadı."', '"Health data unavailable."'),
    ('"Sağlık özeti hazır değil."', '"Health summary not ready."'),
    ('"Anlık veri hazır."', '"Live data ready."'),
    ('" derece"', '"°C"'),

    # ── Setup UI ────────────────────────────────────────────────────────────
    ('"◈ API AYARLARI"', '"◈ API SETTINGS"'),
    ('"◈ İLK KURULUM GEREKLİ"', '"◈ INITIAL SETUP REQUIRED"'),
    ('"Backend seç ve ayarları güncelle."', '"Select backend and update settings."'),
    ('"Gemini Cloud veya LM Studio (yerel) seç. LM Studio için API anahtarı gerekmez."', '"Choose Gemini Cloud or LM Studio (local). LM Studio does not require an API key."'),
    ('"BACKEND"', '"BACKEND"'),
    ('"Gemini Cloud"', '"Gemini Cloud"'),
    ('"LM Studio (Yerel)"', '"LM Studio (Local)"'),
    ('"GEMINI API KEY"', '"GEMINI API KEY"'),
    ('"YOUTUBE API KEY"', '"YOUTUBE API KEY"'),
    ('"YOUTUBE HANDLE / CHANNEL"', '"YOUTUBE HANDLE / CHANNEL"'),
    ('"LM STUDIO URL  (yerel mod)"', '"LM STUDIO URL  (local mode)"'),
    ('"LM STUDIO MODEL ID"', '"LM STUDIO MODEL ID"'),
    ('"▸ KAYDET"', '"▸ SAVE"'),
    ('"KAPAT"', '"CLOSE"'),

    # ── Command processing keywords ─────────────────────────────────────────
    # These are Turkish stop words that users might type
    ('text.lower() in ("sus", "dur", "stop", "sessiz", "kes")', 'text.lower() in ("stop", "suspend", "silence", "shut", "cease")'),

    # ── Mini window mic icon refresh comment ────────────────────────────────
    ('"""Mic ikonunu mute durumuna göre günceller."""', '"""Update mic icon based on mute state."""'),

    # ── Debug entries ───────────────────────────────────────────────────────
    ('"Henüz not edilebilir hata yok.\\n"', '"No notable errors yet.\\n"'),

    # ── _parse_weather_card ─────────────────────────────────────────────────
    ('"alınamadı"', '"unavailable"'),
    ('"alınamadi"', '"unavailable"'),
    ('" için"', '" for"'),
    ('" derece"', '"°C"'),

    # ── _parse_health_card ──────────────────────────────────────────────────
    ('"Sağlık verisi alınamadı."', '"Health data unavailable."'),
    ('"Sağlık özeti hazır değil."', '"Health summary not ready."'),

    # ── _refresh_brief_cards ────────────────────────────────────────────────
    ('"Hava durumu alınamadı."', '"Weather data unavailable."'),
    ('"Sağlık verisi alınamadı."', '"Health data unavailable."'),

    # ── _save_api_key ───────────────────────────────────────────────────────
    ('"SYS: API ayarlari guncellendi."', '"SYS: API settings updated."'),
    ('"SYS: JARVIS hazır. Dinliyorum..."', '"SYS: JARVIS ready. Listening..."'),

    # ── Gemini modunda anahtar zorunlu; LM Studio modunda degil. ────────────
    ('# Gemini modunda anahtar zorunlu; LM Studio modunda degil.', '# API key required in Gemini mode; not required in LM Studio mode.'),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"Replaced: {old[:50]}...")
    else:
        print(f"NOT FOUND: {old[:50]}...")

with open("ui.py", "w", encoding="utf-8") as f:
    f.write(content)

print("\nDone! All translations applied.")
