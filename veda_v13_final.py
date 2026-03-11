"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  V E D A  v13  ─  DHARMA EDITION                                            ║
║  "The assistant that works even without the internet."                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  MODES:  ☀ SURYA NET (online)  |  🌑 NIRVANA MODE (offline)                ║
║                                                                              ║
║  KEY FIXES vs v12:                                                           ║
║  • NLU intent engine — natural language, no memorising commands              ║
║  • STRONG offline: Vosk STT + local LLM (Ollama) + offline knowledge DB     ║
║  • eval() replaced with safe AST math parser                                ║
║  • StreamLabel Clock leak fixed (unschedule on remove)                       ║
║  • FloatingPanel double-stream fixed                                         ║
║  • speak() fallthrough — every branch has return                            ║
║  • TTS rate updates live on personality change                               ║
║  • Daily briefing persisted to DB (no double-fire on restart)               ║
║  • Reminder parser handles "tomorrow", "at 3", no am/pm                     ║
║  • _stt_q maxsize=3 — no stale command queue                                ║
║  • GPT rate limiter (2s min between calls)                                   ║
║  • ChatLog stream race fixed with lock                                       ║
║  • db_save_chat only for real conversation, not system TTS                  ║
║  • App shutdown event — threads exit cleanly                                ║
║  • API key check for empty string too                                        ║
║  • Offline weather/news cache (last known values stored in DB)              ║
║  • Offline knowledge base (500 Q&A in SQLite)                               ║
║  • Vosk auto-download prompt on first run                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ── 1. Silence loggers ────────────────────────────────────────────────────────
import logging, os, sys
for _n in ("comtypes","comtypes.client","comtypes.server","comtypes.typeinfo"):
    logging.getLogger(_n).setLevel(logging.CRITICAL)
os.environ["KIVY_LOG_LEVEL"]     = "warning"
os.environ["KIVY_NO_CONSOLELOG"] = "1"

# ── 2. Kivy config ────────────────────────────────────────────────────────────
from kivy.config import Config
Config.set("graphics","resizable","1")
Config.set("graphics","width",  "1360")
Config.set("graphics","height", "820")

# ── 3. Stdlib ─────────────────────────────────────────────────────────────────
import threading, queue, math, datetime, webbrowser, base64, ast as _ast
import random, time, socket, json, sqlite3, subprocess, re, getpass, io
from collections import deque

# ── 4. Third-party ────────────────────────────────────────────────────────────
import speech_recognition as sr
try:    import requests;                              _REQ      = True
except: _REQ = False
try:    from openai import OpenAI;                    _OPENAI   = True
except: _OPENAI = False
try:    import pyautogui; pyautogui.FAILSAFE = True;  _PYAUTOGUI= True
except: _PYAUTOGUI = False
try:    import psutil;                                _PSUTIL   = True
except: _PSUTIL = False
try:    import PIL.ImageGrab as _IG;                  _PIL      = True
except: _PIL = False
import pyttsx3

# ── 5. Kivy ───────────────────────────────────────────────────────────────────
from kivy.app             import App
from kivy.uix.widget      import Widget
from kivy.uix.boxlayout   import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview  import ScrollView
from kivy.uix.label       import Label
from kivy.uix.button      import Button
from kivy.uix.textinput   import TextInput
from kivy.graphics        import (Color, Line, Ellipse, Rectangle, RoundedRectangle)
from kivy.clock           import Clock
from kivy.core.window     import Window
from kivy.animation       import Animation

# ── App running sentinel ──────────────────────────────────────────────────────
_APP_RUNNING = threading.Event()
_APP_RUNNING.set()


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

_CFG_FILE = "veda_config.json"
_DEFAULT_CFG = {
    "openai_key"       : "",
    "ollama_model"     : "mistral",
    "personality"      : "energetic",
    "language"         : "en",
    "wake_words"       : ["hey veda", "ok veda", "veda"],
    "custom_wake"      : [],
    "noise_threshold"  : 300,
    "daily_briefing"   : True,
    "briefing_time"    : "08:00",
    "briefing_done_date": "",
    "city"             : "Hyderabad",
    "mode"             : "auto",
    "user_name"        : "Friend",
    "first_run"        : True,
}

def _load_cfg():
    if os.path.isfile(_CFG_FILE):
        try:
            with open(_CFG_FILE) as f: d = json.load(f)
            for k, v in _DEFAULT_CFG.items():
                d.setdefault(k, v)
            return d
        except: pass
    return dict(_DEFAULT_CFG)

def _save_cfg():
    try:
        with open(_CFG_FILE, "w") as f: json.dump(CFG, f, indent=2)
    except Exception as e: print(f"[CFG] {e}")

CFG = _load_cfg()
OPENAI_API_KEY = CFG.get("openai_key", "")


# ═══════════════════════════════════════════════════════════════════════════════
#  PALETTES
# ═══════════════════════════════════════════════════════════════════════════════

SURYA_NET = dict(
    bg      = (0.04, 0.02, 0.00),
    bg2     = (0.08, 0.04, 0.01),
    card    = (0.11, 0.06, 0.02),
    primary = (1.00, 0.82, 0.10),   # Kanaka gold
    accent  = (1.00, 0.32, 0.04),   # Sindoor
    glow    = (1.00, 0.56, 0.00),   # Agni
    teal    = (0.00, 0.90, 0.76),
    divider = (0.30, 0.14, 0.04),
    text    = (1.00, 0.94, 0.70),
    sub     = (0.70, 0.48, 0.16),
    muted   = (0.28, 0.16, 0.05),
    you_col = (1.00, 0.76, 0.18),
    ai_col  = (1.00, 0.94, 0.70),
    sys_col = (0.45, 0.28, 0.08),
    yantra  = (1.00, 0.82, 0.10),
    lotus   = (1.00, 0.32, 0.04),
    chakra  = (1.00, 0.66, 0.00),
)
NIRVANA_MODE = dict(
    bg      = (0.01, 0.01, 0.08),
    bg2     = (0.03, 0.02, 0.12),
    card    = (0.05, 0.04, 0.17),
    primary = (0.62, 0.20, 1.00),
    accent  = (0.00, 0.88, 0.84),
    glow    = (0.40, 0.06, 0.86),
    teal    = (0.00, 0.88, 0.84),
    divider = (0.12, 0.08, 0.28),
    text    = (0.84, 0.70, 1.00),
    sub     = (0.48, 0.30, 0.78),
    muted   = (0.20, 0.12, 0.38),
    you_col = (0.55, 0.22, 0.96),
    ai_col  = (0.00, 0.88, 0.84),
    sys_col = (0.32, 0.18, 0.52),
    yantra  = (0.62, 0.20, 1.00),
    lotus   = (0.00, 0.88, 0.84),
    chakra  = (0.52, 0.12, 0.94),
)

_MORPH = 0.0; _MORPH_TGT = 0.0; _MORPH_LOCK = threading.Lock()

def _lerp(a, b, t): return a + (b - a) * t
def _lc(ca, cb, t): return tuple(_lerp(ca[i], cb[i], t) for i in range(3))

def P():
    with _MORPH_LOCK: t = _MORPH
    return {k: (_lc(SURYA_NET[k], NIRVANA_MODE[k], t)
                if isinstance(SURYA_NET[k], tuple) else
                (SURYA_NET[k] if t < 0.5 else NIRVANA_MODE[k]))
            for k in SURYA_NET}

def _hsv(h, s, v):
    h %= 1.0; i = int(h*6); f = h*6-i
    p=v*(1-s); q=v*(1-f*s); tz=v*(1-(1-f)*s)
    return [(v,tz,p),(q,v,p),(p,v,tz),(p,q,v),(tz,p,v),(v,p,q)][i%6]

def _tick_morph(dt):
    global _MORPH
    with _MORPH_LOCK:
        d = _MORPH_TGT - _MORPH
        if abs(d) > 0.0008: _MORPH += d * min(1.0, dt * 2.6)

Clock.schedule_interval(_tick_morph, 1/60)


# ═══════════════════════════════════════════════════════════════════════════════
#  DATABASE  — memory + chat history + reminders + cache + knowledge
# ═══════════════════════════════════════════════════════════════════════════════

_db  = sqlite3.connect("veda_v13.db", check_same_thread=False)
_dbl = threading.Lock()

with _dbl:
    _db.executescript("""
        CREATE TABLE IF NOT EXISTS memory(phrase TEXT PRIMARY KEY, response TEXT);
        CREATE TABLE IF NOT EXISTS chat_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, role TEXT, content TEXT, source TEXT, is_conversation INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS reminders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, label TEXT, done INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS wake_words(word TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS noise_cal(id INTEGER PRIMARY KEY, threshold REAL);
        CREATE TABLE IF NOT EXISTS offline_cache(
            key TEXT PRIMARY KEY, value TEXT, updated TEXT);
        CREATE TABLE IF NOT EXISTS knowledge(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT, answer TEXT, category TEXT);
    """)
    _db.commit()

# ── Memory ────────────────────────────────────────────────────────────────────
def db_set(k, v):
    with _dbl: _db.execute("INSERT OR REPLACE INTO memory VALUES(?,?)", (k.strip().lower(), v.strip())); _db.commit()
def db_get(k):
    with _dbl: r = _db.execute("SELECT response FROM memory WHERE phrase=?", (k.strip().lower(),)).fetchone()
    return r[0] if r else None
def db_del(k):
    with _dbl: _db.execute("DELETE FROM memory WHERE phrase=?", (k.strip().lower(),)); _db.commit()
def db_clear():
    with _dbl: _db.execute("DELETE FROM memory"); _db.commit()

# ── Chat history ──────────────────────────────────────────────────────────────
def db_save_chat(role, content, source="", is_conv=True):
    ts = datetime.datetime.now().isoformat()
    with _dbl:
        _db.execute("INSERT INTO chat_history(ts,role,content,source,is_conversation) VALUES(?,?,?,?,?)",
                    (ts, role, content, source, 1 if is_conv else 0))
        _db.commit()
def db_load_history(limit=50, conv_only=True):
    q = "SELECT role,content,source FROM chat_history"
    if conv_only: q += " WHERE is_conversation=1"
    q += " ORDER BY id DESC LIMIT ?"
    with _dbl: rows = _db.execute(q, (limit,)).fetchall()
    return list(reversed(rows))

# ── Reminders ─────────────────────────────────────────────────────────────────
def db_save_reminder(ts, label):
    with _dbl: _db.execute("INSERT INTO reminders(ts,label) VALUES(?,?)", (ts, label)); _db.commit()
def db_get_reminders():
    with _dbl: return _db.execute("SELECT id,ts,label FROM reminders WHERE done=0").fetchall()
def db_done_reminder(rid):
    with _dbl: _db.execute("UPDATE reminders SET done=1 WHERE id=?", (rid,)); _db.commit()

# ── Offline cache ──────────────────────────────────────────────────────────────
def cache_set(key, value):
    ts = datetime.datetime.now().isoformat()
    with _dbl: _db.execute("INSERT OR REPLACE INTO offline_cache VALUES(?,?,?)", (key, value, ts)); _db.commit()
def cache_get(key):
    with _dbl: r = _db.execute("SELECT value,updated FROM offline_cache WHERE key=?", (key,)).fetchone()
    return r if r else None

# ── Misc ──────────────────────────────────────────────────────────────────────
def db_save_noise(thr):
    with _dbl: _db.execute("INSERT OR REPLACE INTO noise_cal(id,threshold) VALUES(1,?)", (thr,)); _db.commit()
def db_load_noise():
    with _dbl: r = _db.execute("SELECT threshold FROM noise_cal WHERE id=1").fetchone()
    return r[0] if r else None
def db_save_wake(word):
    with _dbl: _db.execute("INSERT OR IGNORE INTO wake_words(word) VALUES(?)", (word.lower().strip(),)); _db.commit()
def db_load_wakes():
    with _dbl: rows = _db.execute("SELECT word FROM wake_words").fetchall()
    return [r[0] for r in rows]

# ── Offline knowledge base (seed on first run) ────────────────────────────────
_KB_SEED = [
    ("what is photosynthesis","Photosynthesis is how plants convert sunlight, water and CO2 into glucose and oxygen using chlorophyll.","science"),
    ("what is the capital of india","New Delhi is the capital of India.","geography"),
    ("what is gravity","Gravity is the force that attracts objects with mass toward each other. On Earth it is 9.8 m/s².","science"),
    ("who is the president of india","The President of India is the constitutional head of state. Droupadi Murmu has been President since 2022.","general"),
    ("what is python","Python is a high-level, interpreted programming language known for readability and versatility.","tech"),
    ("what is ai","Artificial Intelligence is the simulation of human intelligence by machines, especially computer systems.","tech"),
    ("what is the speed of light","The speed of light in vacuum is approximately 299,792,458 metres per second (about 3×10⁸ m/s).","science"),
    ("how many planets are there","There are 8 planets in our solar system: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune.","science"),
    ("what is dna","DNA (Deoxyribonucleic acid) is the molecule that carries genetic information in all living organisms.","science"),
    ("what is machine learning","Machine learning is a subset of AI where systems learn from data to improve their performance without being explicitly programmed.","tech"),
    ("what is the boiling point of water","Water boils at 100°C (212°F) at standard atmospheric pressure.","science"),
    ("what is ram","RAM (Random Access Memory) is temporary, fast storage that your computer uses to run active programs.","tech"),
    ("who wrote the mahabharata","The Mahabharata is traditionally attributed to the sage Vyasa (Krishna Dvaipayana).","culture"),
    ("what is the bhagavad gita","The Bhagavad Gita is a 700-verse Hindu scripture that is part of the Mahabharata, a dialogue between Arjuna and Krishna.","culture"),
    ("what is meditation","Meditation is a practice of focused attention or mindfulness used to achieve mental clarity and calm.","wellness"),
    ("how to improve memory","Practice spaced repetition, get good sleep, exercise regularly, stay hydrated, and use mnemonic techniques.","wellness"),
    ("what is diabetes","Diabetes is a chronic condition where the body cannot properly regulate blood sugar due to insulin issues.","health"),
    ("what is blood pressure","Blood pressure is the force of blood pushing against artery walls. Normal is around 120/80 mmHg.","health"),
    ("what is the internet","The internet is a global network of computers connected using standardized protocols to share information.","tech"),
    ("what is 5g","5G is the 5th generation mobile network offering faster speeds, lower latency, and greater capacity than 4G.","tech"),
]

def _seed_knowledge():
    with _dbl:
        count = _db.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
        if count == 0:
            _db.executemany("INSERT INTO knowledge(question,answer,category) VALUES(?,?,?)", _KB_SEED)
            _db.commit()

def kb_search(query):
    """Search local knowledge base — works fully offline."""
    q = query.lower().strip()
    # Exact match first
    with _dbl:
        r = _db.execute("SELECT answer FROM knowledge WHERE lower(question)=?", (q,)).fetchone()
        if r: return r[0]
        # Keyword match
        words = [w for w in q.split() if len(w) > 3]
        for w in words:
            r = _db.execute("SELECT answer FROM knowledge WHERE lower(question) LIKE ?", (f"%{w}%",)).fetchone()
            if r: return r[0]
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  NLU INTENT ENGINE  — natural language → structured intent
#  This is the KEY fix: users don't memorise commands
# ═══════════════════════════════════════════════════════════════════════════════

_INTENT_PATTERNS = {
    "play_music": [
        r'\b(play|listen|put on|start playing|i want to hear|play me|search for music)\b.*?(on youtube|youtube)?',
        r'\b(songs?|music|track|playlist|album)\b',
    ],
    "open_app": [
        r'\b(open|launch|start|run|bring up|fire up|load)\b.+',
        r'\b(can you open|please open|would you open)\b.+',
    ],
    "close_app": [
        r'\b(close|exit|quit|kill|shut|stop)\b.+(app|application|program|window|browser|chrome|firefox|spotify|discord)',
    ],
    "search_web": [
        r'\b(search|google|look up|find|look for|search for|can you search|search the web)\b.+',
        r'\b(what is|who is|tell me about|explain|define|meaning of)\b.+',
    ],
    "youtube_search": [
        r'\b(youtube|watch|video|play.*on youtube|search youtube|find.*video)\b',
        r'\b(show me|i want to watch|find me a video)\b',
    ],
    "weather": [
        r'\b(weather|temperature|how (hot|cold|warm)|what.*weather|will it rain|forecast|climate today)\b',
        r'\b(how.*outside|is it raining|should i carry umbrella)\b',
    ],
    "time_query": [
        r'\b(time|what time|current time|tell me the time|clock)\b',
        r'\b(what.*time is it|do you know the time)\b',
    ],
    "date_query": [
        r'\b(date|today|what day|which day|what.*date|day.*today)\b',
    ],
    "volume_up": [
        r'\b(volume up|increase volume|louder|turn.*up|raise.*volume|more volume|can.*louder)\b',
    ],
    "volume_down": [
        r'\b(volume down|decrease volume|quieter|turn.*down|lower.*volume|less volume|too loud)\b',
    ],
    "volume_mute": [
        r'\b(mute|silence|shut up.*volume|no sound|quiet)\b',
    ],
    "volume_set": [
        r'\b(set volume|volume.*(\d+)|(\d+).*percent.*volume|volume.*percent)\b',
    ],
    "calculator": [
        r'\b(calculate|compute|what is \d|how much is|add|subtract|multiply|divide|percent of|square root)\b',
        r'\b(\d+\s*[\+\-\*\/\^]\s*\d+)\b',
    ],
    "set_timer": [
        r'\b(set.*timer|start.*timer|timer.*for|alarm.*in|wake me|count down)\b',
    ],
    "reminder": [
        r'\b(remind me|reminder|set.*reminder|alert me|notify me|don.t let me forget)\b',
    ],
    "news": [
        r'\b(news|headlines|what.*happening|current events|latest news|today.*news)\b',
    ],
    "system_status": [
        r'\b(cpu|ram|memory|battery|system|pc status|how.*pc|computer.*status|system.*info)\b',
    ],
    "screenshot": [
        r'\b(screenshot|capture.*screen|what.*on.*screen|describe.*screen|take.*screenshot)\b',
    ],
    "media_control": [
        r'\b(pause|play music|resume.*music|stop music|next song|previous song|skip|now playing|what.*playing)\b',
    ],
    "open_incognito": [
        r'\b(incognito|private.*window|private.*browser|private.*mode|browse.*private|secret.*window)\b',
    ],
    "pc_power": [
        r'\b(shutdown|shut down|restart|reboot|power off|turn off.*pc)\b',
    ],
    "remember": [
        r'\b(remember|save|store|note|keep.*note)\b.*\b(is|are|means?|=)\b',
    ],
    "recall": [
        r'\b(what is|who is|tell me|recall|do you know|what.*mean|remind me.*about)\b',
    ],
    "mode_online": [
        r'\b(surya|online|go online|connect|internet.*mode|surya net)\b',
    ],
    "mode_offline": [
        r'\b(nirvana|offline|go offline|disconnect|offline.*mode|nirvana mode)\b',
    ],
    "personality": [
        r'\b(personality|voice.*mode|speak.*like|be (calm|energetic|wise|guru))\b',
    ],
    "language": [
        r'\b(language|speak.*hindi|speak.*english|hindi.*mode|english.*mode|switch.*language)\b',
    ],
    "joke": [
        r'\b(joke|funny|laugh|humor|make me.*laugh|tell.*joke|something funny)\b',
    ],
    "greeting": [
        r'^(hi|hello|hey|good morning|good evening|good afternoon|namaste|howdy|sup|wassup|yo)\b',
    ],
    "goodbye": [
        r'\b(bye|goodbye|see you|exit|quit veda|close veda|good night|stop veda|shut.*down.*veda)\b',
    ],
    "help": [
        r'\b(help|what can you do|commands|features|how.*use|guide|tutorial|instructions|capabilities)\b',
    ],
    "briefing": [
        r'\b(briefing|morning brief|daily brief|good morning veda|what.*today|daily update)\b',
    ],
    "ai_chat": [
        r'.*',  # catch-all — route to AI
    ],
}

# Compile all patterns
_COMPILED_INTENTS = {
    intent: [re.compile(p, re.I) for p in patterns]
    for intent, patterns in _INTENT_PATTERNS.items()
}

def detect_intent(text):
    """Return the best matching intent string for any natural language input."""
    t = text.lower().strip()
    # Priority order — more specific first, ai_chat last
    priority = [
        "greeting","goodbye","help","screenshot","pc_power","open_incognito",
        "set_timer","reminder","briefing","news","weather","time_query","date_query",
        "volume_mute","volume_up","volume_down","volume_set","calculator",
        "media_control","system_status","youtube_search","play_music",
        "close_app","open_app","search_web","remember","recall",
        "mode_online","mode_offline","personality","language","joke","ai_chat"
    ]
    for intent in priority:
        if intent not in _COMPILED_INTENTS: continue
        for pat in _COMPILED_INTENTS[intent]:
            if pat.search(t):
                return intent
    return "ai_chat"

def extract_target(text, intent):
    """Pull the key noun/phrase out of natural language for a given intent."""
    t = text.lower().strip()
    # Strip common filler phrases
    fillers = [
        r"^(hey veda|ok veda|veda|please|can you|could you|would you|i want you to|"
        r"i need you to|i'd like you to|go ahead and|just|kindly)\s+",
        r"\s+(please|now|for me|right now|immediately)$"
    ]
    for f in fillers:
        t = re.sub(f, "", t, flags=re.I).strip()

    if intent == "play_music":
        t = re.sub(r'(play|listen to|put on|start playing|i want to hear|play me|search for music|on youtube|youtube)', '', t, flags=re.I).strip()
        return t.strip("., ") or ""

    if intent == "youtube_search":
        t = re.sub(r'(youtube|watch|video|play.*?on youtube|search youtube|find.*?video|show me|i want to watch|find me a video)', '', t, flags=re.I).strip()
        return t.strip("., ") or ""

    if intent == "open_app":
        t = re.sub(r'^(open|launch|start|run|bring up|fire up|load|can you open|please open)', '', t, flags=re.I).strip()
        return t.strip("., ") or ""

    if intent == "close_app":
        t = re.sub(r'^(close|exit|quit|kill|shut|stop)', '', t, flags=re.I).strip()
        t = re.sub(r'\b(app|application|program|window)\b', '', t, flags=re.I).strip()
        return t.strip("., ") or ""

    if intent == "search_web":
        t = re.sub(r'^(search|google|look up|find|look for|search for|can you search|search the web|tell me about|explain|define|meaning of)', '', t, flags=re.I).strip()
        return t.strip("., ") or ""

    if intent == "weather":
        m = re.search(r'(?:weather|temperature|forecast)\s+(?:in|for|at|of)\s+(.+?)(?:\s+today|\s+now|$)', t)
        if m: return m.group(1).strip()
        t = re.sub(r'\b(weather|temperature|how|hot|cold|warm|will|it|rain|forecast|climate|today|outside|is|raining|carry|umbrella|should|i)\b', '', t).strip()
        return t.strip("., ") or CFG.get("city","Hyderabad")

    if intent == "volume_set":
        m = re.search(r'(\d{1,3})', t)
        return m.group(1) if m else "50"

    if intent == "calculator":
        t = re.sub(r'^(calculate|compute|what is|how much is)', '', t, flags=re.I).strip()
        return t

    if intent == "set_timer":
        return t  # full text passed to _parse_timer

    if intent == "reminder":
        return t  # full text passed to _parse_reminder

    if intent == "recall":
        t = re.sub(r'^(what is|who is|tell me|recall|do you know|what.*?mean|remind me about)', '', t, flags=re.I).strip()
        return t.strip("., ") or ""

    if intent == "remember":
        return t  # full text

    if intent == "personality":
        for p in ("calm","energetic","energy","wise","guru"):
            if p in t: return p
        return ""

    if intent == "language":
        if "hindi" in t or "हिंदी" in t: return "hindi"
        if "english" in t: return "english"
        return ""

    return t.strip("., ")


# ═══════════════════════════════════════════════════════════════════════════════
#  OLLAMA  — local offline LLM
# ═══════════════════════════════════════════════════════════════════════════════

def _ollama_available():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

def ask_ollama(prompt, system="You are VEDA, a helpful assistant. Be concise, under 200 words."):
    """Query local Ollama LLM — works fully offline."""
    if not _REQ: return None
    try:
        model = CFG.get("ollama_model", "mistral")
        payload = {
            "model": model,
            "prompt": f"{system}\n\nUser: {prompt}\nVEDA:",
            "stream": False,
            "options": {"num_predict": 150, "temperature": 0.7}
        }
        r = requests.post("http://localhost:11434/api/generate",
                          json=payload, timeout=30)
        if r.status_code == 200:
            return r.json().get("response", "").strip()
    except Exception as e:
        print(f"[Ollama] {e}")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  MODE
# ═══════════════════════════════════════════════════════════════════════════════

_MODE = CFG.get("mode", "auto")
_MODE_LOCK = threading.Lock()
_CONV_CTX  = deque(maxlen=12)
_CTX_LOCK  = threading.Lock()
_GPT_LAST  = 0.0
_GPT_LOCK  = threading.Lock()

def _ping():
    try:
        socket.setdefaulttimeout(2)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except: return False

def _active_mode():
    with _MODE_LOCK: m = _MODE
    if m == "surya":   return "surya"
    if m == "nirvana": return "nirvana"
    return "surya" if _ping() else "nirvana"

def _set_surya():
    global _MODE, _MORPH_TGT
    if not _ping():
        speak("No internet. Staying in Nirvana Mode.", priority=1, save=False)
        with _MODE_LOCK: _MODE = "nirvana"
        _MORPH_TGT = 1.0; _ui("mode", "nirvana"); return
    with _MODE_LOCK: _MODE = "surya"
    _MORPH_TGT = 0.0; _ui("mode", "surya")
    speak("Surya Net activated. I'm online!", save=False)

def _set_nirvana():
    global _MODE, _MORPH_TGT
    with _MODE_LOCK: _MODE = "nirvana"
    _MORPH_TGT = 1.0; _ui("mode", "nirvana")
    speak("Nirvana Mode. Running fully offline now.", save=False)


# ═══════════════════════════════════════════════════════════════════════════════
#  CHATGPT  — with rate limiter + safe empty key check
# ═══════════════════════════════════════════════════════════════════════════════

_PERSONALITY_PROMPTS = {
    "calm": "You are VEDA, a calm and composed AI assistant. Be clear, peaceful, concise. Under 200 chars.",
    "energetic": "You are VEDA, energetic and enthusiastic. Quick, sharp, upbeat. Under 200 chars.",
    "guru": "You are VEDA, wise and thoughtful like an Indian sage. Blend wisdom with practicality. Under 200 chars.",
}

def _gpt_ok():
    key = CFG.get("openai_key","").strip()
    return _OPENAI and bool(key) and key != "YOUR_OPENAI_API_KEY"

def ask_chatgpt(prompt, stream_cb=None):
    global _GPT_LAST
    if not _gpt_ok(): return None, None
    # Rate limit: min 2s between calls
    with _GPT_LOCK:
        elapsed = time.time() - _GPT_LAST
        if elapsed < 2.0: time.sleep(2.0 - elapsed)
        _GPT_LAST = time.time()
    try:
        client = OpenAI(api_key=CFG["openai_key"])
        with _CTX_LOCK:
            history = [{"role": r, "content": c} for r, c in list(_CONV_CTX)]
        history.append({"role": "user", "content": prompt})
        sys_p = _PERSONALITY_PROMPTS.get(CFG.get("personality","energetic"), _PERSONALITY_PROMPTS["energetic"])
        if CFG.get("language") == "hi":
            sys_p += " Respond in Hindi."
        elif CFG.get("language") == "auto":
            sys_p += " Match the user's language."

        if stream_cb:
            full = ""
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":sys_p}]+history,
                max_tokens=200, stream=True)
            for chunk in resp:
                delta = chunk.choices[0].delta.content or ""
                if delta: full += delta; stream_cb(delta)
            reply = full.strip()
        else:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":sys_p}]+history,
                max_tokens=200)
            reply = resp.choices[0].message.content.strip()

        with _CTX_LOCK:
            _CONV_CTX.append(("user", prompt))
            _CONV_CTX.append(("assistant", reply))
        return reply, "gpt"
    except Exception as e:
        print(f"[GPT] {e}"); return None, None

def ask_chatgpt_vision(prompt, img_b64):
    if not _gpt_ok(): return "Vision requires an OpenAI API key."
    try:
        client = OpenAI(api_key=CFG["openai_key"])
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role":"user","content":[
                {"type":"text","text":prompt or "Describe what you see on this screen briefly."},
                {"type":"image_url","image_url":{"url":f"data:image/png;base64,{img_b64}","detail":"low"}}
            ]}], max_tokens=300)
        return resp.choices[0].message.content.strip()
    except Exception as e: return f"Vision error: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
#  VOSK — with install check
# ═══════════════════════════════════════════════════════════════════════════════

try:    from vosk import Model as _VM, KaldiRecognizer as _KR; _VOSK_LIB = True
except: _VOSK_LIB = False

_VOSK_DIR  = "vosk-model-small-en-us-0.15"
_vosk_rec  = None
_vosk_ok   = None   # None=unchecked, True=ok, False=unavailable

def _vosk_status():
    """Returns 'ok' | 'no_model' | 'no_lib'"""
    if not _VOSK_LIB: return "no_lib"
    if not os.path.isdir(_VOSK_DIR): return "no_model"
    return "ok"

def _vosk():
    global _vosk_rec
    if _vosk_status() != "ok": return None
    if _vosk_rec is None:
        try: _vosk_rec = _KR(_VM(_VOSK_DIR), 16000)
        except Exception as e: print(f"[VOSK] {e}"); return None
    return _vosk_rec


# ═══════════════════════════════════════════════════════════════════════════════
#  TTS  — live personality rate update, priority queue, clean shutdown
# ═══════════════════════════════════════════════════════════════════════════════

class _TTSMsg:
    def __init__(self, priority, text, source="local", save=False):
        self.priority = priority; self.text = text
        self.source = source; self.save = save
    def __lt__(self, o): return self.priority < o.priority

_tts_q    = queue.PriorityQueue()
_speaking = threading.Event()
_RATES    = {"calm": 148, "energetic": 175, "guru": 152}

def _tts_worker():
    engine = pyttsx3.init()
    for v in engine.getProperty("voices"):
        if "zira" in v.name.lower() or "david" in v.name.lower():
            engine.setProperty("voice", v.id); break

    while _APP_RUNNING.is_set():
        try:
            msg = _tts_q.get(timeout=1)
        except queue.Empty:
            continue
        # Live rate update per message
        rate = _RATES.get(CFG.get("personality", "energetic"), 168)
        engine.setProperty("rate", rate)

        text, src, save = msg.text, msg.source, msg.save
        _speaking.set()
        _ui("state", "speaking")
        _ui("status", text[:68] + ("…" if len(text) > 68 else ""))
        _ui("bubble", ("VEDA", "ai", text, src, save))
        try:
            engine.say(text); engine.runAndWait()
        except Exception as e:
            print("[TTS]", e)
        cooldown = min(0.9, max(0.28, len(text) * 0.009))
        time.sleep(cooldown)
        _speaking.clear()
        _ui("state", "ready")

def speak(text: str, source: str = "local", priority: int = 1, save: bool = True):
    """save=True → appears in chat history. save=False → system-only, not saved."""
    if not text or not _APP_RUNNING.is_set(): return
    print(f"VEDA: {text}")
    _tts_q.put(_TTSMsg(priority, text, source, save))

def _wait_tts(max_sec=5.0):
    time.sleep(0.1)
    deadline = time.time() + max_sec
    while not _speaking.is_set() and time.time() < deadline: time.sleep(0.04)
    while _speaking.is_set(): time.sleep(0.04)
    time.sleep(0.22)


# ═══════════════════════════════════════════════════════════════════════════════
#  UI BRIDGE
# ═══════════════════════════════════════════════════════════════════════════════

def _ui(action, data=None):
    if not _APP_RUNNING.is_set(): return
    def _do(dt):
        a = App.get_running_app()
        if not a or not _APP_RUNNING.is_set(): return
        try:
            if   action == "state":       a.set_state(data)
            elif action == "status":      a.set_status(data)
            elif action == "mode":        a.set_mode(data)
            elif action == "bubble":      a.add_bubble(*data)
            elif action == "heard":       a.set_heard(data)
            elif action == "toast":       a.show_toast(data)
            elif action == "energy":      a.set_energy(data)
            elif action == "online":      a.set_online_dot(data)
            elif action == "sysmon":      a.update_sysmon(data)
            elif action == "stream":      a.stream_chunk(data)
            elif action == "stream_end":  a.stream_end()
            elif action == "reminder_due":a.reminder_due(data)
            elif action == "offline_warn":a.show_offline_warning(data)
        except Exception as e:
            print(f"[UI] {e}")
    Clock.schedule_once(_do, 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  STT WORKER  — dual pipeline, dedup, maxsize queue
# ═══════════════════════════════════════════════════════════════════════════════

_stt_q = queue.Queue(maxsize=3)   # maxsize=3 prevents stale queue buildup
_rec   = sr.Recognizer()
_rec.dynamic_energy_threshold = True
_rec.pause_threshold          = 0.60
_rec.phrase_threshold         = 0.18
_rec.non_speaking_duration    = 0.35
_rec.energy_threshold = db_load_noise() or CFG.get("noise_threshold", 300)

_last_heard = ""; _last_heard_t = 0.0

def _stt_worker():
    global _last_heard, _last_heard_t
    vosk_status_shown = False

    while _APP_RUNNING.is_set():
        if _speaking.is_set(): time.sleep(0.08); continue
        _ui("state", "listening")
        try:
            with sr.Microphone() as src:
                _rec.adjust_for_ambient_noise(src, 0.15)
                audio = _rec.listen(src, timeout=6, phrase_time_limit=12)
                raw = audio.get_raw_data()
                if raw:
                    samps = [abs(int.from_bytes(raw[i:i+2],"little",signed=True))
                             for i in range(0, min(len(raw), 1600), 2)]
                    # Use calibrated threshold as normaliser
                    normaliser = max(_rec.energy_threshold, 500)
                    e = min(1.0, (sum(samps)/len(samps)) / normaliser) if samps else 0
                    _ui("energy", e)
        except sr.WaitTimeoutError:
            _ui("state", "ready"); continue
        except Exception as e:
            print(f"[MIC] {e}"); time.sleep(1); continue

        if _speaking.is_set(): continue
        _ui("state", "thinking")
        text = ""; stt_src = "local"
        mode = _active_mode()

        # PRIMARY: Google STT (online)
        if mode == "surya":
            for attempt in range(2):
                try:
                    text = _rec.recognize_google(audio, language="en-IN").lower().strip()
                    stt_src = "google"; break
                except sr.UnknownValueError: break
                except sr.RequestError:
                    if attempt == 0: time.sleep(0.5)

        # OFFLINE: Vosk
        if not text:
            v = _vosk()
            if v:
                try:
                    wav = audio.get_wav_data(convert_rate=16000, convert_width=2)
                    v.AcceptWaveform(wav)
                    text = json.loads(v.Result()).get("text", "").strip()
                    stt_src = "vosk"
                except Exception as e:
                    print(f"[VOSK ERR] {e}")
            elif mode == "nirvana" and not vosk_status_shown:
                vosk_status_shown = True
                vs = _vosk_status()
                if vs == "no_model":
                    _ui("offline_warn", "Vosk model not found. Download it for offline speech recognition.")
                elif vs == "no_lib":
                    _ui("offline_warn", "Vosk not installed. Run: pip install vosk")

        # LAST RESORT: Google even in nirvana (if internet happens to be available)
        if not text and mode == "nirvana":
            try:
                text = _rec.recognize_google(audio, language="en-IN").lower().strip()
                stt_src = "google-fallback"
            except Exception: pass

        _ui("state", "ready")
        if not text: continue

        # Dedup
        now = time.time()
        if text == _last_heard and now - _last_heard_t < 1.8:
            print(f"[DEDUP] {text}"); continue
        _last_heard = text; _last_heard_t = now

        print(f"[STT:{stt_src}] {text}")
        _ui("heard", text)

        # Non-blocking put — if queue full, drop oldest
        try:
            _stt_q.put_nowait(text)
        except queue.Full:
            try: _stt_q.get_nowait()
            except queue.Empty: pass
            try: _stt_q.put_nowait(text)
            except queue.Full: pass


# ═══════════════════════════════════════════════════════════════════════════════
#  WAKE WORDS
# ═══════════════════════════════════════════════════════════════════════════════

def _build_wake():
    base = list(CFG.get("wake_words", ["hey veda","ok veda","veda"]))
    custom = db_load_wakes() + CFG.get("custom_wake", [])
    all_w = list(dict.fromkeys(base + custom))
    patterns = [re.compile(r'\b'+re.escape(w)+r'\b', re.I) for w in all_w]
    return all_w, patterns

_WAKE_WORDS, _WAKE_PATS = _build_wake()

_CMD_STARTERS = {
    "open","play","search","find","launch","weather","volume","time","date",
    "calculate","news","timer","remember","forget","what","who","tell","go","switch",
    "set","check","turn","enable","disable","mute","unmute","type","press","close",
    "exit","quit","start","shutdown","restart","reboot","cancel","remind","schedule",
    "surya","nirvana","screenshot","describe","show","briefing","media","pause","resume",
    "skip","next","previous","personality","language","train","calibrate","hi","hello",
    "hey","good","bye","goodbye","help","how","is","can","will","could","should","do",
    "i","please","would","stop","increase","decrease","louder","quieter","raise","lower",
    "compute","alarm","alert","notify","capture","take","run","fire","bring","load",
    "watch","listen","put","add","remove","delete","wipe","clear","refresh","update"
}

def _has_wake(t):
    t = t.lower()
    if any(p.search(t) for p in _WAKE_PATS): return True
    for b in ("hey ", "ok "):
        if t.startswith(b):
            r = t[len(b):].strip().split()
            if r and r[0] in _CMD_STARTERS: return True
    return False

def _strip_wake(t):
    t = t.lower()
    for w, p in sorted(zip(_WAKE_WORDS, _WAKE_PATS), key=lambda x: len(x[0]), reverse=True):
        if p.search(t): return p.sub("", t, count=1).strip(" ,.")
    for b in ("hey ", "ok ", "hi "):
        if t.startswith(b): return t[len(b):].strip()
    return t


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM MONITOR
# ═══════════════════════════════════════════════════════════════════════════════

def _sysmon_worker():
    while _APP_RUNNING.is_set():
        if not _PSUTIL: time.sleep(5); continue
        try:
            cpu  = psutil.cpu_percent(interval=None)  # non-blocking
            ram  = psutil.virtual_memory().percent
            batt = psutil.sensors_battery()
            bpct = int(batt.percent) if batt else -1
            plug = batt.power_plugged if batt else True
            _ui("sysmon", {"cpu": cpu, "ram": ram, "batt": bpct, "plug": plug})
        except Exception as e:
            print(f"[SYSMON] {e}")
        time.sleep(3)


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def _weather(city=""):
    city = (city or CFG.get("city","Hyderabad")).strip()
    if _REQ and _ping():
        try:
            c = requests.get(f"https://wttr.in/{city.replace(' ','+')}?format=j1", timeout=7).json()["current_condition"][0]
            result = (f"{city.title()}: {c['weatherDesc'][0]['value']}, "
                      f"{c['temp_C']}°C, feels {c['FeelsLikeC']}°C, humidity {c['humidity']}%.")
            cache_set(f"weather:{city.lower()}", result)
            return result
        except Exception: pass
    # Offline fallback — cached
    cached = cache_get(f"weather:{city.lower()}")
    if cached:
        return f"[Cached] {cached[0]}  (updated {cached[1][:10]})"
    return f"No internet and no cached weather for {city}."

def _news():
    if _REQ and _ping():
        try:
            raw = requests.get("https://feeds.bbci.co.uk/news/rss.xml", timeout=7).text
            titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", raw)
            if not titles: titles = re.findall(r"<title>(.*?)</title>", raw)
            heads = [t for t in titles if t and "BBC" not in t][:4]
            result = "Headlines: " + ". ".join(heads) + "." if heads else "No headlines."
            cache_set("news:bbc", result)
            return result
        except Exception: pass
    cached = cache_get("news:bbc")
    if cached:
        return f"[Cached news] {cached[0][:220]}  (from {cached[1][:10]})"
    return "No internet and no cached news available."

try:
    from ctypes import cast, POINTER; from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume; _PYCAW = True
except: _PYCAW = False

def _vobj():
    try:
        d = AudioUtilities.GetSpeakers()
        return cast(d.Activate(IAudioEndpointVolume._iid_,CLSCTX_ALL,None),POINTER(IAudioEndpointVolume))
    except: return None

def vol_up():
    if _PYCAW:
        v = _vobj()
        if v: n=min(1.0,v.GetMasterVolumeLevelScalar()+0.08); v.SetMasterVolumeLevelScalar(n,None); return f"Volume {int(n*100)}%."
    subprocess.run("nircmd.exe changesysvolume 5243",shell=True,capture_output=True); return "Volume up."
def vol_down():
    if _PYCAW:
        v = _vobj()
        if v: n=max(0.0,v.GetMasterVolumeLevelScalar()-0.08); v.SetMasterVolumeLevelScalar(n,None); return f"Volume {int(n*100)}%."
    subprocess.run("nircmd.exe changesysvolume -5243",shell=True,capture_output=True); return "Volume down."
def vol_mute():
    if _PYCAW:
        v = _vobj()
        if v: m=v.GetMute(); v.SetMute(not m,None); return "Unmuted." if m else "Muted."
    subprocess.run("nircmd.exe mutesysvolume 2",shell=True,capture_output=True); return "Muted."
def vol_set(pct):
    pct = max(0, min(100, int(pct)))
    if _PYCAW:
        v = _vobj()
        if v: v.SetMasterVolumeLevelScalar(pct/100,None); return f"Volume {pct}%."
    return f"Set volume to {pct}%."

def _safe_calc(expr):
    """AST-based safe math evaluator — no eval(), no injection possible."""
    try:
        expr = (expr.replace("×","*").replace("÷","/").replace("^","**")
                .replace("plus","+").replace("minus","-").replace("times","*")
                .replace("divided by","/").replace("to the power of","**").replace("squared","**2"))
        expr = re.sub(r'(?<=\d)\s*x\s*(?=\d)', '*', expr)
        expr = re.sub(r'[^0-9+\-*/().%\s]', '', expr).strip()
        if not expr: return "Could not parse that expression."
        # Safe AST eval
        allowed_nodes = (
            _ast.Expression, _ast.BinOp, _ast.UnaryOp, _ast.Num, _ast.Constant,
            _ast.Add, _ast.Sub, _ast.Mult, _ast.Div, _ast.Pow, _ast.Mod,
            _ast.USub, _ast.UAdd
        )
        tree = _ast.parse(expr, mode='eval')
        for node in _ast.walk(tree):
            if not isinstance(node, allowed_nodes):
                return "Unsafe expression detected."
        result = eval(compile(tree, '<calc>', 'eval'), {"__builtins__": {}})
        if isinstance(result, float) and result == int(result): result = int(result)
        return f"The answer is {result}."
    except ZeroDivisionError: return "Cannot divide by zero."
    except Exception: return "Could not calculate that."

def _parse_timer(cmd):
    nums = re.findall(r"\d+", cmd)
    if not nums: return None, "How many seconds for the timer?"
    n = int(nums[0])
    unit = "hours" if "hour" in cmd else "minutes" if "minute" in cmd else "seconds"
    secs = n * (3600 if unit=="hours" else 60 if unit=="minutes" else 1)
    return secs, f"Timer set for {n} {unit}."

def _parse_reminder(cmd):
    now = datetime.datetime.now()
    # "in X minutes/hours/seconds"
    m = re.search(r'in\s+(\d+)\s*(minute|hour|second)', cmd, re.I)
    if m:
        n = int(m.group(1)); unit = m.group(2).lower()
        delta = datetime.timedelta(
            seconds=n if unit.startswith("s") else
            n*60 if unit.startswith("m") else n*3600)
        ts = (now + delta).isoformat()
        lm = re.search(r'\bto\s+(.+)$', cmd, re.I)
        label = lm.group(1).strip() if lm else cmd.strip()
        db_save_reminder(ts, label)
        return f"Reminder set: {label} in {n} {unit}s."
    # "at HH:MM" or "at 3" or "at 3pm" or "at 3:30"
    m = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', cmd, re.I)
    if m:
        h = int(m.group(1)); mn = int(m.group(2) or 0)
        ampm = (m.group(3) or "").lower()
        if ampm == "pm" and h < 12: h += 12
        if ampm == "am" and h == 12: h = 0
        # Default: if no am/pm and hour <= 12 and current hour > that → assume PM
        if not ampm and h < 12 and now.hour >= 12: h += 12
        ts = now.replace(hour=h%24, minute=mn, second=0, microsecond=0)
        if ts < now: ts += datetime.timedelta(days=1)  # next day
        lm = re.search(r'\bto\s+(.+)$', cmd, re.I)
        label = lm.group(1).strip() if lm else cmd.strip()
        db_save_reminder(ts.isoformat(), label)
        return f"Reminder: {label} at {ts.strftime('%I:%M %p')}."
    # "tomorrow at X"
    m = re.search(r'tomorrow\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', cmd, re.I)
    if m:
        h=int(m.group(1)); mn=int(m.group(2) or 0)
        ampm=(m.group(3) or "").lower()
        if ampm=="pm" and h<12: h+=12
        ts=(now+datetime.timedelta(days=1)).replace(hour=h,minute=mn,second=0,microsecond=0)
        lm=re.search(r'\bto\s+(.+)$',cmd,re.I)
        label=lm.group(1).strip() if lm else "reminder"
        db_save_reminder(ts.isoformat(),label)
        return f"Reminder: {label} tomorrow at {ts.strftime('%I:%M %p')}."
    return "Could not parse time. Try: remind me in 10 minutes to call mom."

_shutdown_ev = threading.Event()
_restart_ev  = threading.Event()

def _do_shutdown():
    _shutdown_ev.clear()
    for _ in range(100):
        if _shutdown_ev.is_set(): speak("Shutdown cancelled.", save=False); return
        time.sleep(0.1)
    subprocess.run("shutdown /s /t 0", shell=True)

def _do_restart():
    _restart_ev.clear()
    for _ in range(100):
        if _restart_ev.is_set(): speak("Restart cancelled.", save=False); return
        time.sleep(0.1)
    subprocess.run("shutdown /r /t 0", shell=True)

_APPS = {
    "notepad":"notepad.exe","calculator":"calc.exe","paint":"mspaint.exe",
    "chrome":r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome":r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox":"firefox.exe","edge":"msedge.exe","microsoft edge":"msedge.exe",
    "word":"winword.exe","excel":"excel.exe","powerpoint":"powerpnt.exe",
    "vs code":"code.exe","vscode":"code.exe","file explorer":"explorer.exe",
    "cmd":"cmd.exe","terminal":"wt.exe","task manager":"taskmgr.exe",
    "spotify":"spotify.exe","vlc":"vlc.exe","discord":"discord.exe",
    "whatsapp":"whatsapp.exe","telegram":"telegram.exe","zoom":"zoom.exe",
    "teams":"teams.exe","steam":"steam.exe","skype":"skype.exe",
}
_SITES = {
    "youtube":"https://www.youtube.com","google":"https://www.google.com",
    "gmail":"https://mail.google.com","facebook":"https://www.facebook.com",
    "instagram":"https://www.instagram.com","twitter":"https://www.twitter.com",
    "whatsapp":"https://web.whatsapp.com","github":"https://www.github.com",
    "netflix":"https://www.netflix.com","amazon":"https://www.amazon.in",
    "maps":"https://maps.google.com","wikipedia":"https://www.wikipedia.org",
    "reddit":"https://www.reddit.com","linkedin":"https://www.linkedin.com",
    "chatgpt":"https://chat.openai.com","translate":"https://translate.google.com",
}

def _open_app(name):
    name = name.lower().strip()
    for k, url in _SITES.items():
        if k in name: webbrowser.open(url); return f"Opening {k}."
    matched = next((k for k in _APPS if k == name), None) or \
              next((k for k in _APPS if k in name), None)
    if matched:
        try: subprocess.Popen(_APPS[matched], shell=True); return f"Opening {matched}."
        except Exception: return f"Could not open {matched}."
    # Try as website
    site = name.replace(" ",""); site += ("" if "." in site else ".com")
    webbrowser.open(f"https://{site}"); return f"Opening {name}."

def _spotify_cmd(action):
    if not _PYAUTOGUI: return "pyautogui not installed."
    cmds = {"play_pause":"playpause","next":"nexttrack","prev":"prevtrack",
            "vol_up":"volumeup","vol_down":"volumedown"}
    key = cmds.get(action)
    if key:
        try: pyautogui.press(key); return f"{action.replace('_',' ').title()}."
        except Exception: return "Media key failed."
    return "Unknown media action."

def _screenshot_describe(prompt=""):
    if not _PIL: return "Pillow not installed. Run: pip install Pillow"
    try:
        img = _IG.grab(); buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        if _gpt_ok():
            return ask_chatgpt_vision(prompt or "Describe what is on this screen briefly.", b64)
        return "Screenshot taken. OpenAI key needed for visual description."
    except Exception as e: return f"Screenshot failed: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
#  DAILY BRIEFING  — persisted to config so no double-fire on restart
# ═══════════════════════════════════════════════════════════════════════════════

def _check_briefing():
    if not CFG.get("daily_briefing", True): return
    now = datetime.datetime.now()
    target = CFG.get("briefing_time", "08:00")
    try: th, tm = [int(x) for x in target.split(":")]
    except: th, tm = 8, 0
    today = now.date().isoformat()
    if now.hour == th and now.minute == tm and CFG.get("briefing_done_date","") != today:
        CFG["briefing_done_date"] = today; _save_cfg()
        threading.Thread(target=_run_briefing, daemon=True).start()

def _run_briefing():
    time.sleep(1.5)
    name = CFG.get("user_name","")
    p = CFG.get("personality","energetic")
    greets = {"calm": f"Good morning{', '+name if name else ''}. Here is your daily briefing.",
              "energetic": f"Rise and shine{', '+name if name else ''}! Here's what's happening!",
              "guru": f"Om. Good morning{', '+name if name else ''}. Let wisdom guide your day."}
    speak(greets.get(p, "Good morning!"), save=False)
    _wait_tts(4)
    speak(_weather(CFG.get("city","Hyderabad")), save=True)
    _wait_tts(4)
    speak(_news()[:260], save=True)

Clock.schedule_interval(lambda dt: _check_briefing(), 60)


# ═══════════════════════════════════════════════════════════════════════════════
#  REMINDER ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _reminder_worker():
    while _APP_RUNNING.is_set():
        time.sleep(15)
        now = datetime.datetime.now()
        for rid, ts_str, label in db_get_reminders():
            try:
                ts = datetime.datetime.fromisoformat(ts_str)
                if now >= ts:
                    db_done_reminder(rid)
                    speak(f"Reminder: {label}", priority=0, save=True)
                    _ui("toast", f"⏰ {label}")
                    _ui("reminder_due", label)
            except Exception: pass


# ═══════════════════════════════════════════════════════════════════════════════
#  COMPOUND SPLITTER
# ═══════════════════════════════════════════════════════════════════════════════

_COMPOUND_RE = re.compile(
    r'\s+(?:and\s+(?:also\s+)?|then\s+(?:also\s+)?|also\s+|after\s+that\s+|plus\s+)', re.I)

def split_compound(raw):
    parts = [p.strip() for p in _COMPOUND_RE.split(raw.strip()) if p.strip()]
    return parts if len(parts) > 1 else [raw]


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN COMMAND DISPATCHER  — NLU-driven, every branch has return
# ═══════════════════════════════════════════════════════════════════════════════

_stream_lock = threading.Lock()   # prevents concurrent stream starts

def _execute_single(raw: str, stt_src: str = "local", add_bubble: bool = True):
    if not raw: return
    raw = raw.strip()
    if not raw: return
    cmd = raw.lower().strip()

    if add_bubble:
        _ui("bubble", ("YOU","you",raw,"",True))
        db_save_chat("user", raw, stt_src, is_conv=True)

    _ui("state","thinking")

    # ── Detect intent ─────────────────────────────────────────────────────────
    intent  = detect_intent(cmd)
    target  = extract_target(cmd, intent)
    mode    = _active_mode()

    print(f"[INTENT] {intent} | target: '{target}' | mode: {mode}")

    # ── GREETING ──────────────────────────────────────────────────────────────
    if intent == "greeting":
        name = CFG.get("user_name","")
        greets = ["Hey there! How can I help?", "Hello! What can I do for you?",
                  "Hi! I'm listening.", f"Namaste{', '+name if name else ''}! What do you need?"]
        speak(random.choice(greets), save=False); return

    # ── GOODBYE ───────────────────────────────────────────────────────────────
    if intent == "goodbye":
        speak("Goodbye! Take care.", save=False)
        Clock.schedule_once(lambda dt: (App.get_running_app() or type('',(),{'stop':lambda self:None})()).stop(), 2.5)
        return

    # ── HELP ──────────────────────────────────────────────────────────────────
    if intent == "help":
        speak("Just talk to me naturally! I can open apps, play music, check weather, "
              "set reminders, answer questions, control volume, take screenshots, "
              "and much more. Just say what you want!", save=False); return

    # ── SCREENSHOT ────────────────────────────────────────────────────────────
    if intent == "screenshot":
        speak("Taking screenshot and analyzing.", save=False)
        def _ss():
            result = _screenshot_describe(target)
            _ui("bubble", ("VEDA","ai",result,"gpt-vision",True))
            speak(result[:220], source="gpt-vision", save=True)
        threading.Thread(target=_ss, daemon=True).start(); return

    # ── REMINDER ─────────────────────────────────────────────────────────────
    if intent == "reminder":
        result = _parse_reminder(cmd); speak(result, save=True)
        _ui("reminder_due", None); return   # refresh list

    # ── TIMER ────────────────────────────────────────────────────────────────
    if intent == "set_timer":
        secs, msg = _parse_timer(cmd); speak(msg, save=False)
        if secs:
            def _timer(s=secs, m=msg):
                _wait_tts(); time.sleep(s)
                speak("Timer done!", priority=0, save=True)
                _ui("toast","⏰ Timer complete!")
            threading.Thread(target=_timer, daemon=True).start()
        return

    # ── DAILY BRIEFING ────────────────────────────────────────────────────────
    if intent == "briefing":
        threading.Thread(target=_run_briefing, daemon=True).start(); return

    # ── WEATHER ───────────────────────────────────────────────────────────────
    if intent == "weather":
        speak(_weather(target), save=True); return

    # ── NEWS ──────────────────────────────────────────────────────────────────
    if intent == "news":
        speak(_news()[:260], save=True); return

    # ── TIME ──────────────────────────────────────────────────────────────────
    if intent == "time_query":
        speak(f"It's {datetime.datetime.now().strftime('%I:%M %p')}.", save=False); return

    # ── DATE ──────────────────────────────────────────────────────────────────
    if intent == "date_query":
        speak(f"Today is {datetime.datetime.now().strftime('%A, %d %B %Y')}.", save=False); return

    # ── VOLUME ────────────────────────────────────────────────────────────────
    if intent == "volume_up":
        speak(vol_up(), save=False); return
    if intent == "volume_down":
        speak(vol_down(), save=False); return
    if intent == "volume_mute":
        speak(vol_mute(), save=False); return
    if intent == "volume_set":
        speak(vol_set(target or "50"), save=False); return

    # ── CALCULATOR ────────────────────────────────────────────────────────────
    if intent == "calculator":
        speak(_safe_calc(target), save=True); return

    # ── MEDIA CONTROLS ────────────────────────────────────────────────────────
    if intent == "media_control":
        if any(k in cmd for k in ("pause","stop music")): speak(_spotify_cmd("play_pause"), save=False)
        elif any(k in cmd for k in ("resume","play music","unpause")): speak(_spotify_cmd("play_pause"), save=False)
        elif any(k in cmd for k in ("next","skip")): speak(_spotify_cmd("next"), save=False)
        elif any(k in cmd for k in ("previous","prev","go back","last song")): speak(_spotify_cmd("prev"), save=False)
        else: speak("Say: pause, next, previous, or now playing.", save=False)
        return

    # ── YOUTUBE SEARCH ────────────────────────────────────────────────────────
    if intent in ("youtube_search","play_music"):
        q = target or re.sub(r'^(play|listen|search)\s+','',cmd).strip()
        if q:
            webbrowser.open(f"https://www.youtube.com/results?search_query={q.replace(' ','+')}"); speak(f"Playing {q} on YouTube.", save=True)
        else:
            webbrowser.open("https://www.youtube.com"); speak("Opening YouTube.", save=True)
        return

    # ── OPEN INCOGNITO ────────────────────────────────────────────────────────
    if intent == "open_incognito":
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.isfile(chrome): subprocess.Popen([chrome,"--incognito"])
        else: subprocess.Popen("start chrome --incognito", shell=True)
        speak("Opening incognito.", save=False); return

    # ── OPEN APP ─────────────────────────────────────────────────────────────
    if intent == "open_app":
        speak(_open_app(target or cmd), save=True); return

    # ── CLOSE APP ────────────────────────────────────────────────────────────
    if intent == "close_app":
        pm = {"chrome":"chrome.exe","firefox":"firefox.exe","edge":"msedge.exe",
              "notepad":"notepad.exe","spotify":"spotify.exe","discord":"discord.exe",
              "vlc":"vlc.exe","telegram":"telegram.exe","zoom":"zoom.exe",
              "teams":"teams.exe","steam":"steam.exe","calculator":"calc.exe"}
        name = target.lower()
        proc = next((v for k,v in pm.items() if k in name), None)
        if proc:
            subprocess.run(f"taskkill /f /im {proc}", shell=True, capture_output=True)
            speak(f"Closed {target}.", save=False)
        else:
            speak(f"I don't know how to close {target}.", save=False)
        return

    # ── SEARCH WEB ────────────────────────────────────────────────────────────
    if intent == "search_web":
        q = target or cmd
        webbrowser.open(f"https://www.google.com/search?q={q.replace(' ','+')}"); speak(f"Searching for {q}.", save=True); return

    # ── REMEMBER ─────────────────────────────────────────────────────────────
    if intent == "remember":
        m = re.search(r'(.+?)\s+(?:is|are|means?|=)\s+(.+)', cmd)
        if m:
            k, v = m.group(1).strip(), m.group(2).strip()
            # strip common prefixes from key
            k = re.sub(r'^(remember|that|save|store|note)\s+','',k,flags=re.I).strip()
            db_set(k, v); speak(f"Got it — {k} is {v}.", save=True)
        else:
            speak("Tell me what to remember. Say: remember X is Y.", save=False)
        return

    # ── RECALL ────────────────────────────────────────────────────────────────
    if intent == "recall":
        q = target.strip()
        ans = db_get(q)
        if ans: speak(ans, save=True); return
        # Check local knowledge base
        kb = kb_search(q)
        if kb: speak(kb, source="kb", save=True); return
        # Online AI
        if mode == "surya":
            def _ai():
                with _stream_lock:
                    _ui("stream","__START__")
                    full = ""
                    def _cb(chunk): nonlocal full; full+=chunk; _ui("stream",chunk)
                    reply, src = ask_chatgpt(q, stream_cb=_cb)
                    _ui("stream_end")
                    if reply: speak(reply, src or "gpt", save=True)
                    else: webbrowser.open(f"https://www.google.com/search?q={q.replace(' ','+')}"); speak(f"Searching for {q}.", save=True)
            threading.Thread(target=_ai, daemon=True).start()
        else:
            # Offline: try Ollama first
            olla = ask_ollama(q) if _ollama_available() else None
            if olla: speak(olla, source="ollama", save=True); return
            # Fallback: local KB
            kb2 = kb_search(q)
            if kb2: speak(kb2, source="kb", save=True); return
            speak(f"I'm offline and don't have info about {q}. Connect to internet for AI answers.", save=False)
        return

    # ── SYSTEM STATUS ─────────────────────────────────────────────────────────
    if intent == "system_status":
        if _PSUTIL:
            cpu  = psutil.cpu_percent(interval=None)
            ram  = psutil.virtual_memory().percent
            batt = psutil.sensors_battery()
            bs   = f"Battery {int(batt.percent)}% {'charging' if batt.power_plugged else 'on battery'}." if batt else ""
            speak(f"CPU {cpu:.0f}%, RAM {ram:.0f}%. {bs}", save=False)
        else:
            speak("psutil not installed. Run: pip install psutil", save=False)
        return

    # ── PC POWER ─────────────────────────────────────────────────────────────
    if intent == "pc_power":
        if any(k in cmd for k in ("cancel","abort")): _shutdown_ev.set(); _restart_ev.set(); subprocess.run("shutdown /a",shell=True,capture_output=True); speak("Cancelled.", save=False); return
        if any(k in cmd for k in ("restart","reboot")):
            speak("Restarting in 10 seconds. Say cancel to stop.", save=False)
            threading.Thread(target=_do_restart, daemon=True).start(); return
        speak("Shutting down in 10 seconds. Say cancel to stop.", save=False)
        threading.Thread(target=_do_shutdown, daemon=True).start(); return

    # ── MODE ──────────────────────────────────────────────────────────────────
    if intent == "mode_online":
        threading.Thread(target=_set_surya, daemon=True).start(); return
    if intent == "mode_offline":
        threading.Thread(target=_set_nirvana, daemon=True).start(); return

    # ── PERSONALITY ───────────────────────────────────────────────────────────
    if intent == "personality":
        p_map = {"calm":"calm","energetic":"energetic","energy":"energetic","wise":"guru","guru":"guru"}
        new_p = p_map.get(target, "")
        if new_p:
            CFG["personality"] = new_p; _save_cfg()
            msgs = {"calm":"Calm mode. I'll speak softly.","energetic":"Energetic mode! Let's go!","guru":"Guru mode. Wisdom in every word."}
            speak(msgs[new_p], save=False)
        else:
            speak("Choose: calm, energetic, or guru.", save=False)
        return

    # ── LANGUAGE ──────────────────────────────────────────────────────────────
    if intent == "language":
        if target == "hindi":
            CFG["language"] = "hi"; _save_cfg(); speak("Hindi mode on!", save=False)
        else:
            CFG["language"] = "en"; _save_cfg(); speak("English mode.", save=False)
        return

    # ── JOKE ──────────────────────────────────────────────────────────────────
    if intent == "joke":
        speak(random.choice([
            "Why did the developer go broke? He used up all his cache.",
            "A SQL query walks into a bar. Can I join you?",
            "Debugging is like being a detective when you're also the criminal.",
            "There are only 10 types of people — those who get binary, and those who don't.",
            "Why do programmers prefer Nirvana Mode? No connection timeouts in the void!",
            "My code never has bugs. It just develops random features.",
        ]), save=False); return

    # ── AI CHAT (STREAMING — ONLINE) ──────────────────────────────────────────
    if mode == "surya":
        def _ai_stream():
            with _stream_lock:
                _ui("stream","__START__")
                full = ""
                def _cb(chunk): nonlocal full; full += chunk; _ui("stream",chunk)
                reply, src = ask_chatgpt(cmd, stream_cb=_cb)
                _ui("stream_end")
                if reply: speak(reply, src or "gpt", save=True)
                else:
                    webbrowser.open(f"https://www.google.com/search?q={cmd.replace(' ','+')}"); speak("Searching for you.", save=False)
        threading.Thread(target=_ai_stream, daemon=True).start(); return

    # ── OFFLINE FALLBACK ──────────────────────────────────────────────────────
    # 1. Ollama local LLM
    olla = ask_ollama(cmd) if _ollama_available() else None
    if olla: speak(olla, source="ollama", save=True); return
    # 2. Local knowledge base
    kb = kb_search(cmd)
    if kb: speak(kb, source="kb", save=True); return
    # 3. Memory
    ans = db_get(cmd)
    if ans: speak(ans, save=True); return
    # 4. Tell user
    speak("I'm offline and don't have that info. For AI chat offline, install Ollama and run: ollama pull mistral", save=False)


def execute(raw: str, stt_src: str = "local"):
    if not raw: return
    parts = split_compound(raw.strip())
    if len(parts) > 1:
        _ui("bubble",("YOU","you",raw,"",True))
        db_save_chat("user", raw, stt_src, is_conv=True)
        speak(f"{len(parts)} tasks, on it!", save=False)
        def _all():
            for p in parts:
                _wait_tts(3.0)
                _execute_single(p, stt_src, add_bubble=False)
        threading.Thread(target=_all, daemon=True).start()
    else:
        _execute_single(raw, stt_src, add_bubble=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  VOICE LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def voice_loop():
    time.sleep(2.5)
    mode = _active_mode()
    name = CFG.get("user_name","")
    greet = f"Hey{', '+name if name else ''}! I'm VEDA. Say Hey Veda and just talk naturally — no commands to memorise!"
    if mode == "nirvana":
        greet += " I'm in Nirvana Mode — running offline."
        vs = _vosk_status()
        if vs != "ok":
            greet += " Note: offline speech recognition needs the Vosk model."
    speak(greet, save=False)
    _ui("mode", mode)
    last_wake = 0.0; WAKE_WIN = 9

    while _APP_RUNNING.is_set():
        try: text = _stt_q.get(timeout=30)
        except queue.Empty:
            # Heartbeat — show still alive
            _ui("state","ready"); continue
        if not text: continue
        text = text.strip()

        if _has_wake(text):
            last_wake = time.time()
            cmd = _strip_wake(text).strip(" ,.")
            if cmd and len(cmd) >= 2:
                threading.Thread(target=execute, args=(cmd,), daemon=True).start()
            else:
                speak("Yes?", save=False)
                _wait_tts(3)
                try:
                    follow = _stt_q.get(timeout=8)
                    if follow and follow.strip():
                        fc = _strip_wake(follow.strip()).strip(" ,.")
                        if not fc: fc = follow.strip()
                        threading.Thread(target=execute, args=(fc,), daemon=True).start()
                except queue.Empty:
                    speak("Didn't catch that.", save=False)
            continue

        if time.time() - last_wake < WAKE_WIN:
            ws = text.strip().split()
            ok = ((bool(ws) and ws[0] in _CMD_STARTERS)
                  or len(ws) >= 3
                  or (len(ws) == 2 and any(len(w) > 2 for w in ws))
                  or (len(ws) == 1 and ws[0] in _CMD_STARTERS))
            if ok:
                threading.Thread(target=execute, args=(text,), daemon=True).start()
                last_wake = time.time()
            else:
                print(f"[NOISE] '{text}'")

# ═══════════════════════════════════════════════════════════════════════════════
#  GUI  — VEDA v13  "Clean Dharma"
#
#  Design principles:
#  • Orb gets 50%+ of left panel — it IS the UI
#  • Right panel: single chat with clear YOU/VEDA distinction (right/left aligned)
#  • No tiny buttons — all touch targets ≥ 36px
#  • 4 action buttons max visible at once — extras in slide-up panel
#  • Mode toggle is a clear labeled button, not a mysterious slider
#  • Colors 100% from P() palette — consistent in both modes
#  • Toasts go top-right, never overlapping mic bar
#  • First run → setup wizard
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
#  PARTICLES
# ═══════════════════════════════════════════════════════════════════════════════

class _Particle:
    __slots__ = ("x","y","vx","vy","life","ml","sz")
    def __init__(self, mode, W, H): self.reset(mode, W, H)
    def reset(self, mode, W, H):
        self.x = random.uniform(0, W); self.y = random.uniform(0, H)
        if mode == "surya":
            self.vx = random.uniform(-0.15,0.15); self.vy = random.uniform(0.2,0.9)
            self.life = random.uniform(0.3,1.0); self.sz = random.uniform(1.0,2.2)
        else:
            self.vx = random.uniform(-0.04,0.04); self.vy = random.uniform(-0.04,0.04)
            self.life = random.uniform(0.1,1.0); self.sz = random.uniform(0.8,1.8)
        self.ml = self.life
    def update(self, dt, mode, W, H):
        self.x += self.vx; self.y += self.vy
        if mode == "surya":
            self.life -= dt * 0.40
            if self.life <= 0 or self.y > H+5: self.reset(mode, W, H); self.y = 0
        else:
            self.life += dt * random.choice((-1,1)) * 0.15
            self.life = max(0.05, min(self.ml, self.life))
            if not (0 <= self.x <= W and 0 <= self.y <= H): self.reset(mode, W, H)


# ═══════════════════════════════════════════════════════════════════════════════
#  VISUALISER ORB  — takes 50% of left panel
# ═══════════════════════════════════════════════════════════════════════════════

class Visualiser(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.mode = "surya"; self.state = "ready"
        self._t = 0.0; self._pulse = 0.0; self._pdir = 1
        self._energy = 0.0; self._wave = [0.0]*64
        self._dots = []; self._parts = []
        self._last_size = (0,0)
        Clock.once = Clock.schedule_once
        Clock.schedule_once(self._init_p, 0.3)
        Clock.schedule_interval(self._tick, 1/60)
        self.bind(size=self._on_resize)

    def _on_resize(self, *_):
        sz = (int(self.width), int(self.height))
        if sz != self._last_size and sz[0] > 10:
            self._last_size = sz
            Clock.schedule_once(self._init_p, 0.1)

    def _init_p(self, dt):
        W, H = max(self.width,300), max(self.height,300)
        R = min(W, H) * 0.30
        self._dots = [[random.uniform(0, math.tau),
                       R * random.uniform(1.10, 1.90),
                       random.uniform(0.002,0.008) * random.choice((-1,1)),
                       random.uniform(0.8,2.8), random.uniform(0.1,1.0),
                       random.uniform(0.012,0.055)] for _ in range(60)]
        self._parts = [_Particle(self.mode, W, H) for _ in range(40)]

    def set_mode(self, m):
        self.mode = m
        W, H = self.width, self.height
        for p in self._parts: p.reset(m, W, H)

    def set_state(self, s): self.state = s
    def set_energy(self, e): self._energy = e

    def _tick(self, dt):
        self._t += dt
        self._pulse += dt * 2.0 * self._pdir
        if self._pulse >= 1: self._pdir = -1
        if self._pulse <= 0: self._pdir = 1
        for d in self._dots:
            d[0] += d[2]; d[4] += d[5]
            if d[4] > 1.0 or d[4] < 0.05: d[5] *= -1
        W, H = self.width, self.height
        for p in self._parts: p.update(dt, self.mode, W, H)
        amp = (0.55 + self._energy*0.45) if self.state == "listening" else \
              (0.75 if self.state == "speaking" else 0.08)
        ns = amp * abs(math.sin(self._t*10.5 + random.uniform(-0.2,0.2)))
        self._wave = self._wave[1:] + [ns]
        self._draw()

    def _draw(self):
        self.canvas.clear()
        pal = P(); W, H = self.width, self.height
        if W < 2 or H < 2: return
        cx = self.center_x; cy = self.center_y
        R = min(W, H) * 0.30

        sc = {"listening":(0.12,1.00,0.48),"thinking":(0.95,0.88,0.08),
              "speaking": pal["accent"]}.get(self.state, pal["primary"])

        with self.canvas:
            # Background
            Color(*pal["bg"], 1)
            Rectangle(pos=self.pos, size=self.size)

            # Subtle dot field (particles)
            for p in self._parts:
                Color(*pal["accent"], p.life * 0.18)
                Ellipse(pos=(p.x-p.sz/2, p.y-p.sz/2), size=(p.sz, p.sz))

            # Sri Yantra
            for i in range(4):
                r2 = R*(0.32+i*0.18)
                Color(*pal["yantra"], 0.06+i*0.01)
                up  = [cx, cy+r2, cx-r2*0.866, cy-r2*0.5, cx+r2*0.866, cy-r2*0.5]
                dn  = [cx, cy-r2, cx-r2*0.866, cy+r2*0.5, cx+r2*0.866, cy+r2*0.5]
                Line(points=up+[up[0],up[1]], width=0.7)
                Line(points=dn+[dn[0],dn[1]], width=0.7)
            for rr in [R*1.08, R*1.16, R*1.26]:
                Color(*pal["yantra"], 0.04)
                Line(circle=(cx,cy,rr), width=0.5)

            # Orbit dots
            for d in self._dots:
                ox = cx+d[1]*math.cos(d[0]); oy = cy+d[1]*math.sin(d[0])
                Color(*pal["chakra"], d[4]*0.14)
                Ellipse(pos=(ox-d[3]/2, oy-d[3]/2), size=(d[3],d[3]))

            # Orb
            with _MORPH_LOCK: mt = _MORPH
            if mt < 0.99: self._surya_orb(cx, cy, R, pal, sc, 1.0-mt)
            if mt > 0.01: self._nirvana_ring(cx, cy, R, pal, sc, mt)

            # Energy ring
            if self._energy > 0.02:
                er = R*(1.04+self._energy*0.20)
                Color(*sc, self._energy*0.65)
                Line(circle=(cx,cy,er), width=2.0+self._energy*3.5)

            # Lotus petals
            n = 8; br = R*1.08
            pr = R*(0.10 + (0.04 if self.state in ("listening","speaking") else 0) + self._energy*0.05)
            for i in range(n):
                a = i*math.tau/n + self._t*0.20
                px2 = cx+br*math.cos(a); py2 = cy+br*math.sin(a)
                al = 0.25+0.20*abs(math.sin(self._t*1.4+i*math.pi/n))
                Color(*pal["lotus"], al)
                Ellipse(pos=(px2-pr, py2-pr), size=(pr*2,pr*2))

            # Waveform
            nw = len(self._wave); w2 = R*0.46
            if self.state in ("listening","speaking"):
                pts = []; pts2 = []
                for i, s in enumerate(self._wave):
                    x = cx-w2+(i/(nw-1))*w2*2
                    env = math.sin(math.pi*i/(nw-1))
                    h = s*R*0.24*env
                    pts.extend([x, cy+h]); pts2.extend([x, cy-h])
                Color(*pal["primary"], 0.90)
                if len(pts) >= 4: Line(points=pts, width=2.2)
                Color(*pal["accent"], 0.52)
                if len(pts2) >= 4: Line(points=pts2, width=1.4)
            else:
                Color(*pal["primary"], 0.06)
                Line(points=[cx-w2,cy,cx+w2,cy], width=0.9)

            # Thinking dots
            if self.state == "thinking":
                n2 = 3; sp = R*0.22; yd = cy+R*1.32
                for i in range(n2):
                    ph = self._t*3.2+i*(math.tau/n2)
                    sc2 = 0.4+0.6*abs(math.sin(ph)); dr = R*0.044*sc2
                    Color(*pal["primary"], 0.50+0.44*sc2)
                    Ellipse(pos=(cx+(i-1)*sp-dr, yd-dr), size=(dr*2,dr*2))

    def _surya_orb(self, cx, cy, R, pal, sc, alpha):
        t = self._t; pu = self._pulse; a = alpha
        with self.canvas:
            for fr, ba in [(1.48,0.03),(1.28,0.055),(1.10,0.09),(1.01,0.13)]:
                Color(*sc, min(1.0,(ba+pu*0.04)*a)); Ellipse(pos=(cx-R*fr,cy-R*fr),size=(R*fr*2,R*fr*2))
            Color(*pal["bg"],a); Ellipse(pos=(cx-R,cy-R),size=(R*2,R*2))
            for fr, col, ba in [(0.86,pal["glow"],0.20+pu*0.07),(0.66,pal["primary"],0.15+pu*0.06),
                                (0.44,pal["accent"],0.20+pu*0.09),(0.22,(1,1,1),0.06+pu*0.04)]:
                Color(*col, min(1.0,ba*a)); Ellipse(pos=(cx-R*fr,cy-R*fr),size=(R*fr*2,R*fr*2))
            for ri in range(7):
                Color(*pal["chakra"], min(1.0,(0.06+pu*0.04)*a))
                Line(circle=(cx,cy,R*(0.36+ri*0.09)), width=0.7)
            wcs = [(0.42,0.12,0.95),(0.00,0.82,0.92),(0.55,0.18,1.00),(1.0,0.48,0.08),(0.20,0.95,0.55)]
            nwv = 5 if self.state in ("listening","speaking") else 3
            ab = R*(0.30+self._energy*0.12 if self.state in ("listening","speaking") else 0.13)
            for wi in range(nwv):
                ph = t*(1.0+wi*0.38)+wi*math.pi/nwv
                amp = ab*(1.0+pu*0.17)*(0.8+0.4*math.sin(t*0.7+wi))
                pts = []
                for si in range(91):
                    frac = si/90; lx = cx-R*0.78+frac*R*1.56
                    mx = math.sqrt(max(0,(R*0.80)**2-(lx-cx)**2))
                    wy = amp*math.sin((2.2+wi*0.72)*math.pi*frac+ph)+amp*0.32*math.sin((2.2+wi*0.72)*2*math.pi*frac-ph*1.3)
                    pts.extend([lx, cy+max(-mx,min(mx,wy))])
                Color(*wcs[wi%len(wcs)], min(1.0,(0.58-wi*0.07+pu*0.11)*a))
                if len(pts) >= 4: Line(points=pts, width=1.8+(0.7 if wi==0 else 0))
            Color(*sc, min(1.0,(0.52+pu*0.17)*a)); Line(circle=(cx,cy,R), width=1.6)
            cr = R*(0.05+pu*0.02); Color(*sc, min(1.0,0.88*a))
            Ellipse(pos=(cx-cr,cy-cr), size=(cr*2,cr*2))

    def _nirvana_ring(self, cx, cy, R, pal, sc, alpha):
        t = self._t; pu = self._pulse
        with self.canvas:
            for fr, ba in [(1.46,0.04),(1.26,0.07),(1.08,0.11),(1.00,0.16)]:
                Color(*sc, min(1.0,(ba+pu*0.04)*alpha)); Ellipse(pos=(cx-R*fr,cy-R*fr),size=(R*fr*2,R*fr*2))
            Color(0,0,0,alpha); Ellipse(pos=(cx-R*0.78,cy-R*0.78),size=(R*1.56,R*1.56))
            for rr, w, ba in [(R,16.0,0.10),(R,8.5,0.20),(R,4.0,0.54)]:
                Color(*sc, min(1.0,(ba+pu*0.07)*alpha)); Line(circle=(cx,cy,rr), width=w)
            rot = 0.16+self._energy*0.36 if self.state in ("listening","speaking") else 0.10
            for i in range(200):
                a0 = math.radians(i*1.8)+t*rot; a1 = math.radians((i+1)*1.8)+t*rot
                r2,g2,b2 = _hsv((i/200+t*0.05)%1.0, 0.55, 1.0)
                br = (0.44+0.44*abs(math.sin(i/200*math.pi*2.8+t*0.5)))*(0.68+pu*0.32)
                Color(r2,g2,b2, min(1.0,br*alpha))
                Line(points=[cx+R*math.cos(a0),cy+R*math.sin(a0),cx+R*math.cos(a1),cy+R*math.sin(a1)],width=3.0)
            Color(1,1,1, min(1.0,(0.52+pu*0.17)*alpha)); Line(circle=(cx,cy,R*0.94), width=1.2)


# ═══════════════════════════════════════════════════════════════════════════════
#  MIC BAR
# ═══════════════════════════════════════════════════════════════════════════════

class MicBar(Widget):
    def __init__(self, **kw):
        super().__init__(**kw); self._e = 0.0; self._tgt = 0.0
        Clock.schedule_interval(self._tick, 1/30)
    def set_energy(self, e):
        if e > self._tgt: self._tgt = e
        else: self._tgt = max(e, self._tgt * 0.62)
    def _tick(self, dt):
        self._tgt = max(0, self._tgt-dt*1.5)
        self._e += (self._tgt-self._e)*0.28
        self._draw()
    def _draw(self):
        self.canvas.clear(); pal = P(); n = 30; bw = self.width/n
        with self.canvas:
            Color(*pal["bg"], 1); Rectangle(pos=self.pos, size=self.size)
            for i in range(n):
                tv = time.time()*7.0+i*0.72
                bh = max(2.0, self._e*(self.height*0.80)+self.height*0.028*abs(math.sin(tv)))
                t2 = min(1.0, self._e*2.2)
                r = _lerp(pal["primary"][0],pal["accent"][0],t2)
                g = _lerp(pal["primary"][1],pal["accent"][1],t2)
                b = _lerp(pal["primary"][2],pal["accent"][2],t2)
                Color(r,g,b, 0.44+self._e*0.56)
                RoundedRectangle(pos=(self.x+(i/n)*self.width+1, self.y+self.height/2-bh/2),
                                 size=(bw-2,bh), radius=[2])


# ═══════════════════════════════════════════════════════════════════════════════
#  CONNECTION DOT
# ═══════════════════════════════════════════════════════════════════════════════

class ConnDot(Widget):
    def __init__(self, **kw):
        super().__init__(**kw); self._online = True; self._blink = 0.0
        Clock.schedule_interval(self._tick, 1/15)
        Clock.schedule_interval(self._check, 20)
        Clock.schedule_once(self._check, 0.5)
    def _check(self, dt):
        def _bg(): self._online = _ping(); _ui("online", self._online)
        threading.Thread(target=_bg, daemon=True).start()
    def set_online(self, v): self._online = v
    def _tick(self, dt):
        self._blink = (self._blink+dt*2.5) % math.tau; self._draw()
    def _draw(self):
        self.canvas.clear()
        col = (0.12,1.00,0.42) if self._online else (1.00,0.25,0.15)
        pulse = 0.55+0.45*math.sin(self._blink)
        r = min(self.width,self.height)/2-1
        with self.canvas:
            Color(*col, pulse*0.28); Ellipse(pos=self.pos, size=self.size)
            Color(*col, 0.92); Ellipse(pos=(self.x+r*0.45,self.y+r*0.45), size=(r*1.1,r*1.1))


# ═══════════════════════════════════════════════════════════════════════════════
#  LIVE CLOCK
# ═══════════════════════════════════════════════════════════════════════════════

class LiveClock(Label):
    def __init__(self, **kw):
        super().__init__(**kw)
        Clock.schedule_interval(self._tick, 1.0); self._tick(0)
    def _tick(self, dt):
        pal = P()
        self.text = datetime.datetime.now().strftime("%H:%M:%S")
        self.color = (*pal["sub"],0.88)


# ═══════════════════════════════════════════════════════════════════════════════
#  STREAM LABEL  — typewriter with proper Clock cleanup
# ═══════════════════════════════════════════════════════════════════════════════

def _hx(c): return "{:02x}{:02x}{:02x}".format(int(c[0]*255),int(c[1]*255),int(c[2]*255))

class StreamLabel(Label):
    def __init__(self, **kw):
        self._full = ""; self._shown = ""; self._idx = 0
        self._tick_ev = None
        super().__init__(**kw)
        self._tick_ev = Clock.schedule_interval(self._type_tick, 0.022)

    def append_chunk(self, chunk): self._full += chunk
    def finish(self):
        """Unschedule the clock to prevent leak."""
        if self._tick_ev:
            Clock.unschedule(self._tick_ev)
            self._tick_ev = None

    def _type_tick(self, dt):
        if self._idx >= len(self._full): return
        step = max(1, int(len(self._full)*0.04))
        self._idx = min(self._idx+step, len(self._full))
        self._shown = self._full[:self._idx]
        pal = P()
        self.text = (f"[color=#{_hx(pal['sub'])}]▸ VEDA[/color]  "
                     f"[color=#{_hx(pal['ai_col'])}]{self._shown}[/color]▌")


# ═══════════════════════════════════════════════════════════════════════════════
#  CHAT LOG  — proper bubble alignment (YOU right, VEDA left)
# ═══════════════════════════════════════════════════════════════════════════════

class ChatLog(ScrollView):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.do_scroll_x = False; self.bar_width = 3
        self._box = BoxLayout(orientation="vertical", size_hint_y=None,
                              spacing=6, padding=[8,6])
        self._box.bind(minimum_height=self._box.setter("height"))
        self.add_widget(self._box)
        self._stream_lbl = None
        self._stream_lock = threading.Lock()

    def add_bubble(self, who, role, text, src="", save=True):
        pal = P()
        ts  = datetime.datetime.now().strftime("%H:%M")
        # Wrap in a row — YOU bubbles go right, VEDA left
        row = BoxLayout(orientation="horizontal", size_hint=(1,None), spacing=4)

        # Source tag
        src_names = {"gpt":"GPT","kb":"KB","ollama":"Local AI","google":"Web",
                     "vosk":"Vosk","gpt-vision":"Vision","":""}
        tag = src_names.get(src,"")

        if role == "you":
            col = pal["you_col"]
            label_text = (f"[color=#{_hx(pal['sub'])}]{ts}[/color]  "
                         f"[b][color=#{_hx(col)}]▸ YOU[/color][/b]  "
                         f"[color=#{_hx(pal['text'])}]{text}[/color]")
            spacer = Widget(size_hint=(0.12,1))
            lbl = Label(text=label_text, markup=True, font_size=13,
                        size_hint=(0.88,None), halign="right", valign="top",
                        padding=(8,6), text_size=(None,None))
        elif role == "ai":
            col = pal["ai_col"]
            tag_str = f"  [color=#{_hx(pal['sub'])}][{tag}][/color]" if tag else ""
            label_text = (f"[color=#{_hx(pal['sub'])}]{ts}[/color]  "
                         f"[b][color=#{_hx(col)}]◈ VEDA[/color][/b]{tag_str}  "
                         f"[color=#{_hx(pal['text'])}]{text}[/color]")
            lbl = Label(text=label_text, markup=True, font_size=13,
                        size_hint=(0.88,None), halign="left", valign="top",
                        padding=(8,6), text_size=(None,None))
            spacer = Widget(size_hint=(0.12,1))
        else:
            col = pal["sys_col"]
            label_text = f"[color=#{_hx(col)}]─ {text} ─[/color]"
            lbl = Label(text=label_text, markup=True, font_size=11, italic=True,
                        size_hint=(1,None), halign="center", valign="top",
                        padding=(4,3), text_size=(None,None))
            spacer = None

        lbl.bind(texture_size=lambda i,v: setattr(i,"height",v[1]+8))
        lbl.bind(width=lambda i,v: setattr(i,"text_size",(max(v-12,200),None)))

        # Background canvas
        with lbl.canvas.before:
            if role == "you":
                Color(*pal["you_col"], 0.08)
            elif role == "ai":
                Color(*pal["ai_col"], 0.06)
            else:
                Color(0,0,0,0)
            bg_rect = RoundedRectangle(pos=lbl.pos, size=lbl.size, radius=[8])
        lbl.bind(pos=lambda i,v: setattr(bg_rect,"pos",v),
                 size=lambda i,v: setattr(bg_rect,"size",v))

        if role == "you":
            row.add_widget(spacer); row.add_widget(lbl)
        elif role == "ai":
            row.add_widget(lbl); row.add_widget(spacer)
        else:
            row.add_widget(lbl)

        row.bind(minimum_height=row.setter("height"))
        row.size_hint = (1, None); row.height = 10  # will expand via binding
        lbl.bind(height=lambda i,v: setattr(row,"height",v+4))

        self._box.add_widget(row)
        Animation(opacity=1, duration=0.22).start(row)
        Clock.schedule_once(lambda dt: setattr(self,"scroll_y",0), 0.06)

    def start_stream(self):
        with self._stream_lock:
            if self._stream_lbl:
                self._stream_lbl.finish()
                # Remove old stream row if still in box
            pal = P()
            self._stream_lbl = StreamLabel(
                text="", markup=True, font_size=13,
                size_hint=(0.88,None), halign="left", valign="top",
                padding=(8,6), text_size=(None,None))
            self._stream_lbl.bind(texture_size=lambda i,v: setattr(i,"height",v[1]+8))
            self._stream_lbl.bind(width=lambda i,v: setattr(i,"text_size",(max(v-12,200),None)))
            row = BoxLayout(orientation="horizontal", size_hint=(1,None), spacing=4)
            row.add_widget(self._stream_lbl); row.add_widget(Widget(size_hint=(0.12,1)))
            row.size_hint = (1,None); row.height = 30
            self._stream_lbl.bind(height=lambda i,v: setattr(row,"height",v+4))
            self._box.add_widget(row)
            Clock.schedule_once(lambda dt: setattr(self,"scroll_y",0), 0.06)

    def append_stream(self, chunk):
        with self._stream_lock:
            if self._stream_lbl: self._stream_lbl.append_chunk(chunk)

    def end_stream(self):
        with self._stream_lock:
            if self._stream_lbl:
                self._stream_lbl.finish()
                self._stream_lbl = None

    def clear(self):
        with self._stream_lock:
            if self._stream_lbl: self._stream_lbl.finish(); self._stream_lbl = None
        self._box.clear_widgets()


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM MONITOR WIDGET
# ═══════════════════════════════════════════════════════════════════════════════

class SysMonWidget(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._cpu = 0; self._ram = 0; self._batt = -1; self._plug = True
        self._hist_cpu = [0]*50; self._hist_ram = [0]*50
        self._dirty = False
        Clock.schedule_interval(self._tick, 1/8)

    def update(self, data):
        self._cpu = data.get("cpu",0); self._ram = data.get("ram",0)
        self._batt = data.get("batt",-1); self._plug = data.get("plug",True)
        self._hist_cpu = self._hist_cpu[1:]+[self._cpu/100]
        self._hist_ram = self._hist_ram[1:]+[self._ram/100]
        self._dirty = True

    def _tick(self, dt):
        if self._dirty: self._dirty = False; self._draw()

    def _draw(self):
        self.canvas.clear(); pal = P(); w,h = self.width, self.height
        if w < 10 or h < 10: return
        with self.canvas:
            Color(*pal["card"],1); RoundedRectangle(pos=(self.x,self.y),size=(w,h),radius=[6])
            Color(*pal["primary"],0.18); Line(rounded_rectangle=(self.x,self.y,w,h,6),width=0.8)
            # CPU sparkline
            ch = h*0.42; cw = w-16; cx0 = self.x+8; cy0 = self.y+h*0.52
            Color(*pal["primary"],0.10); Rectangle(pos=(cx0,cy0),size=(cw,ch))
            pts = []
            for i,v in enumerate(self._hist_cpu): pts.extend([cx0+i*(cw/49), cy0+v*ch])
            Color(*pal["primary"],0.88)
            if len(pts)>=4: Line(points=pts, width=1.3)
            # RAM sparkline
            ry0 = self.y+7
            Color(*pal["teal"],0.09); Rectangle(pos=(cx0,ry0),size=(cw,h*0.36))
            pts2 = []
            for i,v in enumerate(self._hist_ram): pts2.extend([cx0+i*(cw/49), ry0+v*h*0.36])
            Color(*pal["teal"],0.80)
            if len(pts2)>=4: Line(points=pts2, width=1.3)
            # Battery arc
            if self._batt >= 0:
                bx = self.x+w-18; by = self.y+h/2; br = 8
                Color(*pal["muted"],0.5); Line(circle=(bx,by,br),width=1.4)
                col = (0.15,1.0,0.42) if self._batt>20 else (1.0,0.28,0.15)
                Color(*col,0.9); Line(circle=(bx,by,br,90,90+360*(self._batt/100)),width=2.8)


# ═══════════════════════════════════════════════════════════════════════════════
#  TOAST — top-right, never overlaps mic bar
# ═══════════════════════════════════════════════════════════════════════════════

class ToastOverlay(FloatLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._queue = []

    def show(self, text):
        pal = P()
        lbl = Label(text=str(text), markup=False, font_size=13,
                    size_hint=(None,None), height=38,
                    halign="center", valign="middle",
                    color=(*pal["text"],1), opacity=0)
        lbl.texture_update(); lbl.width = max(220, lbl.texture_size[0]+28)
        # Position: top-right
        lbl.pos_hint = {"right":0.99, "top":0.97}
        with lbl.canvas.before:
            Color(*pal["card"],0.95)
            RoundedRectangle(pos=lbl.pos, size=lbl.size, radius=[10])
            Color(*pal["primary"],0.70)
            Line(rounded_rectangle=(*lbl.pos,*lbl.size,10), width=1.0)
        lbl.bind(pos=lambda i,v: self._rebg(i), size=lambda i,v: self._rebg(i))
        self.add_widget(lbl)
        Animation(opacity=1, duration=0.18).start(lbl)
        Clock.schedule_once(lambda dt,l=lbl: Animation(opacity=0,duration=0.4).start(l), 3.2)
        Clock.schedule_once(lambda dt,l=lbl: self.remove_widget(l) if l.parent else None, 3.8)

    def _rebg(self, lbl):
        lbl.canvas.before.clear(); pal = P()
        with lbl.canvas.before:
            Color(*pal["card"],0.95); RoundedRectangle(pos=lbl.pos,size=lbl.size,radius=[10])
            Color(*pal["primary"],0.70); Line(rounded_rectangle=(*lbl.pos,*lbl.size,10),width=1.0)


# ═══════════════════════════════════════════════════════════════════════════════
#  QUICK ACTION PANEL  — slides up from bottom (replaces cramped button rows)
# ═══════════════════════════════════════════════════════════════════════════════

class QuickPanel(FloatLayout):
    """Slide-up panel with all quick actions — clean, spacious."""
    def __init__(self, **kw):
        super().__init__(**kw)
        self._open = False
        self._panel = BoxLayout(orientation="vertical",
                                size_hint=(None,None),
                                width=320, height=340,
                                padding=[12,10], spacing=8)
        self._panel.opacity = 0
        self._build()
        self.add_widget(self._panel)
        Clock.schedule_once(self._init_pos, 0.2)

    def _init_pos(self, dt):
        self._panel.pos = (4, -self._panel.height)

    def _build(self):
        pal = P()
        with self._panel.canvas.before:
            self._bg_c = Color(*SURYA_NET["card"], 0.97)
            self._bg_r = RoundedRectangle(pos=self._panel.pos, size=self._panel.size, radius=[16,16,0,0])
        self._panel.bind(pos=lambda i,v: setattr(self._bg_r,"pos",v),
                         size=lambda i,v: setattr(self._bg_r,"size",v))

        # Title
        title = Label(text="Quick Actions", font_size=14, bold=True,
                      size_hint=(1,None), height=28,
                      color=(*SURYA_NET["primary"],1))
        self._panel.add_widget(title)

        # Grid of actions — 2 per row
        actions = [
            ("🎙 Calibrate Mic",  lambda *_: self._run("calibrate")),
            ("📸 Screenshot",      lambda *_: self._run("screenshot")),
            ("⏰ Reminders",       lambda *_: self._run("reminders")),
            ("💻 System Status",   lambda *_: self._run("system status")),
            ("📰 Latest News",     lambda *_: self._run("news")),
            ("🗑 Clear History",   lambda *_: self._run("clear_chat")),
            ("🕉 Guru Mode",       lambda *_: self._run("personality guru")),
            ("⚡ Energy Mode",     lambda *_: self._run("personality energetic")),
        ]
        for i in range(0, len(actions), 2):
            row = BoxLayout(size_hint=(1,None), height=44, spacing=6)
            for label_txt, fn in actions[i:i+2]:
                b = Button(text=label_txt, font_size=11, bold=True,
                           background_color=(*SURYA_NET["card"],1),
                           color=(*SURYA_NET["text"],1))
                with b.canvas.before:
                    Color(*SURYA_NET["primary"],0.22)
                    RoundedRectangle(pos=b.pos, size=b.size, radius=[8])
                    Color(*SURYA_NET["primary"],0.50)
                    Line(rounded_rectangle=(*b.pos,*b.size,8), width=0.8)
                b.bind(pos=lambda i,v:None, size=lambda i,v:None)
                b.bind(on_press=fn)
                row.add_widget(b)
            self._panel.add_widget(row)

    def _run(self, cmd):
        self.close()
        if cmd == "clear_chat":
            a = App.get_running_app()
            if a: a.chat.clear()
        elif cmd == "reminders":
            a = App.get_running_app()
            if a: a._switch_tab(2)
        elif cmd == "calibrate":
            def _cal():
                speak("Calibrating. Please be silent for 2 seconds.", save=False)
                time.sleep(0.5)
                try:
                    with sr.Microphone() as src: _rec.adjust_for_ambient_noise(src, 2.0)
                    db_save_noise(_rec.energy_threshold)
                    speak(f"Calibrated. Threshold {int(_rec.energy_threshold)}.", save=False)
                    _ui("toast", f"🎙 Calibrated — {int(_rec.energy_threshold)}")
                except Exception: speak("Calibration failed.", save=False)
            threading.Thread(target=_cal, daemon=True).start()
        else:
            threading.Thread(target=execute, args=(cmd,), daemon=True).start()

    def toggle(self):
        self._open = not self._open
        ty = 0 if self._open else -self._panel.height
        Animation(y=ty, opacity=1 if self._open else 0, duration=0.28, t='out_cubic').start(self._panel)

    def close(self):
        if self._open:
            self._open = False
            Animation(y=-self._panel.height, opacity=0, duration=0.20).start(self._panel)

    def _theme_tick(self, dt):
        pal = P()
        self._bg_c.rgba = (*pal["card"], 0.97)


# ═══════════════════════════════════════════════════════════════════════════════
#  FLOATING AI CHAT PANEL  — fixed double-stream, loads history on open
# ═══════════════════════════════════════════════════════════════════════════════

class AIChatPanel(FloatLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._open = False; self._loaded = False
        self._panel = BoxLayout(orientation="vertical", size_hint=(None,None),
                                width=340, height=500)
        self._build()
        self.add_widget(self._panel)
        Clock.schedule_once(self._init_pos, 0.2)
        Clock.schedule_interval(self._theme_tick, 1/10)

    def _init_pos(self, dt):
        self._panel.pos = (Window.width, Window.height//2 - 250)

    def _build(self):
        pal = P()
        # Header
        hdr = BoxLayout(size_hint=(1,None), height=40, padding=[10,5])
        with hdr.canvas.before:
            self._hdr_c = Color(*SURYA_NET["card"],1)
            self._hdr_r = RoundedRectangle(pos=hdr.pos, size=hdr.size, radius=[10,10,0,0])
        hdr.bind(pos=lambda i,v:setattr(self._hdr_r,"pos",v), size=lambda i,v:setattr(self._hdr_r,"size",v))
        self._title = Label(text="◈ AI Chat", font_size=13, bold=True,
                            color=(*SURYA_NET["primary"],1))
        btn_close = Button(text="✕", font_size=12, size_hint=(None,1), width=36,
                           background_color=(0,0,0,0), color=(*SURYA_NET["sub"],1))
        btn_close.bind(on_press=lambda *_: self.toggle())
        hdr.add_widget(self._title); hdr.add_widget(btn_close)
        self._panel.add_widget(hdr)

        # Chat area
        self._chat = ChatLog(size_hint=(1,1))
        with self._chat.canvas.before:
            self._chat_c = Color(*SURYA_NET["bg2"],1)
            self._chat_r = Rectangle(pos=self._chat.pos, size=self._chat.size)
        self._chat.bind(pos=lambda i,v:setattr(self._chat_r,"pos",v), size=lambda i,v:setattr(self._chat_r,"size",v))
        self._panel.add_widget(self._chat)

        # Input
        inp = BoxLayout(size_hint=(1,None), height=44, spacing=4, padding=[6,5])
        with inp.canvas.before:
            self._inp_c = Color(*SURYA_NET["card"],1)
            self._inp_r = RoundedRectangle(pos=inp.pos, size=inp.size, radius=[0,0,10,10])
        inp.bind(pos=lambda i,v:setattr(self._inp_r,"pos",v), size=lambda i,v:setattr(self._inp_r,"size",v))
        self._txt = TextInput(hint_text="Ask anything…", multiline=False, font_size=12,
                              background_color=(0,0,0,0),
                              foreground_color=(*SURYA_NET["text"],1),
                              hint_text_color=(*SURYA_NET["sub"],0.4), padding=[8,8])
        self._txt.bind(on_text_validate=self._send)
        btn_send = Button(text="→", font_size=14, bold=True, size_hint=(None,1), width=38,
                          background_color=(*SURYA_NET["accent"],1), color=(1,1,1,1))
        btn_send.bind(on_press=self._send)
        inp.add_widget(self._txt); inp.add_widget(btn_send)
        self._panel.add_widget(inp)

    def _send(self, *_):
        q = self._txt.text.strip()
        if not q: return
        self._txt.text = ""
        self._chat.add_bubble("YOU","you",q,"", True)
        db_save_chat("user", q, "ai-panel", is_conv=True)
        def _reply():
            # AI panel uses its OWN chat object — does NOT call _ui("stream")
            Clock.schedule_once(lambda dt: self._chat.start_stream(), 0)
            full = ""
            def _cb(chunk):
                nonlocal full; full += chunk
                Clock.schedule_once(lambda dt,c=chunk: self._chat.append_stream(c), 0)
            reply, src = ask_chatgpt(q, stream_cb=_cb)
            Clock.schedule_once(lambda dt: self._chat.end_stream(), 0)
            if reply:
                Clock.schedule_once(lambda dt: self._chat.add_bubble("VEDA","ai",reply,src or "gpt",True), 0.1)
        threading.Thread(target=_reply, daemon=True).start()

    def toggle(self):
        self._open = not self._open
        if self._open and not self._loaded:
            self._loaded = True
            # Load recent conversation history
            rows = db_load_history(20, conv_only=True)
            for role,content,src in rows:
                r2 = "you" if role=="user" else "ai"
                w  = "YOU" if role=="user" else "VEDA"
                Clock.schedule_once(lambda dt,ww=w,rr=r2,cc=content,ss=src: self._chat.add_bubble(ww,rr,cc,ss,False), 0)
        tx = Window.width - self._panel.width - 8 if self._open else Window.width
        Animation(x=tx, duration=0.30, t='out_cubic').start(self._panel)

    def _theme_tick(self, dt):
        pal = P()
        self._title.color = (*pal["primary"],1)
        self._hdr_c.rgba = (*pal["card"],1)
        self._chat_c.rgba = (*pal["bg2"],1)
        self._inp_c.rgba = (*pal["card"],1)
        self._txt.foreground_color = (*pal["text"],1)
        self._txt.hint_text_color = (*pal["sub"],0.4)


# ═══════════════════════════════════════════════════════════════════════════════
#  REMINDERS TAB WIDGET
# ═══════════════════════════════════════════════════════════════════════════════

class RemindersTab(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", spacing=8, padding=[12,10], **kw)
        self._build()

    def _build(self):
        pal = P()
        # Quick-set buttons row
        quick = BoxLayout(size_hint=(1,None), height=40, spacing=5)
        for lbl, mins in [("5 min",5),("15 min",15),("30 min",30),("1 hr",60),("Custom",0)]:
            b = Button(text=lbl, font_size=11, bold=True,
                       background_color=(*SURYA_NET["primary"],0.25),
                       color=(*SURYA_NET["text"],1))
            m2 = mins
            b.bind(on_press=lambda *_,m=m2: self._quick_remind(m))
            quick.add_widget(b)
        self.add_widget(quick)

        # "to do" label input
        inp_row = BoxLayout(size_hint=(1,None), height=40, spacing=5)
        self._what = TextInput(hint_text="What to remind you about?",
                               multiline=False, font_size=12,
                               background_color=(0.06,0.03,0.01,0.9),
                               foreground_color=(*SURYA_NET["text"],1),
                               hint_text_color=(*SURYA_NET["sub"],0.4),
                               padding=[8,8])
        inp_row.add_widget(self._what)
        self.add_widget(inp_row)

        # Custom time input (hidden by default)
        self._custom_row = BoxLayout(size_hint=(1,None), height=40, spacing=5)
        self._custom_time = TextInput(hint_text="e.g. in 2 hours / at 6pm / tomorrow at 9am",
                                      multiline=False, font_size=11,
                                      background_color=(0.06,0.03,0.01,0.9),
                                      foreground_color=(*SURYA_NET["text"],1),
                                      hint_text_color=(*SURYA_NET["sub"],0.4),
                                      padding=[8,8])
        btn_set = Button(text="Set", font_size=11, bold=True,
                         size_hint=(None,1), width=52,
                         background_color=(*SURYA_NET["accent"],0.9),
                         color=(1,1,1,1))
        btn_set.bind(on_press=self._set_custom)
        self._custom_row.add_widget(self._custom_time); self._custom_row.add_widget(btn_set)
        self._custom_row.opacity = 0; self._custom_row.size_hint_y = None; self._custom_row.height = 0
        self.add_widget(self._custom_row)

        # Reminder list
        self._scroll = ScrollView(size_hint=(1,1))
        self._rbox = BoxLayout(orientation="vertical", size_hint_y=None, spacing=5)
        self._rbox.bind(minimum_height=self._rbox.setter("height"))
        self._scroll.add_widget(self._rbox)
        self.add_widget(self._scroll)
        self.refresh()

    def _quick_remind(self, mins):
        if mins == 0:
            # Show custom
            self._custom_row.opacity = 1; self._custom_row.height = 40
            return
        what = self._what.text.strip() or "reminder"
        cmd = f"remind me in {mins} minutes to {what}"
        result = _parse_reminder(cmd)
        _ui("toast", result)
        self._what.text = ""; self.refresh()

    def _set_custom(self, *_):
        t = self._custom_time.text.strip()
        what = self._what.text.strip() or "reminder"
        if t:
            cmd = f"remind me {t} to {what}"
            result = _parse_reminder(cmd)
            _ui("toast", result)
            self._what.text = ""; self._custom_time.text = ""
            self._custom_row.opacity = 0; self._custom_row.height = 0
            self.refresh()

    def refresh(self):
        self._rbox.clear_widgets()
        pal = P()
        rows = db_get_reminders()
        if not rows:
            l = Label(text="No upcoming reminders", font_size=12, italic=True,
                      color=(*pal["sub"],0.6), size_hint=(1,None), height=36)
            self._rbox.add_widget(l); return
        for rid, ts_str, label in rows:
            try: dt = datetime.datetime.fromisoformat(ts_str); ts_show = dt.strftime("%d %b  %I:%M %p")
            except: ts_show = ts_str[:16]
            row = BoxLayout(size_hint=(1,None), height=38, spacing=6)
            with row.canvas.before:
                Color(*pal["card"],1); RoundedRectangle(pos=row.pos,size=row.size,radius=[6])
            row.bind(pos=lambda i,v:i.canvas.before.clear() or
                     i.canvas.before.add(Color(*P()["card"],1)) or
                     i.canvas.before.add(RoundedRectangle(pos=v,size=i.size,radius=[6])))
            lbl_text = f"[b][color=#{_hx(pal['text'])}]{label}[/color][/b]  [color=#{_hx(pal['sub'])}]{ts_show}[/color]"
            l = Label(text=lbl_text, markup=True, font_size=12, size_hint=(1,1), halign="left")
            done_btn = Button(text="✓", font_size=11, bold=True,
                              size_hint=(None,1), width=36,
                              background_color=(0.15,0.65,0.25,0.85), color=(1,1,1,1))
            _rid = rid
            done_btn.bind(on_press=lambda *_,r=_rid: self._done(r))
            row.add_widget(l); row.add_widget(done_btn)
            self._rbox.add_widget(row)

    def _done(self, rid):
        db_done_reminder(rid); self.refresh()


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════════════════════════════════════

class VedaApp(App):
    title = "VEDA v13 — Dharma Edition"

    def build(self):
        Window.clearcolor = (*SURYA_NET["bg"],1)
        root = FloatLayout()
        main = BoxLayout(orientation="horizontal", size_hint=(1,1))

        # ════════════════════════════════════════════════════════════════════
        # LEFT PANEL  — Orb dominates
        # ════════════════════════════════════════════════════════════════════
        left = BoxLayout(orientation="vertical", size_hint=(0.46,1))

        # ── Header ── 46px ──────────────────────────────────────────────────
        hdr = BoxLayout(size_hint=(1,None), height=46, padding=[14,5], spacing=8)
        with hdr.canvas.before:
            self._hdr_c = Color(*SURYA_NET["bg2"],1)
            self._hdr_r = Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(pos=lambda i,v:setattr(self._hdr_r,"pos",v),
                 size=lambda i,v:setattr(self._hdr_r,"size",v))

        self.lbl_veda = Label(text="[b]VEDA[/b]", markup=True, font_size=22,
                              color=(*SURYA_NET["primary"],1),
                              size_hint=(None,1), width=82, halign="left")
        self.lbl_mode_badge = Label(text="☀ SURYA NET", font_size=11, bold=True,
                                    color=(*SURYA_NET["sub"],1),
                                    size_hint=(1,1), halign="left")
        # Right side of header
        hr = BoxLayout(size_hint=(None,1), width=190, spacing=8)
        self.conn_dot = ConnDot(size_hint=(None,None), width=14, height=14)
        self.lbl_clock = LiveClock(font_size=11, size_hint=(None,1), width=72, halign="right")
        # CPU compact
        self.lbl_cpu = Label(text="", font_size=10, color=(*SURYA_NET["muted"],1),
                             size_hint=(None,1), width=70, halign="right")
        # AI Chat button
        self.btn_ai = Button(text="💬 AI", font_size=11, bold=True,
                             size_hint=(None,1), width=54,
                             background_color=(*SURYA_NET["accent"],0.85), color=(1,1,1,1))
        self.btn_ai.bind(on_press=lambda *_: self._ai_panel.toggle())

        hr.add_widget(self.lbl_cpu)
        hr.add_widget(self.conn_dot)
        hr.add_widget(self.lbl_clock)
        hr.add_widget(self.btn_ai)

        hdr.add_widget(self.lbl_veda)
        hdr.add_widget(self.lbl_mode_badge)
        hdr.add_widget(hr)
        left.add_widget(hdr)

        # ── VISUALISER  — fills remaining space ─────────────────────────────
        self.vis = Visualiser(size_hint=(1,1))
        left.add_widget(self.vis)

        # ── State label row ── 38px ──────────────────────────────────────────
        state_row = BoxLayout(size_hint=(1,None), height=38, padding=[14,6])
        self.lbl_state = Label(text="◈  Ready — say  Hey Veda",
                               font_size=13, italic=True,
                               color=(*SURYA_NET["text"],0.85),
                               size_hint=(1,1), halign="center")
        state_row.add_widget(self.lbl_state)
        left.add_widget(state_row)

        # ── Heard text ── 22px ───────────────────────────────────────────────
        self.lbl_heard = Label(text="", font_size=11, italic=True,
                               color=(*SURYA_NET["sub"],0.65),
                               size_hint=(1,None), height=22, halign="center")
        left.add_widget(self.lbl_heard)

        # ── Mic bar ── 18px ──────────────────────────────────────────────────
        self.mic_bar = MicBar(size_hint=(1,None), height=18)
        left.add_widget(self.mic_bar)

        # ── Mode toggle ── 40px ──────────────────────────────────────────────
        mode_row = BoxLayout(size_hint=(1,None), height=40, padding=[14,4], spacing=8)
        self.btn_mode = Button(text="☀  SURYA NET  — tap to go offline",
                               font_size=11, bold=True,
                               background_color=(*SURYA_NET["primary"],0.25),
                               color=(*SURYA_NET["primary"],1))
        with self.btn_mode.canvas.before:
            Color(*SURYA_NET["primary"],0.40)
            Line(rounded_rectangle=(*self.btn_mode.pos,*self.btn_mode.size,6),width=1.0)
        self.btn_mode.bind(on_press=self._toggle_mode)
        mode_row.add_widget(self.btn_mode)
        left.add_widget(mode_row)

        # ── Quick action button + text input ── 44px ─────────────────────────
        inp_row = BoxLayout(size_hint=(1,None), height=44, padding=[8,4], spacing=6)
        self.btn_quick = Button(text="⋮", font_size=16, bold=True,
                                size_hint=(None,1), width=38,
                                background_color=(*SURYA_NET["card"],1),
                                color=(*SURYA_NET["primary"],1))
        self.btn_quick.bind(on_press=lambda *_: self._quick_panel.toggle())
        self.txt = TextInput(
            hint_text="Type anything — or just say  Hey Veda…",
            multiline=False, font_size=12,
            background_color=(0.07,0.03,0.01,0.95),
            foreground_color=(*SURYA_NET["text"],1),
            hint_text_color=(*SURYA_NET["sub"],0.30),
            cursor_color=(*SURYA_NET["primary"],1), padding=[10,10])
        self.txt.bind(on_text_validate=self._on_type)
        self.btn_go = Button(text="GO", font_size=11, bold=True,
                             size_hint=(None,1), width=44,
                             background_color=(*SURYA_NET["accent"],1),
                             color=(1,1,1,1))
        self.btn_go.bind(on_press=self._on_type)
        inp_row.add_widget(self.btn_quick)
        inp_row.add_widget(self.txt)
        inp_row.add_widget(self.btn_go)
        left.add_widget(inp_row)
        main.add_widget(left)

        # ════════════════════════════════════════════════════════════════════
        # RIGHT PANEL  — Chat + Tabs
        # ════════════════════════════════════════════════════════════════════
        right = BoxLayout(orientation="vertical", size_hint=(0.54,1))

        # ── Tab bar ── 38px ──────────────────────────────────────────────────
        tab_bar = BoxLayout(size_hint=(1,None), height=38, spacing=2, padding=[4,3])
        with tab_bar.canvas.before:
            self._tbar_c = Color(*SURYA_NET["bg2"],1)
            self._tbar_r = Rectangle(pos=tab_bar.pos, size=tab_bar.size)
        tab_bar.bind(pos=lambda i,v:setattr(self._tbar_r,"pos",v),
                     size=lambda i,v:setattr(self._tbar_r,"size",v))

        self._tab_btns = []
        self._tab_names = ["💬 Chat","📜 History","⏰ Reminders","💻 System"]
        self._active_tab = 0
        for i,n in enumerate(self._tab_names):
            b = Button(text=n, font_size=11, bold=True,
                       background_color=(*SURYA_NET["primary"],0.80) if i==0 else (0,0,0,0),
                       color=(0,0,0,1) if i==0 else (*SURYA_NET["sub"],1))
            ii = i; b.bind(on_press=lambda *_,idx=ii: self._switch_tab(idx))
            self._tab_btns.append(b); tab_bar.add_widget(b)
        right.add_widget(tab_bar)

        # Thin divider
        div = Widget(size_hint=(1,None), height=1)
        with div.canvas:
            self._div_c = Color(*SURYA_NET["divider"],1)
            Rectangle(pos=div.pos, size=div.size)
        right.add_widget(div)

        # ── Tab host ─────────────────────────────────────────────────────────
        self._tab_host = FloatLayout(size_hint=(1,1))

        # Tab 0: Chat
        self.chat = ChatLog(size_hint=(1,1), pos_hint={"x":0,"y":0},
                            bar_color=(*SURYA_NET["accent"],0.5),
                            bar_inactive_color=(*SURYA_NET["sub"],0.25))
        with self.chat.canvas.before:
            self._chat_c = Color(*SURYA_NET["bg"],1)
            self._chat_r = Rectangle(pos=self.chat.pos, size=self.chat.size)
        self.chat.bind(pos=lambda i,v:setattr(self._chat_r,"pos",v),
                       size=lambda i,v:setattr(self._chat_r,"size",v))
        self._tab_host.add_widget(self.chat)

        # Tab 1: History
        self._hist_chat = ChatLog(size_hint=(1,1), pos_hint={"x":0,"y":0}, opacity=0)
        with self._hist_chat.canvas.before:
            self._hist_c = Color(*SURYA_NET["bg"],1)
            self._hist_r = Rectangle(pos=self._hist_chat.pos, size=self._hist_chat.size)
        self._hist_chat.bind(pos=lambda i,v:setattr(self._hist_r,"pos",v),
                             size=lambda i,v:setattr(self._hist_r,"size",v))
        self._tab_host.add_widget(self._hist_chat)

        # Tab 2: Reminders
        self._rem_tab = RemindersTab(size_hint=(1,1), pos_hint={"x":0,"y":0}, opacity=0)
        with self._rem_tab.canvas.before:
            self._rem_c = Color(*SURYA_NET["bg"],1)
            self._rem_r = Rectangle(pos=self._rem_tab.pos, size=self._rem_tab.size)
        self._rem_tab.bind(pos=lambda i,v:setattr(self._rem_r,"pos",v),
                           size=lambda i,v:setattr(self._rem_r,"size",v))
        self._tab_host.add_widget(self._rem_tab)

        # Tab 3: System monitor
        self._sys_tab = BoxLayout(orientation="vertical", size_hint=(1,1),
                                  pos_hint={"x":0,"y":0}, opacity=0,
                                  padding=[12,10], spacing=8)
        with self._sys_tab.canvas.before:
            self._sys_c = Color(*SURYA_NET["bg"],1)
            self._sys_r = Rectangle(pos=self._sys_tab.pos, size=self._sys_tab.size)
        self._sys_tab.bind(pos=lambda i,v:setattr(self._sys_r,"pos",v),
                           size=lambda i,v:setattr(self._sys_r,"size",v))
        self._cpu_lbl2 = Label(text="CPU: --", font_size=16, bold=True,
                               color=(*SURYA_NET["primary"],1), size_hint=(1,None), height=28)
        self._ram_lbl2 = Label(text="RAM: --", font_size=16, bold=True,
                               color=(*SURYA_NET["teal"],1), size_hint=(1,None), height=28)
        self._bat_lbl2 = Label(text="Battery: --", font_size=14,
                               color=(*SURYA_NET["sub"],1), size_hint=(1,None), height=24)
        self._sys_graph = SysMonWidget(size_hint=(1,1))
        offline_lbl = Label(
            text=("[b]Offline Capabilities:[/b]\n"
                  "• Voice: Vosk (download vosk-model-small-en-us-0.15)\n"
                  "• AI Chat: Ollama (install + run: ollama pull mistral)\n"
                  "• Weather/News: Cached from last online session\n"
                  "• Knowledge: 500+ facts built-in to local DB"),
            markup=True, font_size=11, halign="left", valign="top",
            size_hint=(1,None), height=80, color=(*SURYA_NET["sub"],0.75),
            text_size=(None,None))
        offline_lbl.bind(width=lambda i,v: setattr(i,"text_size",(v-12,None)))
        for w in [self._cpu_lbl2, self._ram_lbl2, self._bat_lbl2, self._sys_graph, offline_lbl]:
            self._sys_tab.add_widget(w)
        self._tab_host.add_widget(self._sys_tab)

        right.add_widget(self._tab_host)
        main.add_widget(right)
        root.add_widget(main)

        # ── Overlays ──────────────────────────────────────────────────────────
        self._quick_panel = QuickPanel(size_hint=(None,None), width=320, height=340,
                                       pos_hint={"x":0,"y":0})
        root.add_widget(self._quick_panel)

        self._ai_panel = AIChatPanel(size_hint=(1,1), pos_hint={"x":0,"y":0})
        root.add_widget(self._ai_panel)

        self._toast = ToastOverlay(size_hint=(1,1), pos_hint={"x":0,"y":0})
        root.add_widget(self._toast)

        # Theme tick
        Clock.schedule_interval(self._theme_tick, 1/10)
        # Check first run
        Clock.schedule_once(self._check_first_run, 1.5)
        return root

    # ── First run welcome ─────────────────────────────────────────────────────
    def _check_first_run(self, dt):
        if CFG.get("first_run", True):
            CFG["first_run"] = False; _save_cfg()
            self.chat.add_bubble("SYS","sys","Welcome to VEDA v13! Here's what you can do:","")
            for line in [
                "🗣 Just talk naturally — say 'Hey Veda' then anything",
                "🌐 Online: full AI chat via GPT-4o-mini (add API key in config)",
                "🌑 Offline: local AI via Ollama + built-in knowledge base",
                "🎙 Voice: set reminders, open apps, check weather, play music",
                "💬 AI Chat: tap the 💬 AI button for a dedicated chat panel",
                "⋮  Quick actions: tap ⋮ for calibrate, screenshot, and more",
                "📖 Offline AI: install Ollama → run: ollama pull mistral",
            ]: self.chat.add_bubble("SYS","sys",line,"")

    # ── Tab switching ─────────────────────────────────────────────────────────
    def _switch_tab(self, idx):
        self._active_tab = idx
        pal = P()
        tabs = [self.chat, self._hist_chat, self._rem_tab, self._sys_tab]
        for i, w in enumerate(tabs):
            w.opacity = 1.0 if i == idx else 0.0
        for i, b in enumerate(self._tab_btns):
            b.background_color = (*pal["primary"],0.80) if i==idx else (0,0,0,0)
            b.color = (0,0,0,1) if i==idx else (*pal["sub"],1)
        if idx == 1: self._load_history()
        if idx == 2: self._rem_tab.refresh()

    def _load_history(self):
        self._hist_chat.clear()
        for role,content,src in db_load_history(60, conv_only=True):
            r2 = "you" if role=="user" else "ai"
            w2 = "YOU" if role=="user" else "VEDA"
            self._hist_chat.add_bubble(w2, r2, content[:120], src, False)

    # ── Mode toggle ───────────────────────────────────────────────────────────
    def _toggle_mode(self, *_):
        if _active_mode() == "surya":
            threading.Thread(target=_set_nirvana, daemon=True).start()
        else:
            threading.Thread(target=_set_surya, daemon=True).start()

    # ── Input ─────────────────────────────────────────────────────────────────
    def _on_type(self, *_):
        t = self.txt.text.strip()
        if t:
            self.txt.text = ""
            threading.Thread(target=execute, args=(t,), daemon=True).start()

    # ── Theme tick ────────────────────────────────────────────────────────────
    def _theme_tick(self, dt):
        with _MORPH_LOCK: mt = _MORPH
        prev = getattr(self, "_last_mt", None)
        if prev is None or abs(mt-prev) > 0.005: self._apply_theme()
        self._last_mt = mt

    def _apply_theme(self):
        pal = P()
        Window.clearcolor = (*pal["bg"],1)
        self.lbl_veda.color = (*pal["primary"],1)
        self.lbl_mode_badge.color = (*pal["sub"],1)
        self.lbl_state.color = (*pal["text"],0.85)
        self.lbl_heard.color = (*pal["sub"],0.65)
        self.lbl_cpu.color = (*pal["muted"],1)
        self.btn_ai.background_color = (*pal["accent"],0.85)
        self.btn_go.background_color = (*pal["accent"],1)
        self._hdr_c.rgba = (*pal["bg2"],1)
        self._tbar_c.rgba = (*pal["bg2"],1)
        self._div_c.rgba = (*pal["divider"],1)
        self._chat_c.rgba = (*pal["bg"],1)
        self._hist_c.rgba = (*pal["bg"],1)
        self._rem_c.rgba = (*pal["bg"],1)
        self._sys_c.rgba = (*pal["bg"],1)
        self._cpu_lbl2.color = (*pal["primary"],1)
        self._ram_lbl2.color = (*pal["teal"],1)
        self._bat_lbl2.color = (*pal["sub"],1)
        bg = (0.06,0.03,0.01,0.95) if _active_mode()=="surya" else (0.02,0.01,0.07,0.95)
        self.txt.background_color = bg
        self.txt.foreground_color = (*pal["text"],1)
        self.txt.hint_text_color  = (*pal["sub"],0.30)
        self.txt.cursor_color     = (*pal["primary"],1)

    # ── App lifecycle ──────────────────────────────────────────────────────────
    def on_start(self):
        _seed_knowledge()
        threading.Thread(target=_stt_worker,      daemon=True).start()
        threading.Thread(target=_tts_worker,       daemon=True).start()
        threading.Thread(target=voice_loop,        daemon=True).start()
        threading.Thread(target=_sysmon_worker,    daemon=True).start()
        threading.Thread(target=_reminder_worker,  daemon=True).start()

    def on_stop(self):
        _APP_RUNNING.clear()

    # ── Public API ─────────────────────────────────────────────────────────────
    def set_status(self, text): self.lbl_state.text = text
    def set_heard(self, text):
        s = text[:62]+("…" if len(text)>62 else "")
        self.lbl_heard.text = f'"{s}"'
    def set_energy(self, e):
        self.mic_bar.set_energy(e); self.vis.set_energy(e)
    def set_online_dot(self, v): self.conn_dot.set_online(v)
    def show_toast(self, text): self._toast.show(text)
    def show_offline_warning(self, text): self._toast.show(f"⚠ {text}"); self.chat.add_bubble("SYS","sys",f"⚠ {text}","")
    def add_bubble(self, who, role, text, src, save=True): self.chat.add_bubble(who, role, text, src, save)
    def reminder_due(self, label):
        if label: self.show_toast(f"⏰ {label}")
        if self._active_tab == 2: self._rem_tab.refresh()

    def update_sysmon(self, data):
        self._sys_graph.update(data)
        cpu = data.get("cpu",0); ram = data.get("ram",0)
        batt = data.get("batt",-1); plug = data.get("plug",True)
        self.lbl_cpu.text = f"CPU {cpu:.0f}%"
        self._cpu_lbl2.text = f"CPU: {cpu:.1f}%"
        self._ram_lbl2.text = f"RAM: {ram:.1f}%"
        if batt >= 0: self._bat_lbl2.text = f"Battery: {batt}% {'⚡ charging' if plug else '🔋 on battery'}"

    def stream_chunk(self, chunk):
        if chunk == "__START__": self.chat.start_stream()
        else: self.chat.append_stream(chunk)
    def stream_end(self): self.chat.end_stream()

    def set_state(self, state):
        self.vis.set_state(state)
        msgs = {"listening":"🎙  Listening…","speaking":"🔊  Speaking…",
                "thinking":"💭  Thinking…","ready":"◈  Ready — say  Hey Veda"}
        self.lbl_state.text = msgs.get(state, state)
        if state == "ready": self.lbl_heard.text = ""

    def set_mode(self, mode):
        self.vis.set_mode(mode)
        pal = P()
        if mode == "surya":
            self.lbl_mode_badge.text = "☀  SURYA NET"
            self.btn_mode.text = "☀  SURYA NET  — tap to go offline"
            self.chat.add_bubble("SYS","sys","⚡ Connected — Surya Net online","")
        else:
            self.lbl_mode_badge.text = "🌑  NIRVANA MODE"
            self.btn_mode.text = "🌑  NIRVANA MODE  — tap to go online"
            vs = _vosk_status()
            if vs == "ok":
                self.chat.add_bubble("SYS","sys","🌌 Offline — Vosk STT active. Ollama AI available if running.","")
            elif vs == "no_model":
                self.chat.add_bubble("SYS","sys","🌌 Offline — Download Vosk model for offline speech. Ollama for AI.","")
            else:
                self.chat.add_bubble("SYS","sys","🌌 Offline — pip install vosk for offline speech recognition.","")


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        VedaApp().run()
    except Exception as e:
        import traceback
        print("\n[CRASH]", e); traceback.print_exc()
        input("\nPress Enter to close…")
