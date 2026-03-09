"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   V E D A  v12  ─  DHARMA CYBER EDITION                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  MODES:                                                                      ║
║    ☀  SURYA NET    — Online / Connected / Solar Grid                        ║
║    🌑  NIRVANA MODE — Offline / Silent / Local                               ║
║    ◈   AKASHA DARK  — Deep Offline / Void / No fallback                     ║
║                                                                              ║
║  NEW FEATURES v12:                                                           ║
║    ① AI Chat Panel  — floating slide-in + dedicated tab + inline bubbles    ║
║       • Typewriter streaming effect for AI replies                           ║
║       • All 4 chat styles in one unified panel                               ║
║    ② Conversation DB — full chat history saved to SQLite                    ║
║    ③ Voice Personality — Calm / Energetic / Guru (Wise)                     ║
║    ④ Hindi+English    — bilingual responses + auto-detect                   ║
║    ⑤ System Monitor  — CPU / RAM / Battery live widget                      ║
║    ⑥ Media Controls  — Spotify play/pause/skip via voice                    ║
║    ⑦ Wake Word Trainer — record & test custom trigger words                 ║
║    ⑧ Screenshot+AI   — capture screen → describe with vision API            ║
║    ⑨ Daily Briefing  — morning greeting: weather + news + calendar          ║
║    ⑩ Reminders+Alarm — persistent reminder system with desktop toasts       ║
║                                                                              ║
║  RELIABILITY FIXES:                                                          ║
║    • Dual STT pipeline: Google primary + Vosk fallback + retry logic        ║
║    • Confidence threshold filtering                                           ║
║    • Command echo-back confirmation                                           ║
║    • Noise gate: ambient calibration stored & reused                        ║
║    • Thread-safe command queue prevents dropped commands                    ║
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
Config.set("graphics","width",  "1400")
Config.set("graphics","height", "860")

# ── 3. Stdlib ─────────────────────────────────────────────────────────────────
import threading, queue, math, datetime, webbrowser, base64
import random, time, socket, json, sqlite3, subprocess, re, getpass, io
from collections import deque

# ── 4. Third-party (graceful degradation) ────────────────────────────────────
import speech_recognition as sr

try:    import requests;                            _REQ      = True
except: _REQ = False

try:    from openai import OpenAI;                  _OPENAI   = True
except: _OPENAI = False

try:    import pyautogui; pyautogui.FAILSAFE=True;  _PYAUTOGUI= True
except: _PYAUTOGUI = False

try:    import psutil;                              _PSUTIL   = True
except: _PSUTIL = False

try:    import PIL.ImageGrab as _IG;                _PIL      = True
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
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.graphics        import (Color, Line, Ellipse, Rectangle,
                                   RoundedRectangle, Triangle)
from kivy.clock           import Clock
from kivy.core.window     import Window
from kivy.animation       import Animation


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG — user settings file
# ═══════════════════════════════════════════════════════════════════════════════

_CFG_FILE = "veda_config.json"
_DEFAULT_CFG = {
    "openai_key"       : "YOUR_OPENAI_API_KEY",
    "personality"      : "energetic",   # calm | energetic | guru
    "language"         : "en",          # en | hi | auto
    "wake_words"       : ["hey veda","ok veda","veda"],
    "custom_wake"      : [],
    "noise_threshold"  : 300,
    "daily_briefing"   : True,
    "briefing_time"    : "08:00",
    "city"             : "Hyderabad",
    "mode"             : "auto",
}

def _load_cfg():
    if os.path.isfile(_CFG_FILE):
        try:
            with open(_CFG_FILE) as f: d=json.load(f)
            for k,v in _DEFAULT_CFG.items():
                d.setdefault(k,v)
            return d
        except: pass
    return dict(_DEFAULT_CFG)

def _save_cfg(cfg):
    try:
        with open(_CFG_FILE,"w") as f: json.dump(cfg,f,indent=2)
    except: pass

CFG = _load_cfg()
OPENAI_API_KEY = CFG["openai_key"]


# ═══════════════════════════════════════════════════════════════════════════════
#  PALETTES  — SURYA NET / NIRVANA MODE
# ═══════════════════════════════════════════════════════════════════════════════

SURYA_NET = dict(
    bg        = (0.03, 0.02, 0.00),
    bg2       = (0.07, 0.04, 0.01),
    card      = (0.10, 0.05, 0.01),
    primary   = (1.00, 0.82, 0.10),   # Kanaka gold
    accent    = (1.00, 0.32, 0.04),   # Sindoor red
    glow      = (1.00, 0.56, 0.00),   # Agni orange
    teal      = (0.00, 0.92, 0.78),   # Neon teal accent
    divider   = (0.80, 0.20, 0.00),
    text      = (1.00, 0.94, 0.68),
    sub       = (0.78, 0.52, 0.18),
    muted     = (0.35, 0.22, 0.08),
    you_bg    = (0.18, 0.08, 0.01),
    you_col   = (1.00, 0.76, 0.18),
    ai_bg     = (0.08, 0.04, 0.01),
    ai_col    = (1.00, 0.94, 0.68),
    sys_col   = (0.50, 0.32, 0.08),
    yantra    = (1.00, 0.82, 0.10),
    lotus     = (1.00, 0.34, 0.04),
    chakra    = (1.00, 0.66, 0.00),
    grid      = (1.00, 0.82, 0.10),
    mode_name = "☀  SURYA NET",
    mode_sub  = "Connected · Solar Grid Online",
)

NIRVANA_MODE = dict(
    bg        = (0.01, 0.01, 0.07),
    bg2       = (0.02, 0.02, 0.11),
    card      = (0.04, 0.04, 0.16),
    primary   = (0.60, 0.18, 1.00),   # Cosmic violet
    accent    = (0.00, 0.88, 0.84),   # Starlight cyan
    glow      = (0.38, 0.04, 0.82),   # Deep indigo
    teal      = (0.00, 0.88, 0.84),
    divider   = (0.00, 0.75, 0.75),
    text      = (0.82, 0.68, 1.00),
    sub       = (0.46, 0.28, 0.76),
    muted     = (0.22, 0.14, 0.40),
    you_bg    = (0.07, 0.03, 0.17),
    you_col   = (0.52, 0.18, 0.94),
    ai_bg     = (0.02, 0.06, 0.14),
    ai_col    = (0.00, 0.86, 0.82),
    sys_col   = (0.30, 0.16, 0.50),
    yantra    = (0.60, 0.18, 1.00),
    lotus     = (0.00, 0.88, 0.84),
    chakra    = (0.50, 0.10, 0.92),
    grid      = (0.60, 0.18, 1.00),
    mode_name = "🌑  NIRVANA MODE",
    mode_sub  = "Offline · Silent Void",
)

_MORPH = 0.0; _MORPH_TGT = 0.0; _MORPH_LOCK = threading.Lock()

def _lerp(a,b,t): return a+(b-a)*t
def _lc(ca,cb,t): return tuple(_lerp(ca[i],cb[i],t) for i in range(3))

def P():
    with _MORPH_LOCK: t=_MORPH
    return {k:(_lc(SURYA_NET[k],NIRVANA_MODE[k],t)
               if isinstance(SURYA_NET[k],tuple)
               else (SURYA_NET[k] if t<0.5 else NIRVANA_MODE[k]))
            for k in SURYA_NET}

def _hsv(h,s,v):
    h%=1.0;i=int(h*6);f=h*6-i
    p=v*(1-s);q=v*(1-f*s);tz=v*(1-(1-f)*s)
    return [(v,tz,p),(q,v,p),(p,v,tz),(p,q,v),(tz,p,v),(v,p,q)][i%6]

def _tick_morph(dt):
    global _MORPH
    with _MORPH_LOCK:
        d=_MORPH_TGT-_MORPH
        if abs(d)>0.0008: _MORPH+=d*min(1.0,dt*2.8)

Clock.schedule_interval(_tick_morph,1/60)


# ═══════════════════════════════════════════════════════════════════════════════
#  DATABASE  — memory + chat history + reminders
# ═══════════════════════════════════════════════════════════════════════════════

_db  = sqlite3.connect("veda_v12.db",check_same_thread=False)
_dbl = threading.Lock()

with _dbl:
    _db.executescript("""
        CREATE TABLE IF NOT EXISTS memory(
            phrase TEXT PRIMARY KEY, response TEXT);
        CREATE TABLE IF NOT EXISTS chat_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, role TEXT, content TEXT, source TEXT);
        CREATE TABLE IF NOT EXISTS reminders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, label TEXT, done INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS wake_words(
            word TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS noise_cal(
            id INTEGER PRIMARY KEY, threshold REAL);
    """)
    _db.commit()

def db_set(k,v):
    with _dbl: _db.execute("INSERT OR REPLACE INTO memory VALUES(?,?)",(k.strip().lower(),v.strip())); _db.commit()
def db_get(k):
    with _dbl: r=_db.execute("SELECT response FROM memory WHERE phrase=?",(k.strip().lower(),)).fetchone()
    return r[0] if r else None
def db_del(k):
    with _dbl: _db.execute("DELETE FROM memory WHERE phrase=?",(k.strip().lower(),)); _db.commit()
def db_clear():
    with _dbl: _db.execute("DELETE FROM memory"); _db.commit()

def db_save_chat(role,content,source=""):
    ts=datetime.datetime.now().isoformat()
    with _dbl: _db.execute("INSERT INTO chat_history(ts,role,content,source) VALUES(?,?,?,?)",(ts,role,content,source)); _db.commit()

def db_load_history(limit=40):
    with _dbl: rows=_db.execute("SELECT role,content,source FROM chat_history ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    return list(reversed(rows))

def db_save_reminder(ts,label):
    with _dbl: _db.execute("INSERT INTO reminders(ts,label) VALUES(?,?)",(ts,label)); _db.commit()

def db_get_reminders():
    with _dbl: rows=_db.execute("SELECT id,ts,label FROM reminders WHERE done=0").fetchall()
    return rows

def db_done_reminder(rid):
    with _dbl: _db.execute("UPDATE reminders SET done=1 WHERE id=?",(rid,)); _db.commit()

def db_save_noise(thr):
    with _dbl: _db.execute("INSERT OR REPLACE INTO noise_cal(id,threshold) VALUES(1,?)",(thr,)); _db.commit()

def db_load_noise():
    with _dbl: r=_db.execute("SELECT threshold FROM noise_cal WHERE id=1").fetchone()
    return r[0] if r else None

def db_save_wake(word):
    with _dbl: _db.execute("INSERT OR IGNORE INTO wake_words(word) VALUES(?)",(word.lower().strip(),)); _db.commit()

def db_load_wakes():
    with _dbl: rows=_db.execute("SELECT word FROM wake_words").fetchall()
    return [r[0] for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
#  PERSONALITY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

_PERSONALITY_PROMPTS = {
    "calm": (
        "You are VEDA, a calm and composed AI assistant. Speak clearly and peacefully. "
        "Respond in under 260 characters. Be direct and reassuring."
    ),
    "energetic": (
        "You are VEDA, an energetic and enthusiastic AI assistant. Be quick, sharp, and upbeat. "
        "Respond in under 260 characters. Keep it punchy and helpful."
    ),
    "guru": (
        "You are VEDA, a wise AI assistant inspired by ancient Indian sages. "
        "Blend practical answers with subtle wisdom. Respond in under 260 characters."
    ),
}

def _get_system_prompt():
    p = CFG.get("personality","energetic")
    lang = CFG.get("language","en")
    base = _PERSONALITY_PROMPTS.get(p, _PERSONALITY_PROMPTS["energetic"])
    if lang == "hi":
        base += " Respond primarily in Hindi (Devanagari or Roman Hindi)."
    elif lang == "auto":
        base += " Detect the user's language and respond in the same language."
    return base


# ═══════════════════════════════════════════════════════════════════════════════
#  MODE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

_MODE      = CFG.get("mode","auto")
_MODE_LOCK = threading.Lock()
_CONV_CTX  = deque(maxlen=12)
_CTX_LOCK  = threading.Lock()

def _ping():
    try:
        socket.setdefaulttimeout(2)
        socket.socket(socket.AF_INET,socket.SOCK_STREAM).connect(("8.8.8.8",53))
        return True
    except: return False

def _active_mode():
    with _MODE_LOCK: m=_MODE
    if m=="surya":   return "surya"
    if m=="nirvana": return "nirvana"
    return "surya" if _ping() else "nirvana"

def _set_surya():
    global _MODE,_MORPH_TGT
    if not _ping():
        speak("No internet connection. Staying in Nirvana Mode.",priority=1)
        with _MODE_LOCK: _MODE="nirvana"
        _MORPH_TGT=1.0; _ui("mode","nirvana"); return
    with _MODE_LOCK: _MODE="surya"
    _MORPH_TGT=0.0; _ui("mode","surya")
    speak("Surya Net activated. Now online!")

def _set_nirvana():
    global _MODE,_MORPH_TGT
    with _MODE_LOCK: _MODE="nirvana"
    _MORPH_TGT=1.0; _ui("mode","nirvana")
    speak("Nirvana Mode. Running offline.")


# ═══════════════════════════════════════════════════════════════════════════════
#  CHATGPT  — streaming typewriter + vision
# ═══════════════════════════════════════════════════════════════════════════════

def ask_chatgpt(prompt, stream_cb=None):
    """Returns (full_text, source). stream_cb(chunk) called per token if provided."""
    if not _OPENAI or OPENAI_API_KEY=="YOUR_OPENAI_API_KEY":
        return None, None
    try:
        client  = OpenAI(api_key=OPENAI_API_KEY)
        with _CTX_LOCK:
            history=[{"role":r,"content":c} for r,c in list(_CONV_CTX)]
        history.append({"role":"user","content":prompt})

        if stream_cb:
            # Streaming path
            full=""
            resp=client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":_get_system_prompt()}]+history,
                max_tokens=260, stream=True)
            for chunk in resp:
                delta=chunk.choices[0].delta.content or ""
                if delta:
                    full+=delta
                    stream_cb(delta)
            reply=full.strip()
        else:
            resp=client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":_get_system_prompt()}]+history,
                max_tokens=260)
            reply=resp.choices[0].message.content.strip()

        with _CTX_LOCK:
            _CONV_CTX.append(("user",prompt))
            _CONV_CTX.append(("assistant",reply))
        db_save_chat("user",prompt,"user")
        db_save_chat("assistant",reply,"gpt")
        return reply,"gpt"
    except Exception as e:
        print(f"[GPT] {e}"); return None,None

def ask_chatgpt_vision(prompt, img_b64):
    """Describe a screenshot using GPT-4o vision."""
    if not _OPENAI or OPENAI_API_KEY=="YOUR_OPENAI_API_KEY":
        return "Vision requires OpenAI API key."
    try:
        client=OpenAI(api_key=OPENAI_API_KEY)
        resp=client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role":"user","content":[
                {"type":"text","text":prompt or "Describe what you see on this screen."},
                {"type":"image_url","image_url":{"url":f"data:image/png;base64,{img_b64}","detail":"low"}}
            ]}],max_tokens=300)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Vision error: {e}"

def ai_pc_control(command):
    if not _OPENAI or OPENAI_API_KEY=="YOUR_OPENAI_API_KEY":
        return {"action":"none"}
    try:
        client=OpenAI(api_key=OPENAI_API_KEY)
        resp=client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":
                'Convert voice to PC action JSON only. '
                'Actions: open_app,search_web,type_text,press_key,none\n'
                '"open notepad"→{"action":"open_app","target":"notepad"}\n'
                '"search AI"→{"action":"search_web","target":"AI"}\n'
                '"type hello"→{"action":"type_text","target":"hello"}\n'
                '"press enter"→{"action":"press_key","target":"enter"}'},
                {"role":"user","content":command}],
            max_tokens=60,temperature=0.1)
        raw=resp.choices[0].message.content.strip().replace("```json","").replace("```","")
        return json.loads(raw)
    except: return {"action":"none"}


# ═══════════════════════════════════════════════════════════════════════════════
#  WAKE WORDS  — dynamic (base + custom from DB)
# ═══════════════════════════════════════════════════════════════════════════════

def _build_wake():
    base = list(CFG.get("wake_words",["hey veda","ok veda","veda"]))
    custom = db_load_wakes() + CFG.get("custom_wake",[])
    all_w = list(dict.fromkeys(base+custom))
    patterns = [re.compile(r'\b'+re.escape(w)+r'\b',re.I) for w in all_w]
    return all_w, patterns

_WAKE_WORDS, _WAKE_PATS = _build_wake()

_CMD_W = {
    "open","play","search","find","google","launch","weather","volume","time","date",
    "calculate","news","timer","remember","forget","what","who","tell","go","switch",
    "status","joke","help","bye","set","check","activate","turn","enable","disable",
    "mute","unmute","type","press","close","exit","quit","kill","stop","start",
    "compute","shutdown","restart","reboot","cancel","remind","surya","nirvana",
    "akasha","online","offline","screenshot","describe","show","briefing","media",
    "spotify","pause","resume","skip","personality","language","train","wake",
    "remind","alarm","schedule"
}

def _has_wake(t):
    t=t.lower()
    if any(p.search(t) for p in _WAKE_PATS): return True
    for b in ("hey ","ok "):
        if t.startswith(b):
            r=t[len(b):].strip().split()
            if r and r[0] in _CMD_W: return True
    return False

def _strip_wake(t):
    t=t.lower()
    for w,p in sorted(zip(_WAKE_WORDS,_WAKE_PATS),key=lambda x:len(x[0]),reverse=True):
        if p.search(t): return p.sub("",t,count=1).strip(" ,.")
    for b in ("hey ","ok ","hi "):
        if t.startswith(b): return t[len(b):].strip()
    return t


# ═══════════════════════════════════════════════════════════════════════════════
#  VOSK
# ═══════════════════════════════════════════════════════════════════════════════

try:    from vosk import Model as _VM,KaldiRecognizer as _KR; _VOSK_LIB=True
except: _VOSK_LIB=False
_VOSK_DIR="vosk-model-small-en-us-0.15"; _vosk_rec=None; _vosk_warn=False

def _vosk():
    global _vosk_rec,_vosk_warn
    if not _VOSK_LIB: return None
    if _vosk_rec is None:
        if not os.path.isdir(_VOSK_DIR):
            if not _vosk_warn: print(f"[VOSK] Not found: {_VOSK_DIR}"); _vosk_warn=True
            return None
        try: _vosk_rec=_KR(_VM(_VOSK_DIR),16000)
        except Exception as e: print(f"[VOSK] {e}"); return None
    return _vosk_rec


# ═══════════════════════════════════════════════════════════════════════════════
#  TTS  — personality-aware speed + priority queue
# ═══════════════════════════════════════════════════════════════════════════════

class _TTSMsg:
    def __init__(self,priority,text,source="local"):
        self.priority=priority; self.text=text; self.source=source
    def __lt__(self,o): return self.priority<o.priority

_tts_q    = queue.PriorityQueue()
_speaking = threading.Event()
_RATES    = {"calm":148,"energetic":175,"guru":155}

def _tts_worker():
    engine=pyttsx3.init()
    rate=_RATES.get(CFG.get("personality","energetic"),168)
    engine.setProperty("rate",rate)
    for v in engine.getProperty("voices"):
        if "zira" in v.name.lower() or "david" in v.name.lower():
            engine.setProperty("voice",v.id); break
    while True:
        msg=_tts_q.get()
        text,src=msg.text,msg.source
        _speaking.set()
        _ui("state","speaking")
        _ui("status",text[:65]+("…" if len(text)>65 else ""))
        _ui("bubble",("VEDA","ai",text,src))
        db_save_chat("assistant",text,src)
        try: engine.say(text); engine.runAndWait()
        except Exception as e: print("[TTS]",e)
        cooldown=min(0.85,max(0.28,len(text)*0.009))
        time.sleep(cooldown)
        _speaking.clear()
        _ui("state","ready")

def speak(text:str,source:str="local",priority:int=1):
    if not text: return
    print(f"VEDA: {text}")
    _tts_q.put(_TTSMsg(priority,text,source))

def _wait_tts(max_sec=5.0):
    time.sleep(0.12)
    deadline=time.time()+max_sec
    while not _speaking.is_set() and time.time()<deadline: time.sleep(0.05)
    while _speaking.is_set(): time.sleep(0.05)
    time.sleep(0.25)


# ═══════════════════════════════════════════════════════════════════════════════
#  UI BRIDGE
# ═══════════════════════════════════════════════════════════════════════════════

def _ui(action,data=None):
    def _do(dt):
        a=App.get_running_app()
        if not a: return
        if   action=="state":    a.set_state(data)
        elif action=="status":   a.set_status(data)
        elif action=="mode":     a.set_mode(data)
        elif action=="bubble":   a.add_bubble(*data)
        elif action=="heard":    a.set_heard(data)
        elif action=="toast":    a.show_toast(data)
        elif action=="energy":   a.set_energy(data)
        elif action=="online":   a.set_online_dot(data)
        elif action=="sysmon":   a.update_sysmon(data)
        elif action=="stream":   a.stream_chunk(data)       # typewriter
        elif action=="stream_end":a.stream_end()
        elif action=="media":    a.update_media(data)
        elif action=="reminder_due": a.reminder_due(data)
    Clock.schedule_once(_do,0)


# ═══════════════════════════════════════════════════════════════════════════════
#  RELIABLE STT WORKER  — dual pipeline + retry + command queue
# ═══════════════════════════════════════════════════════════════════════════════

_stt_q      = queue.Queue()
_cmd_q      = queue.Queue()    # deduplicated command queue
_rec        = sr.Recognizer()
_rec.dynamic_energy_threshold = True
_rec.pause_threshold          = 0.65
_rec.phrase_threshold         = 0.2
_rec.non_speaking_duration    = 0.4

# Load stored noise calibration
_stored_thr = db_load_noise()
_rec.energy_threshold = _stored_thr if _stored_thr else CFG.get("noise_threshold",300)

_last_cmd   = ""          # dedup: ignore identical cmd within 2s
_last_cmd_t = 0.0

def _stt_worker():
    global _last_cmd,_last_cmd_t
    while True:
        if _speaking.is_set(): time.sleep(0.08); continue
        _ui("state","listening")
        try:
            with sr.Microphone() as src:
                # Quick ambient adjust every cycle (50ms)
                _rec.adjust_for_ambient_noise(src,0.18)
                audio=_rec.listen(src,timeout=6,phrase_time_limit=12)
                # Live energy meter
                raw=audio.get_raw_data()
                if raw:
                    samps=[abs(int.from_bytes(raw[i:i+2],"little",signed=True))
                           for i in range(0,min(len(raw),1600),2)]
                    e=min(1.0,(sum(samps)/len(samps))/6500) if samps else 0
                    _ui("energy",e)
        except sr.WaitTimeoutError: _ui("state","ready"); continue
        except Exception as e: print(f"[MIC] {e}"); time.sleep(1); continue
        if _speaking.is_set(): continue

        _ui("state","thinking")
        text=""; stt_src="local"
        mode=_active_mode()

        # PRIMARY: Google STT
        if mode=="surya":
            for attempt in range(2):          # retry once on failure
                try:
                    text=_rec.recognize_google(audio,language="en-IN").lower().strip()
                    stt_src="google"; break
                except sr.UnknownValueError: break
                except sr.RequestError:
                    if attempt==0: time.sleep(0.5)

        # FALLBACK: Vosk (offline)
        if not text:
            v=_vosk()
            if v:
                try:
                    wav=audio.get_wav_data(convert_rate=16000,convert_width=2)
                    v.AcceptWaveform(wav)
                    text=json.loads(v.Result()).get("text","").strip()
                    stt_src="vosk"
                except Exception as e: print(f"[VOSK ERR] {e}")

        # LAST RESORT: Google even in nirvana if vosk failed
        if not text and mode=="nirvana":
            try:
                text=_rec.recognize_google(audio,language="en-IN").lower().strip()
                stt_src="google-fallback"
            except: pass

        _ui("state","ready")
        if not text: continue

        # Dedup: same command within 1.8s → skip
        now=time.time()
        if text==_last_cmd and now-_last_cmd_t<1.8:
            print(f"[DEDUP] Skipped duplicate: {text}"); continue
        _last_cmd=text; _last_cmd_t=now

        print(f"[STT:{stt_src}] {text}")
        _ui("heard",text)
        _stt_q.put(text)


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM MONITOR
# ═══════════════════════════════════════════════════════════════════════════════

def _sysmon_worker():
    while True:
        if not _PSUTIL: time.sleep(5); continue
        try:
            cpu  = psutil.cpu_percent(interval=1)
            ram  = psutil.virtual_memory().percent
            batt = psutil.sensors_battery()
            bpct = int(batt.percent) if batt else -1
            plug = batt.power_plugged if batt else True
            _ui("sysmon",{"cpu":cpu,"ram":ram,"batt":bpct,"plug":plug})
        except Exception as e:
            print(f"[SYSMON] {e}")
        time.sleep(3)


# ═══════════════════════════════════════════════════════════════════════════════
#  MEDIA CONTROLS  — Spotify via subprocess (Windows)
# ═══════════════════════════════════════════════════════════════════════════════

def _spotify_cmd(action):
    """Control Spotify via keyboard shortcuts."""
    if not _PYAUTOGUI: return "pyautogui not installed."
    cmds={"play_pause":"playpause","next":"nexttrack","prev":"prevtrack",
          "volume_up":"volumeup","volume_down":"volumedown"}
    key=cmds.get(action)
    if key:
        try: pyautogui.press(key); return f"Media: {action}."
        except: return "Media key failed."
    return "Unknown media action."

def _get_spotify_info():
    """Try to get current track via tasklist."""
    try:
        out=subprocess.check_output("tasklist /FI \"IMAGENAME eq Spotify.exe\" /V",
                                    shell=True,capture_output=False,text=True,
                                    stderr=subprocess.DEVNULL)
        if "Spotify" in out:
            lines=[l for l in out.splitlines() if "Spotify.exe" in l and " - " in l]
            if lines:
                title=lines[0].split("Spotify.exe")[1].strip()
                return title.strip() or "Spotify is running."
        return "Spotify not running."
    except: return "Could not check Spotify."


# ═══════════════════════════════════════════════════════════════════════════════
#  SCREENSHOT + AI VISION
# ═══════════════════════════════════════════════════════════════════════════════

def _screenshot_describe(prompt=""):
    if not _PIL: return "Pillow not installed. Run: pip install Pillow"
    try:
        img=_IG.grab()
        buf=io.BytesIO()
        img.save(buf,format="PNG")
        b64=base64.b64encode(buf.getvalue()).decode()
        if _OPENAI and OPENAI_API_KEY!="YOUR_OPENAI_API_KEY":
            desc=ask_chatgpt_vision(prompt or "Describe what is on this screen briefly.",b64)
            return desc
        return "Screenshot taken but OpenAI key needed for vision description."
    except Exception as e:
        return f"Screenshot failed: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
#  DAILY BRIEFING
# ═══════════════════════════════════════════════════════════════════════════════

_briefing_done_date = None

def _check_briefing():
    global _briefing_done_date
    if not CFG.get("daily_briefing",True): return
    now=datetime.datetime.now()
    target_str=CFG.get("briefing_time","08:00")
    try: th,tm=[int(x) for x in target_str.split(":")]
    except: th,tm=8,0
    today=now.date()
    if (now.hour==th and now.minute==tm and _briefing_done_date!=today):
        _briefing_done_date=today
        threading.Thread(target=_run_briefing,daemon=True).start()

def _run_briefing():
    time.sleep(1.5)
    p=CFG.get("personality","energetic")
    greets={"calm":"Good morning. Here is your daily briefing.",
            "energetic":"Rise and shine! Here's what's happening today!",
            "guru":"Om. A new day dawns. Let wisdom guide you."}
    speak(greets.get(p,"Good morning!"),priority=0)
    _wait_tts(4)
    city=CFG.get("city","Hyderabad")
    speak(_weather(city),priority=1)
    _wait_tts(4)
    speak(_news()[:260],priority=1)

Clock.schedule_interval(lambda dt:_check_briefing(),60)


# ═══════════════════════════════════════════════════════════════════════════════
#  REMINDER ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _reminder_worker():
    while True:
        time.sleep(20)
        now=datetime.datetime.now()
        rows=db_get_reminders()
        for rid,ts_str,label in rows:
            try:
                ts=datetime.datetime.fromisoformat(ts_str)
                if now>=ts:
                    db_done_reminder(rid)
                    speak(f"Reminder: {label}",priority=0)
                    _ui("toast",f"⏰ {label}")
                    _ui("reminder_due",label)
            except: pass

def _parse_reminder(cmd):
    """Parse 'remind me at 3pm to take medicine' or 'remind me in 10 minutes to call mom'."""
    now=datetime.datetime.now()
    # "in X minutes/hours"
    m=re.search(r'in\s+(\d+)\s*(minute|hour|second)',cmd,re.I)
    if m:
        n=int(m.group(1)); unit=m.group(2).lower()
        delta=datetime.timedelta(
            seconds=n if unit.startswith("s") else
            n*60 if unit.startswith("m") else n*3600)
        ts=(now+delta).isoformat()
        label_m=re.search(r'to\s+(.+)$',cmd,re.I)
        label=label_m.group(1).strip() if label_m else "reminder"
        db_save_reminder(ts,label)
        return f"Reminder set for {label} in {n} {unit}s."
    # "at HH:MM" or "at 3pm"
    m=re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?',cmd,re.I)
    if m:
        h=int(m.group(1)); mn=int(m.group(2) or 0)
        ampm=(m.group(3) or "").lower()
        if ampm=="pm" and h<12: h+=12
        if ampm=="am" and h==12: h=0
        ts=now.replace(hour=h,minute=mn,second=0,microsecond=0)
        if ts<now: ts+=datetime.timedelta(days=1)
        label_m=re.search(r'to\s+(.+)$',cmd,re.I)
        label=label_m.group(1).strip() if label_m else "reminder"
        db_save_reminder(ts.isoformat(),label)
        return f"Reminder set for {label} at {ts.strftime('%I:%M %p')}."
    return "Could not parse reminder time. Try: remind me in 10 minutes to call mom."


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def _weather(city):
    if not _REQ: return "requests not installed."
    if not _ping(): return "No internet for weather."
    city=city.strip() or CFG.get("city","Hyderabad")
    try:
        c=requests.get(f"https://wttr.in/{city.replace(' ','+')}?format=j1",timeout=7).json()["current_condition"][0]
        return (f"{city.title()}: {c['weatherDesc'][0]['value']}, "
                f"{c['temp_C']}°C, feels {c['FeelsLikeC']}°C, humidity {c['humidity']}%.")
    except: return f"Could not get weather for {city}."

try:
    from ctypes import cast,POINTER; from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities,IAudioEndpointVolume; _PYCAW=True
except: _PYCAW=False

def _vobj():
    try:
        d=AudioUtilities.GetSpeakers()
        return cast(d.Activate(IAudioEndpointVolume._iid_,CLSCTX_ALL,None),POINTER(IAudioEndpointVolume))
    except: return None

def vol_up(s=0.08):
    if _PYCAW:
        v=_vobj()
        if v: n=min(1.0,v.GetMasterVolumeLevelScalar()+s);v.SetMasterVolumeLevelScalar(n,None);return f"Volume {int(n*100)}%."
    subprocess.run("nircmd.exe changesysvolume 5243",shell=True,capture_output=True);return "Volume up."
def vol_down(s=0.08):
    if _PYCAW:
        v=_vobj()
        if v: n=max(0.0,v.GetMasterVolumeLevelScalar()-s);v.SetMasterVolumeLevelScalar(n,None);return f"Volume {int(n*100)}%."
    subprocess.run("nircmd.exe changesysvolume -5243",shell=True,capture_output=True);return "Volume down."
def vol_mute():
    if _PYCAW:
        v=_vobj()
        if v: m=v.GetMute();v.SetMute(not m,None);return "Unmuted." if m else "Muted."
    subprocess.run("nircmd.exe mutesysvolume 2",shell=True,capture_output=True);return "Toggled."
def vol_set(pct):
    pct=max(0,min(100,pct))
    if _PYCAW:
        v=_vobj()
        if v: v.SetMasterVolumeLevelScalar(pct/100,None);return f"Volume {pct}%."
    return "pycaw not installed."

def _calc(expr):
    try:
        e=(expr.replace("×","*").replace("÷","/").replace("^","**")
             .replace("plus","+").replace("minus","-").replace("times","*")
             .replace("divided by","/").replace("to the power of","**").replace("squared","**2"))
        e=re.sub(r'(?<=\d)\s*x\s*(?=\d)','*',e)
        safe=re.sub(r"[^0-9+\-*/().\s]","",e).strip()
        if not safe: return "Could not parse."
        r=eval(safe,{"__builtins__":{}})
        if isinstance(r,float) and r==int(r): r=int(r)
        return f"The answer is {r}."
    except ZeroDivisionError: return "Cannot divide by zero."
    except: return "Could not calculate."

def _news():
    if not _REQ or not _ping(): return "Internet needed for news."
    try:
        raw=requests.get("https://feeds.bbci.co.uk/news/rss.xml",timeout=7).text
        titles=re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>",raw)
        if not titles: titles=re.findall(r"<title>(.*?)</title>",raw)
        heads=[t for t in titles if t and "BBC" not in t][:4]
        return "Headlines: "+". ".join(heads)+"." if heads else "No headlines."
    except: return "Could not fetch news."

_shutdown_cancel=threading.Event(); _restart_cancel=threading.Event()

def _do_shutdown():
    _shutdown_cancel.clear()
    for _ in range(100):
        if _shutdown_cancel.is_set(): speak("Shutdown cancelled."); return
        time.sleep(0.1)
    subprocess.run("shutdown /s /t 0",shell=True)

def _do_restart():
    _restart_cancel.clear()
    for _ in range(100):
        if _restart_cancel.is_set(): speak("Restart cancelled."); return
        time.sleep(0.1)
    subprocess.run("shutdown /r /t 0",shell=True)

_APPS={
    "notepad":"notepad.exe","calculator":"calc.exe","paint":"mspaint.exe",
    "chrome":r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome":r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox":"firefox.exe","edge":"msedge.exe","microsoft edge":"msedge.exe",
    "word":"winword.exe","excel":"excel.exe","powerpoint":"powerpnt.exe",
    "vs code":"code.exe","vscode":"code.exe","visual studio":"devenv.exe",
    "file explorer":"explorer.exe","explorer":"explorer.exe",
    "cmd":"cmd.exe","command prompt":"cmd.exe","terminal":"wt.exe",
    "task manager":"taskmgr.exe","spotify":"spotify.exe","vlc":"vlc.exe",
    "discord":"discord.exe","whatsapp":"whatsapp.exe","telegram":"telegram.exe",
    "zoom":"zoom.exe","teams":"teams.exe","steam":"steam.exe",
}
_SITES={
    "youtube":"https://www.youtube.com","google":"https://www.google.com",
    "gmail":"https://mail.google.com","facebook":"https://www.facebook.com",
    "instagram":"https://www.instagram.com","twitter":"https://www.twitter.com",
    "whatsapp":"https://web.whatsapp.com","github":"https://www.github.com",
    "netflix":"https://www.netflix.com","amazon":"https://www.amazon.in",
    "maps":"https://maps.google.com","translate":"https://translate.google.com",
    "wikipedia":"https://www.wikipedia.org","reddit":"https://www.reddit.com",
    "linkedin":"https://www.linkedin.com","chatgpt":"https://chat.openai.com",
}
_INCOG_KW=("incognito","private window","private mode","private browser",
           "open private","browse privately","in private","secret window","inprivate")
_GUEST_KW =("guest mode","guest window","open guest","launch guest","browse as guest")


# ═══════════════════════════════════════════════════════════════════════════════
#  COMPOUND SPLITTER
# ═══════════════════════════════════════════════════════════════════════════════

_COMPOUND_RE=re.compile(
    r'\s+(?:and\s+(?:also\s+)?|then\s+(?:also\s+)?|also\s+|after\s+that\s+|plus\s+)',re.I)

def split_compound(raw):
    parts=[p.strip() for p in _COMPOUND_RE.split(raw.strip()) if p.strip()]
    return parts if len(parts)>1 else [raw]


# ═══════════════════════════════════════════════════════════════════════════════
#  SINGLE COMMAND EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════════

def _add_bubble_src(text,src):
    src_names={"gpt":"AI","google":"Web","vosk":"Vosk","local":"Local",
               "search":"Search","gpt-vision":"Vision"}
    tag=src_names.get(src,"")
    _ui("bubble",("VEDA","ai",f"{text}  [{tag}]" if tag else text,src or "local"))

def run_ai_action(data):
    a,tgt=data.get("action","none"),data.get("target","")
    if a=="open_app":
        for k in _APPS:
            if k==tgt.lower() or k in tgt.lower():
                try: subprocess.Popen(_APPS[k],shell=True); speak(f"Opening {k}."); return True
                except: return False
    if a=="search_web" and tgt:
        webbrowser.open(f"https://www.google.com/search?q={tgt.replace(' ','+')}"); speak(f"Searching {tgt}."); return True
    if a=="type_text" and tgt and _PYAUTOGUI:
        try: pyautogui.write(tgt,interval=0.05); speak("Typed."); return True
        except: return False
    if a=="press_key" and tgt and _PYAUTOGUI:
        km={"enter":"return","tab":"tab","space":"space","backspace":"backspace",
            "delete":"delete","escape":"esc","esc":"esc","ctrl":"ctrl",
            "alt":"alt","shift":"shift","win":"win"}
        try: pyautogui.press(km.get(tgt.lower(),tgt.lower())); speak(f"Pressed {tgt}."); return True
        except: return False
    return False

def _open_incognito(url=""):
    paths=[r"C:\Program Files\Google\Chrome\Application\chrome.exe",
           r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]
    for p in paths:
        if os.path.isfile(p): subprocess.Popen([p,"--incognito"]+([url] if url else [])); return "Opening Chrome incognito."
    subprocess.Popen(f"start chrome --incognito {url}".strip(),shell=True); return "Trying incognito."

def _open_guest(url=""):
    paths=[r"C:\Program Files\Google\Chrome\Application\chrome.exe",
           r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]
    for p in paths:
        if os.path.isfile(p): subprocess.Popen([p,"--guest"]+([url] if url else [])); return "Opening Chrome guest."
    subprocess.Popen("start chrome --guest",shell=True); return "Trying guest mode."

def _execute_single(raw:str, stt_src:str="local", add_bubble:bool=True):
    if not raw: return
    cmd=raw.lower().strip()
    if not cmd: return
    if add_bubble:
        _ui("bubble",("YOU","you",raw,""))
        db_save_chat("user",raw,stt_src)
    _ui("state","thinking")
    words=cmd.split()

    # ── INCOGNITO / GUEST ────────────────────────────────────────────────────
    if any(k in cmd for k in _INCOG_KW): speak(_open_incognito()); return
    if any(k in cmd for k in _GUEST_KW): speak(_open_guest()); return

    # ── SCREENSHOT + VISION ──────────────────────────────────────────────────
    if any(k in cmd for k in ("screenshot","describe screen","what's on screen","what is on screen")):
        speak("Taking screenshot and analyzing…")
        def _ss():
            prompt=re.sub(r'screenshot|describe\s+screen|what(?:\'s| is) on(?: the)? screen','',cmd).strip()
            result=_screenshot_describe(prompt)
            _add_bubble_src(result,"gpt-vision")
            speak(result[:220])
        threading.Thread(target=_ss,daemon=True).start(); return

    # ── REMINDERS ────────────────────────────────────────────────────────────
    if re.search(r'\bremind\b|\balarm\b|\bschedule\b',cmd):
        result=_parse_reminder(cmd); speak(result); return

    # ── DAILY BRIEFING ───────────────────────────────────────────────────────
    if any(k in cmd for k in ("briefing","morning briefing","daily briefing","good morning veda")):
        threading.Thread(target=_run_briefing,daemon=True).start(); return

    # ── MEDIA / SPOTIFY ──────────────────────────────────────────────────────
    if any(k in cmd for k in ("spotify","media","music")):
        if any(k in cmd for k in ("pause","stop music")): speak(_spotify_cmd("play_pause")); return
        if any(k in cmd for k in ("resume","play music","unpause")): speak(_spotify_cmd("play_pause")); return
        if any(k in cmd for k in ("next","skip","next song")): speak(_spotify_cmd("next")); return
        if any(k in cmd for k in ("previous","prev","last song","go back")): speak(_spotify_cmd("prev")); return
        if "volume up" in cmd: speak(_spotify_cmd("volume_up")); return
        if "volume down" in cmd: speak(_spotify_cmd("volume_down")); return
        if any(k in cmd for k in ("what's playing","current song","now playing")):
            speak(_get_spotify_info()); return
        speak("Say: media pause, next, previous, or what's playing."); return

    # ── PERSONALITY SWITCH ───────────────────────────────────────────────────
    if "personality" in cmd or "voice mode" in cmd:
        if "calm" in cmd:
            CFG["personality"]="calm"; _save_cfg(CFG); speak("Switching to calm mode. Breathe easy.")
        elif "energetic" in cmd or "energy" in cmd:
            CFG["personality"]="energetic"; _save_cfg(CFG); speak("Energetic mode! Let's go!")
        elif "guru" in cmd or "wise" in cmd:
            CFG["personality"]="guru"; _save_cfg(CFG); speak("Guru mode. Wisdom flows through every word.")
        else:
            speak("Say: personality calm, energetic, or guru.")
        return

    # ── LANGUAGE ─────────────────────────────────────────────────────────────
    if "language" in cmd or "bhasha" in cmd:
        if "hindi" in cmd or "हिंदी" in cmd:
            CFG["language"]="hi"; _save_cfg(CFG); speak("Hindi mode on. Ab Hindi mein baat karte hain!")
        elif "english" in cmd:
            CFG["language"]="en"; _save_cfg(CFG); speak("Back to English. All good!")
        elif "auto" in cmd:
            CFG["language"]="auto"; _save_cfg(CFG); speak("Auto language detect on.")
        return

    # ── WAKE WORD TRAINER ────────────────────────────────────────────────────
    if "train" in cmd and "wake" in cmd:
        new_w=re.sub(r'train\s+wake\s+word\s*','',cmd).strip().strip('"\'')
        if len(new_w)>=3:
            db_save_wake(new_w)
            global _WAKE_WORDS,_WAKE_PATS
            _WAKE_WORDS,_WAKE_PATS=_build_wake()
            speak(f"Wake word '{new_w}' trained. You can now say '{new_w}' to wake me.")
        else:
            speak("Say: train wake word [your phrase]")
        return

    # ── SYSTEM STATUS ────────────────────────────────────────────────────────
    if any(k in cmd for k in ("system status","cpu","ram","battery","how is my pc","pc status")):
        if _PSUTIL:
            cpu=psutil.cpu_percent(interval=0.5)
            ram=psutil.virtual_memory().percent
            batt=psutil.sensors_battery()
            bstr=f"Battery {int(batt.percent)}% {'charging' if batt.power_plugged else 'on battery'}." if batt else ""
            speak(f"CPU {cpu}%, RAM {ram}%. {bstr}")
        else:
            speak("psutil not installed. Run: pip install psutil")
        return

    # ── YOUTUBE + SEARCH ─────────────────────────────────────────────────────
    if "youtube" in cmd:
        q=re.sub(r'(open\s+)?(youtube)\s*(and\s*)?(search|play|find|watch|for|on)?\s*','',cmd,flags=re.I).strip().strip(".,")
        if q: webbrowser.open(f"https://www.youtube.com/results?search_query={q.replace(' ','+')}"); speak(f"Searching YouTube for {q}.")
        else: webbrowser.open("https://www.youtube.com"); speak("Opening YouTube.")
        return

    if cmd.startswith("play "):
        q=cmd[5:].strip()
        webbrowser.open(f"https://www.youtube.com/results?search_query={q.replace(' ','+')}"); speak(f"Playing {q}."); return

    # ── EXPLICIT URL ─────────────────────────────────────────────────────────
    if words[0]=="open" and len(words)>1 and "." in words[-1]:
        s=words[-1]; webbrowser.open("https://"+s if not s.startswith("http") else s); speak(f"Opening {words[-1]}."); return

    # ── OPEN / LAUNCH ────────────────────────────────────────────────────────
    if cmd.startswith(("open ","launch ","start ")):
        name=cmd.replace("open ","",1).replace("launch ","",1).replace("start ","",1).strip()
        for k,url in _SITES.items():
            if k in name: webbrowser.open(url); speak(f"Opening {k}."); return
        matched=next((k for k in _APPS if k==name),None) or next((k for k in _APPS if k in name),None)
        if matched:
            try: subprocess.Popen(_APPS[matched],shell=True); speak(f"Launching {matched}.")
            except: speak(f"Could not launch {matched}.")
            return
        site=name.replace(" ",""); site+=("" if "." in site else ".com")
        webbrowser.open(f"https://{site}"); speak(f"Opening {name}."); return

    if cmd.strip() in ("browser","open browser"): webbrowser.open("https://www.google.com"); speak("Browser opened."); return

    # ── CLOSE ────────────────────────────────────────────────────────────────
    for pfx in ("exit from ","close ","exit ","quit ","kill ","stop "):
        if cmd.startswith(pfx):
            aname=cmd[len(pfx):].strip()
            pm={"browser":"msedge.exe","edge":"msedge.exe","chrome":"chrome.exe",
                "firefox":"firefox.exe","notepad":"notepad.exe","calc":"calc.exe",
                "calculator":"calc.exe","paint":"mspaint.exe","spotify":"spotify.exe",
                "vlc":"vlc.exe","discord":"discord.exe","telegram":"telegram.exe",
                "zoom":"zoom.exe","teams":"teams.exe","steam":"steam.exe"}
            proc=next((v for k,v in pm.items() if k in aname),None)
            if proc: subprocess.run(f"taskkill /f /im {proc}",shell=True,capture_output=True); speak(f"Closed {aname}.")
            else: speak(f"Don't know how to close {aname}.")
            return

    # ── SEARCH ───────────────────────────────────────────────────────────────
    for pfx in ("search for ","search ","google ","find ","look up "):
        if cmd.startswith(pfx):
            q=cmd[len(pfx):].strip(); webbrowser.open(f"https://www.google.com/search?q={q.replace(' ','+')}"); speak(f"Searching {q}."); return

    # ── WEATHER ──────────────────────────────────────────────────────────────
    if "weather" in cmd:
        cm=re.search(r'weather\s+(?:in|of|for|at)\s+(.+?)(?:\s+today|\s+now|$)',cmd)
        city=cm.group(1).strip() if cm else re.sub(r'\b(weather|what(?:\'s| is)(?: the)?|today|now)\b','',cmd).strip()
        speak(_weather(city if len(city)>1 else CFG.get("city","Hyderabad"))); return

    # ── VOLUME ───────────────────────────────────────────────────────────────
    if "volume" in cmd or cmd in ("mute","unmute"):
        if "unmute" in cmd: speak(vol_mute()); return
        if "mute" in cmd: speak(vol_mute()); return
        m=re.search(r"\b(\d{1,3})\b",cmd)
        if m: speak(vol_set(int(m.group(1)))); return
        if any(k in cmd for k in ("up","increase","louder","higher","max")): speak(vol_up()); return
        if any(k in cmd for k in ("down","decrease","lower","quiet","softer","min")): speak(vol_down()); return
        speak("Volume up, down, mute, or volume 50."); return

    # ── TIME / DATE ───────────────────────────────────────────────────────────
    if "time" in cmd and "timer" not in cmd:
        speak(f"It's {datetime.datetime.now().strftime('%I:%M %p')}."); return
    if "date" in cmd or "what day" in cmd or ("today" in cmd and "weather" not in cmd):
        speak(f"Today is {datetime.datetime.now().strftime('%A, %d %B %Y')}."); return

    # ── CALC ─────────────────────────────────────────────────────────────────
    if cmd.startswith(("calculate ","compute ","how much is ")):
        expr=cmd.replace("calculate","").replace("compute","").replace("how much is","").strip()
        if re.search(r"[\d+\-*/]|plus|minus|times|divided",expr):
            speak(_calc(expr)); return

    # ── NEWS ──────────────────────────────────────────────────────────────────
    if "news" in cmd or "headlines" in cmd:
        speak(_news()); return

    # ── TIMER ────────────────────────────────────────────────────────────────
    if "timer" in cmd or "set timer" in cmd:
        nums=re.findall(r"\d+",cmd)
        if not nums: speak("How many seconds?"); return
        n=int(nums[0]); unit="hours" if "hour" in cmd else "minutes" if "minute" in cmd else "seconds"
        secs=n*(3600 if unit=="hours" else 60 if unit=="minutes" else 1)
        speak(f"Timer: {n} {unit}.")
        def _timer(s=secs,x=n,u=unit):
            _wait_tts(); time.sleep(s)
            speak(f"Timer done! {x} {u} complete.",priority=0)
            _ui("toast",f"⏰ Timer — {x} {u} done!")
        threading.Thread(target=_timer,daemon=True).start(); return

    # ── REMEMBER / FORGET / RECALL ───────────────────────────────────────────
    if "remember " in cmd:
        data=cmd.replace("remember","",1).strip()
        if " is " in data:
            k,v=data.split(" is ",1); db_set(k.strip(),v.strip()); speak(f"Got it — {k.strip()} is {v.strip()}.")
        else: speak("Say: remember [thing] is [value].")
        return
    if "forget everything" in cmd or "clear memory" in cmd:
        db_clear(); speak("Memory cleared."); return
    if "forget " in cmd:
        p=cmd.replace("forget","",1).strip(); db_del(p); speak(f"Forgotten: {p}."); return
    if cmd.startswith(("what is ","who is ","what's ","tell me about ","what are ")):
        q=re.sub(r'^(what is|who is|what\'s|tell me about|what are)\s+','',cmd,flags=re.I).strip()
        ans=db_get(q)
        if ans: speak(ans); return
        if _active_mode()=="surya":
            # AI streaming chat reply
            def _ai_reply():
                _ui("stream","__START__")
                full_text=""
                def _cb(chunk):
                    nonlocal full_text
                    full_text+=chunk
                    _ui("stream",chunk)
                reply,src=ask_chatgpt(q,stream_cb=_cb)
                _ui("stream_end")
                if reply: speak(reply,src)
                else: webbrowser.open(f"https://www.google.com/search?q={q.replace(' ','+')}"); speak(f"Searching for {q}.")
            threading.Thread(target=_ai_reply,daemon=True).start()
        else:
            webbrowser.open(f"https://www.google.com/search?q={q.replace(' ','+')}")
            speak(f"Searching for {q}.")
        return

    # ── MODE ─────────────────────────────────────────────────────────────────
    _OK=("nirvana","go offline","offline mode","akasha dark","switch offline","go nirvana")
    _ON=("surya net","go online","online mode","surya","switch online","go surya")
    if any(k in cmd for k in _OK): threading.Thread(target=_set_nirvana,daemon=True).start(); return
    if any(k in cmd for k in _ON): threading.Thread(target=_set_surya,daemon=True).start(); return

    # ── STATUS ───────────────────────────────────────────────────────────────
    if "status" in cmd or ("mode" in cmd and "what" in cmd):
        m=_active_mode(); speak(f"{'Surya Net — online' if m=='surya' else 'Nirvana Mode — offline'}."); return

    # ── JOKE ─────────────────────────────────────────────────────────────────
    if "joke" in cmd or "funny" in cmd:
        speak(random.choice([
            "Why did the developer go broke? Too much cache and carry.",
            "A SQL query walks into a bar. Can I join you?",
            "Debugging is like being the detective when you're also the criminal.",
            "There are only 10 types of people — those who get binary, and those who don't.",
            "Why do programmers prefer Nirvana Mode? No timeouts in the void.",
        ])); return

    # ── HELP ─────────────────────────────────────────────────────────────────
    if "help" in cmd or "what can you do" in cmd:
        speak("VEDA v12! I handle multi-commands, AI chat, system monitor, Spotify, "
              "screenshots with vision, reminders, daily briefings, wake word training, "
              "and Hindi-English switching. Say Hey Veda and anything!"); return

    # ── SHUTDOWN / RESTART ───────────────────────────────────────────────────
    if any(k in cmd for k in ("shutdown pc","shut down pc","power off","turn off pc")):
        speak("Shutting down in 10 seconds. Say cancel to stop.")
        threading.Thread(target=_do_shutdown,daemon=True).start(); return
    if any(k in cmd for k in ("restart pc","reboot pc","restart computer")):
        speak("Restarting in 10 seconds. Say cancel to stop.")
        threading.Thread(target=_do_restart,daemon=True).start(); return
    if any(k in cmd for k in ("cancel shutdown","cancel restart","abort","cancel")):
        _shutdown_cancel.set(); _restart_cancel.set()
        subprocess.run("shutdown /a",shell=True,capture_output=True); speak("Cancelled."); return

    # ── TYPE / PRESS ─────────────────────────────────────────────────────────
    if cmd.startswith("type ") and _PYAUTOGUI:
        try: pyautogui.write(cmd[5:].strip(),interval=0.05); speak("Typed."); return
        except: speak("Could not type.")
    if cmd.startswith("press ") and _PYAUTOGUI:
        k=cmd[6:].strip()
        km={"enter":"return","tab":"tab","space":"space","backspace":"backspace",
            "delete":"delete","escape":"esc","esc":"esc"}
        try: pyautogui.press(km.get(k,k)); speak(f"Pressed {k}."); return
        except: speak(f"Could not press {k}.")

    # ── BYE ──────────────────────────────────────────────────────────────────
    if any(k in cmd for k in ("bye","goodbye","exit veda","quit veda","good night")):
        speak("Goodbye! Stay awesome.")
        Clock.schedule_once(lambda dt:(App.get_running_app() or type('',(),{'stop':lambda:None})()).stop(),2.8)
        return

    # ── MEMORY FALLBACK ──────────────────────────────────────────────────────
    ans=db_get(cmd)
    if ans: speak(ans); return

    # ── AI PC CONTROL ────────────────────────────────────────────────────────
    if _active_mode()=="surya" and _OPENAI:
        d=ai_pc_control(cmd)
        if run_ai_action(d): return

    # ── AI CHAT (STREAMING) ──────────────────────────────────────────────────
    if _active_mode()=="surya":
        def _ai_stream():
            _ui("stream","__START__")
            full=""
            def _cb(chunk):
                nonlocal full; full+=chunk; _ui("stream",chunk)
            reply,src=ask_chatgpt(cmd,stream_cb=_cb)
            _ui("stream_end")
            if reply: speak(reply,src)
        threading.Thread(target=_ai_stream,daemon=True).start(); return

    # ── FALLBACK SEARCH ──────────────────────────────────────────────────────
    _ui("bubble",("VEDA","sys","Searching…","search"))
    speak("Let me search that.")
    webbrowser.open(f"https://www.google.com/search?q={cmd.replace(' ','+')}")


def execute(raw:str,stt_src:str="local"):
    if not raw: return
    parts=split_compound(raw.strip())
    if len(parts)>1:
        _ui("bubble",("YOU","you",raw,""))
        db_save_chat("user",raw,stt_src)
        speak(f"{len(parts)} tasks — on it!")
        def _all():
            for p in parts:
                _wait_tts(3.0)
                _execute_single(p,stt_src,add_bubble=False)
        threading.Thread(target=_all,daemon=True).start()
    else:
        _execute_single(raw,stt_src,add_bubble=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  VOICE LOOP  — improved reliability
# ═══════════════════════════════════════════════════════════════════════════════

def voice_loop():
    time.sleep(2.5)
    mode=_active_mode()
    speak(f"Hey! I'm VEDA v12. {'Surya Net online.' if mode=='surya' else 'Nirvana Mode active.'} Say Hey Veda!")
    _ui("mode",mode)
    last_wake=0.0; WAKE_WIN=9

    while True:
        try: text=_stt_q.get(timeout=30)
        except queue.Empty: continue
        if not text: continue
        text=text.strip(); print(f"[HEARD] {text}")

        if _has_wake(text):
            last_wake=time.time()
            cmd=_strip_wake(text).strip(" ,.")
            if cmd and len(cmd)>=2:
                threading.Thread(target=execute,args=(cmd,),daemon=True).start()
            else:
                speak("Yes?")
                _wait_tts(3)
                try:
                    follow=_stt_q.get(timeout=8)
                    if follow and follow.strip():
                        fc=_strip_wake(follow.strip()).strip(" ,.")
                        if not fc: fc=follow.strip()
                        threading.Thread(target=execute,args=(fc,),daemon=True).start()
                except queue.Empty:
                    speak("Didn't catch that.")
            continue

        if time.time()-last_wake<WAKE_WIN:
            ws=text.strip().split()
            ok=((bool(ws) and ws[0] in _CMD_W)
                or len(ws)>=3
                or (len(ws)==2 and any(len(w)>2 for w in ws))
                or (len(ws)==1 and ws[0] in _CMD_W))
            if ok:
                threading.Thread(target=execute,args=(text,),daemon=True).start()
                last_wake=time.time()
            else: print(f"[NOISE] '{text}'")


# ═══════════════════════════════════════════════════════════════════════════════
#  PARTICLES
# ═══════════════════════════════════════════════════════════════════════════════

class _Particle:
    __slots__=("x","y","vx","vy","life","ml","sz")
    def __init__(self,mode,W,H): self.reset(mode,W,H)
    def reset(self,mode,W,H):
        self.x=random.uniform(0,W); self.y=random.uniform(0,H)
        if mode=="surya":
            self.vx=random.uniform(-0.20,0.20); self.vy=random.uniform(0.25,1.10)
            self.life=random.uniform(0.3,1.0); self.sz=random.uniform(1.1,2.6)
        else:
            self.vx=random.uniform(-0.05,0.05); self.vy=random.uniform(-0.05,0.05)
            self.life=random.uniform(0.1,1.0); self.sz=random.uniform(0.8,2.0)
        self.ml=self.life
    def update(self,dt,mode,W,H):
        self.x+=self.vx; self.y+=self.vy
        if mode=="surya":
            self.life-=dt*0.42
            if self.life<=0 or self.y>H+5: self.reset(mode,W,H); self.y=0
        else:
            self.life+=dt*random.choice((-1,1))*0.18
            self.life=max(0.05,min(self.ml,self.life))
            if not(0<=self.x<=W and 0<=self.y<=H): self.reset(mode,W,H)


# ═══════════════════════════════════════════════════════════════════════════════
#  CYBER GRID BACKGROUND
# ═══════════════════════════════════════════════════════════════════════════════

class CyberGrid(Widget):
    """Animated receding perspective grid — the cyberpunk floor."""
    def __init__(self,**kw):
        super().__init__(**kw); self._t=0.0
        Clock.schedule_interval(self._tick,1/30)

    def _tick(self,dt): self._t+=dt*0.35; self._draw()

    def _draw(self):
        self.canvas.clear()
        pal=P(); w,h=self.width,self.height
        if w<2 or h<2: return
        with self.canvas:
            Color(*pal["bg"],1); Rectangle(pos=self.pos,size=(w,h))
            vp_x=w/2; vp_y=h*0.52   # vanishing point
            # Horizontal scan lines (perspective)
            for i in range(12):
                frac=(i+1)/13
                y=vp_y+(h-vp_y)*frac
                alpha=0.03+frac*0.06
                Color(*pal["grid"],alpha)
                Line(points=[self.x,self.y+y,self.x+w,self.y+y],width=0.7)
            # Vertical lines converging to vanishing point
            for i in range(14):
                frac=i/13
                bx=self.x+frac*w
                Color(*pal["grid"],0.035)
                Line(points=[self.x+vp_x,self.y+vp_y,bx,self.y],width=0.6)
            # Animated scan shimmer
            sy=((self._t*55)%(h+30))-15
            Color(*pal["primary"],0.04)
            Line(points=[self.x,self.y+sy,self.x+w,self.y+sy],width=2.0)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN VISUALISER ORB
# ═══════════════════════════════════════════════════════════════════════════════

class Visualiser(Widget):
    def __init__(self,**kw):
        super().__init__(**kw)
        self.mode="surya"; self.state="ready"
        self._t=0.0; self._pulse=0.0; self._pdir=1
        self._energy=0.0; self._wave=[0.0]*64
        self._dots=[]; self._parts=[]; self._think_t=0.0
        self._last_size=(0,0)
        Clock.schedule_once(self._init_p,0.3)
        Clock.schedule_interval(self._tick,1/60)
        self.bind(size=self._on_resize)

    def _on_resize(self,*_):
        sz=(int(self.width),int(self.height))
        if sz!=self._last_size and sz[0]>10:
            self._last_size=sz; Clock.schedule_once(self._init_p,0.1)

    def _init_p(self,dt):
        W,H=max(self.width,300),max(self.height,300)
        R=min(W,H)*0.26
        self._dots=[[random.uniform(0,math.tau),
                     R*random.uniform(1.12,1.95),
                     random.uniform(0.002,0.008)*random.choice((-1,1)),
                     random.uniform(0.7,2.5),
                     random.uniform(0.1,1.0),
                     random.uniform(0.011,0.05)] for _ in range(72)]
        self._parts=[_Particle(self.mode,W,H) for _ in range(48)]

    def set_mode(self,m):
        self.mode=m
        W,H=self.width,self.height
        for p in self._parts: p.reset(m,W,H)
    def set_state(self,s): self.state=s
    def set_energy(self,e): self._energy=e

    def _tick(self,dt):
        self._t+=dt; self._think_t+=dt
        self._pulse+=dt*2.2*self._pdir
        if self._pulse>=1: self._pdir=-1
        if self._pulse<=0: self._pdir=1
        for d in self._dots:
            d[0]+=d[2]; d[4]+=d[5]
            if d[4]>1.0 or d[4]<0.05: d[5]*=-1
        W,H=self.width,self.height
        for p in self._parts: p.update(dt,self.mode,W,H)
        amp=(0.58+self._energy*0.42) if self.state=="listening" else \
            (0.78 if self.state=="speaking" else 0.09)
        ns=amp*abs(math.sin(self._t*10.5+random.uniform(-0.22,0.22)))
        self._wave=self._wave[1:]+[ns]
        self._draw()

    def _draw(self):
        self.canvas.clear()
        with _MORPH_LOCK: mt=_MORPH
        pal=P(); W,H=self.width,self.height
        if W<2 or H<2: return
        cx=self.center_x; cy=self.center_y+8
        R=min(W,H)*0.255
        sc={"listening":(0.12,1.00,0.48),"thinking":(0.95,0.88,0.08),
            "speaking":pal["accent"]}.get(self.state,pal["primary"])

        with self.canvas:
            Color(*pal["bg"],1); Rectangle(pos=self.pos,size=self.size)
            # Sri Yantra lines
            self._yantra(cx,cy,R,pal)
            # Particles
            for p in self._parts:
                Color(*pal["accent"],p.life*0.25)
                Ellipse(pos=(p.x-p.sz/2,p.y-p.sz/2),size=(p.sz,p.sz))
            # Crossfade orbs
            if mt<0.99: self._surya_orb(cx,cy,R,pal,sc,1.0-mt)
            if mt>0.01: self._nirvana_ring(cx,cy,R,pal,sc,mt)
            # Orbit dots
            for d in self._dots:
                ox=cx+d[1]*math.cos(d[0]); oy=cy+d[1]*math.sin(d[0])
                Color(*pal["chakra"],d[4]*0.16)
                Ellipse(pos=(ox-d[3]/2,oy-d[3]/2),size=(d[3],d[3]))
            # Mic energy ring
            if self._energy>0.02:
                er=R*(1.05+self._energy*0.22)
                Color(*sc,self._energy*0.68)
                Line(circle=(cx,cy,er),width=2.2+self._energy*3.8)
            # Lotus petals
            self._lotus(cx,cy,R,pal,sc)
            # Waveform
            self._wave_draw(cx,cy,R,pal)
            # Thinking dots
            if self.state=="thinking": self._think_dots(cx,cy,R,pal)

    def _yantra(self,cx,cy,R,pal):
        with self.canvas:
            for i in range(4):
                r2=R*(0.32+i*0.17)
                Color(*pal["yantra"],0.07+i*0.01)
                pts_up=[cx,cy+r2,cx-r2*0.866,cy-r2*0.5,cx+r2*0.866,cy-r2*0.5]
                Line(points=pts_up+[pts_up[0],pts_up[1]],width=0.6)
                pts_dn=[cx,cy-r2,cx-r2*0.866,cy+r2*0.5,cx+r2*0.866,cy+r2*0.5]
                Line(points=pts_dn+[pts_dn[0],pts_dn[1]],width=0.6)
            for r2 in [R*1.06,R*1.14,R*1.24]:
                Color(*pal["yantra"],0.04); Line(circle=(cx,cy,r2),width=0.5)

    def _lotus(self,cx,cy,R,pal,sc):
        n=8; base_r=R*1.10
        pr=R*(0.11+(0.05 if self.state in ("listening","speaking") else 0)+self._energy*0.06)
        with self.canvas:
            for i in range(n):
                a=i*math.tau/n+self._t*0.22
                px=cx+base_r*math.cos(a); py=cy+base_r*math.sin(a)
                al=0.28+0.22*abs(math.sin(self._t*1.4+i*math.pi/n))
                Color(*pal["lotus"],al)
                Ellipse(pos=(px-pr,py-pr),size=(pr*2,pr*2))

    def _surya_orb(self,cx,cy,R,pal,sc,alpha):
        t=self._t; pu=self._pulse; a=alpha
        with self.canvas:
            for fr,ba in [(1.50,0.03),(1.30,0.055),(1.12,0.09),(1.02,0.14)]:
                Color(*sc,min(1.0,(ba+pu*0.04)*a)); Ellipse(pos=(cx-R*fr,cy-R*fr),size=(R*fr*2,R*fr*2))
            Color(*pal["bg"],a); Ellipse(pos=(cx-R,cy-R),size=(R*2,R*2))
            for fr,col,ba in [(0.88,pal["glow"],0.22+pu*0.08),(0.68,pal["primary"],0.16+pu*0.06),
                              (0.46,pal["accent"],0.22+pu*0.10),(0.24,(1,1,1),0.07+pu*0.04)]:
                Color(*col,min(1.0,ba*a)); Ellipse(pos=(cx-R*fr,cy-R*fr),size=(R*fr*2,R*fr*2))
            # 7 chakra rings
            for ri in range(7):
                Color(*pal["chakra"],min(1.0,(0.06+pu*0.05)*a))
                Line(circle=(cx,cy,R*(0.36+ri*0.09)),width=0.7)
            # Solar waves
            wcs=[(0.42,0.12,0.95),(0.00,0.82,0.92),(0.55,0.18,1.00),(1.0,0.48,0.08),(0.20,0.95,0.55)]
            nw=5 if self.state in ("listening","speaking") else 3
            ab=R*(0.32+self._energy*0.13 if self.state in ("listening","speaking") else 0.14)
            for wi in range(nw):
                ph=t*(1.0+wi*0.38)+wi*math.pi/nw
                amp=ab*(1.0+pu*0.18)*(0.8+0.4*math.sin(t*0.7+wi))
                pts=[]
                for si in range(91):
                    frac=si/90; lx=cx-R*0.80+frac*R*1.60
                    mx=math.sqrt(max(0,(R*0.82)**2-(lx-cx)**2))
                    wy=amp*math.sin((2.2+wi*0.72)*math.pi*frac+ph)+amp*0.35*math.sin((2.2+wi*0.72)*2*math.pi*frac-ph*1.3)
                    pts.extend([lx,cy+max(-mx,min(mx,wy))])
                Color(*wcs[wi%len(wcs)],min(1.0,(0.60-wi*0.07+pu*0.12)*a))
                if len(pts)>=4: Line(points=pts,width=1.9+(0.7 if wi==0 else 0))
            Color(*sc,min(1.0,(0.55+pu*0.18)*a)); Line(circle=(cx,cy,R),width=1.7)
            hx,hy,hr=cx-R*0.26,cy+R*0.30,R*0.17
            Color(1,1,1,min(1.0,(0.13+pu*0.05)*a)); Ellipse(pos=(hx-hr,hy-hr),size=(hr*2,hr*2))
            cr=R*(0.05+pu*0.02); Color(*sc,min(1.0,0.90*a)); Ellipse(pos=(cx-cr,cy-cr),size=(cr*2,cr*2))

    def _nirvana_ring(self,cx,cy,R,pal,sc,alpha):
        t=self._t; pu=self._pulse; a=alpha
        with self.canvas:
            for fr,ba in [(1.48,0.04),(1.28,0.07),(1.10,0.11),(1.01,0.17)]:
                Color(*sc,min(1.0,(ba+pu*0.04)*a)); Ellipse(pos=(cx-R*fr,cy-R*fr),size=(R*fr*2,R*fr*2))
            vr=R*0.80; Color(0,0,0,a); Ellipse(pos=(cx-vr,cy-vr),size=(vr*2,vr*2))
            for rr,w,ba in [(R,17.0,0.10),(R,9.0,0.20),(R,4.5,0.55)]:
                Color(*sc,min(1.0,(ba+pu*0.08)*a)); Line(circle=(cx,cy,rr),width=w)
            rot=0.17+self._energy*0.38 if self.state in ("listening","speaking") else 0.11
            for i in range(200):
                a0=math.radians(i*1.8)+t*rot; a1=math.radians((i+1)*1.8)+t*rot
                r2,g2,b2=_hsv((i/200+t*0.05)%1.0,0.55,1.0)
                br=(0.44+0.44*abs(math.sin(i/200*math.pi*2.8+t*0.5)))*(0.68+pu*0.32)
                Color(r2,g2,b2,min(1.0,br*alpha))
                Line(points=[cx+R*math.cos(a0),cy+R*math.sin(a0),cx+R*math.cos(a1),cy+R*math.sin(a1)],width=3.0)
            Color(1,1,1,min(1.0,(0.55+pu*0.18)*alpha)); Line(circle=(cx,cy,R*0.95),width=1.3)
            Color(*pal["teal"],min(1.0,(0.24+pu*0.10)*alpha)); Line(circle=(cx,cy,R*1.06),width=0.9)

    def _wave_draw(self,cx,cy,R,pal):
        n=len(self._wave); w2=R*0.48
        with self.canvas:
            if self.state not in ("listening","speaking"):
                Color(*pal["primary"],0.06); Line(points=[cx-w2,cy,cx+w2,cy],width=0.9); return
            pts=[]; pts2=[]
            for i,s in enumerate(self._wave):
                x=cx-w2+(i/(n-1))*w2*2; env=math.sin(math.pi*i/(n-1)); h=s*R*0.26*env
                pts.extend([x,cy+h]); pts2.extend([x,cy-h])
            Color(*pal["primary"],0.90)
            if len(pts)>=4: Line(points=pts,width=2.3)
            Color(*pal["accent"],0.54)
            if len(pts2)>=4: Line(points=pts2,width=1.4)

    def _think_dots(self,cx,cy,R,pal):
        n=3; sp=R*0.22; y=cy+R*1.34
        with self.canvas:
            for i in range(n):
                ph=self._think_t*3.2+i*(math.tau/n)
                sc2=0.4+0.6*abs(math.sin(ph)); dr=R*0.046*sc2
                Color(*pal["primary"],0.52+0.44*sc2)
                Ellipse(pos=(cx+(i-1)*sp-dr,y-dr),size=(dr*2,dr*2))


# ═══════════════════════════════════════════════════════════════════════════════
#  MIC BAR
# ═══════════════════════════════════════════════════════════════════════════════

class MicBar(Widget):
    def __init__(self,**kw):
        super().__init__(**kw); self._e=0.0; self._tgt=0.0
        Clock.schedule_interval(self._tick,1/30)
    def set_energy(self,e):
        if e>self._tgt: self._tgt=e
        else: self._tgt=max(e,self._tgt*0.62)
    def _tick(self,dt):
        self._tgt=max(0,self._tgt-dt*1.5); self._e+=(self._tgt-self._e)*0.28; self._draw()
    def _draw(self):
        self.canvas.clear(); pal=P(); n=34; bw=self.width/n
        with self.canvas:
            Color(*pal["bg"],1); Rectangle(pos=self.pos,size=self.size)
            for i in range(n):
                t2=time.time()*7.0+i*0.72
                bh=max(2.0,self._e*(self.height*0.84)+self.height*0.032*abs(math.sin(t2)))
                r,g,b=_lerp(pal["primary"][0],pal["accent"][0],min(1.0,self._e*2.2)),\
                       _lerp(pal["primary"][1],pal["accent"][1],min(1.0,self._e*2.2)),\
                       _lerp(pal["primary"][2],pal["accent"][2],min(1.0,self._e*2.2))
                Color(r,g,b,0.46+self._e*0.54)
                RoundedRectangle(pos=(self.x+(i/n)*self.width+1,self.y+self.height/2-bh/2),
                                 size=(bw-2,bh),radius=[2])


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM MONITOR WIDGET
# ═══════════════════════════════════════════════════════════════════════════════

class SysMonWidget(Widget):
    def __init__(self,**kw):
        super().__init__(**kw)
        self._cpu=0; self._ram=0; self._batt=-1; self._plug=True
        self._hist_cpu=[0]*40; self._hist_ram=[0]*40
        self._t=0.0
        Clock.schedule_interval(self._tick,1/15)

    def update(self,data):
        self._cpu=data.get("cpu",0); self._ram=data.get("ram",0)
        self._batt=data.get("batt",-1); self._plug=data.get("plug",True)
        self._hist_cpu=self._hist_cpu[1:]+[self._cpu/100]
        self._hist_ram=self._hist_ram[1:]+[self._ram/100]

    def _tick(self,dt): self._t+=dt; self._draw()

    def _draw(self):
        self.canvas.clear()
        pal=P(); w,h=self.width,self.height
        if w<10 or h<10: return
        with self.canvas:
            # Card background
            Color(*pal["card"],1)
            RoundedRectangle(pos=(self.x,self.y),size=(w,h),radius=[8])
            Color(*pal["primary"],0.25)
            Line(rounded_rectangle=(self.x,self.y,w,h,8),width=1.0)

            # Mini sparkline — CPU (top half)
            ch=h*0.38; cw=w-16; cx0=self.x+8; cy0=self.y+h*0.55
            Color(*pal["primary"],0.12); Rectangle(pos=(cx0,cy0),size=(cw,ch))
            pts=[]
            for i,v in enumerate(self._hist_cpu):
                pts.extend([cx0+i*(cw/39),cy0+v*ch])
            Color(*pal["primary"],0.85)
            if len(pts)>=4: Line(points=pts,width=1.2)

            # RAM sparkline (bottom)
            ry0=self.y+8
            Color(*pal["teal"],0.10); Rectangle(pos=(cx0,ry0),size=(cw,h*0.35))
            pts2=[]
            for i,v in enumerate(self._hist_ram):
                pts2.extend([cx0+i*(cw/39),ry0+v*h*0.35])
            Color(*pal["teal"],0.80)
            if len(pts2)>=4: Line(points=pts2,width=1.2)

            # Battery arc
            if self._batt>=0:
                bx=self.x+w-22; by=self.y+h/2; br=9
                Color(*pal["muted"],0.6); Line(circle=(bx,by,br),width=1.5)
                col=(0.15,1.0,0.42) if self._batt>20 else (1.0,0.28,0.15)
                Color(*col,0.9)
                ang=360*(self._batt/100)
                Line(circle=(bx,by,br,90,90+ang),width=2.5)


# ═══════════════════════════════════════════════════════════════════════════════
#  CONNECTION DOT
# ═══════════════════════════════════════════════════════════════════════════════

class ConnDot(Widget):
    def __init__(self,**kw):
        super().__init__(**kw); self._online=True; self._blink=0.0
        Clock.schedule_interval(self._tick,1/15)
        Clock.schedule_interval(self._check,20)
        Clock.schedule_once(self._check,0.5)
    def _check(self,dt):
        def _bg(): self._online=_ping(); _ui("online",self._online)
        threading.Thread(target=_bg,daemon=True).start()
    def set_online(self,v): self._online=v
    def _tick(self,dt): self._blink=(self._blink+dt*2.5)%math.tau; self._draw()
    def _draw(self):
        self.canvas.clear()
        col=(0.12,1.00,0.42) if self._online else (1.00,0.25,0.15)
        pulse=0.55+0.45*math.sin(self._blink); r=min(self.width,self.height)/2-2
        with self.canvas:
            Color(*col,pulse*0.30); Ellipse(pos=(self.x,self.y),size=(self.width,self.height))
            Color(*col,0.92); Ellipse(pos=(self.x+r*0.45,self.y+r*0.45),size=(r*1.1,r*1.1))


# ═══════════════════════════════════════════════════════════════════════════════
#  MODE SLIDER
# ═══════════════════════════════════════════════════════════════════════════════

class ModeSlider(Widget):
    def __init__(self,**kw):
        super().__init__(**kw); self._t=self._tgt=0.0
        Clock.schedule_interval(self._tick,1/60)
    def set_mode(self,m): self._tgt=0.0 if m=="surya" else 1.0
    def _tick(self,dt):
        d=self._tgt-self._t
        if abs(d)>0.001: self._t+=d*0.14; self._draw()
    def _draw(self):
        self.canvas.clear(); w,h=self.width,self.height; x,y=self.x,self.y
        tr=h/2; kr=tr-3; kx=x+tr+self._t*(w-2*tr); ky=y+h/2
        r=SURYA_NET["primary"][0]*(1-self._t)+NIRVANA_MODE["primary"][0]*self._t
        g=SURYA_NET["primary"][1]*(1-self._t)+NIRVANA_MODE["primary"][1]*self._t
        b=SURYA_NET["primary"][2]*(1-self._t)+NIRVANA_MODE["primary"][2]*self._t
        with self.canvas:
            Color(r,g,b,0.18); RoundedRectangle(pos=(x,y),size=(w,h),radius=[tr])
            Color(r,g,b,0.55); Line(rounded_rectangle=(x,y,w,h,tr),width=1.0)
            Color(r,g,b,0.16); Ellipse(pos=(kx-kr*1.5,ky-kr*0.65),size=(kr*3.0,kr*1.3))
            Color(r,g,b,0.95); Ellipse(pos=(kx-kr,ky-kr),size=(kr*2,kr*2))
            ir=kr*0.36; Color(0.01,0.01,0.06,0.96); Ellipse(pos=(kx-ir,ky-ir),size=(ir*2,ir*2))
            sx=x+tr; Color(1.00,0.82,0.10,0.65*(1-self._t)+0.18*self._t)
            Ellipse(pos=(sx-5,ky-5),size=(10,10))
            mx=x+w-tr; Color(0.60,0.18,1.00,0.18*(1-self._t)+0.65*self._t)
            Ellipse(pos=(mx-5,ky-5),size=(10,10))
    def on_touch_down(self,touch):
        if self.collide_point(*touch.pos):
            self._tgt=1.0 if self._tgt<0.5 else 0.0
            fn=_set_nirvana if self._tgt>=0.5 else _set_surya
            threading.Thread(target=fn,daemon=True).start(); return True
        return super().on_touch_down(touch)


# ═══════════════════════════════════════════════════════════════════════════════
#  LIVE CLOCK
# ═══════════════════════════════════════════════════════════════════════════════

class LiveClock(Label):
    def __init__(self,**kw):
        super().__init__(**kw)
        Clock.schedule_interval(self._tick,1.0); self._tick(0)
    def _tick(self,dt):
        pal=P(); self.text=datetime.datetime.now().strftime("%H:%M:%S"); self.color=(*pal["sub"],0.85)


# ═══════════════════════════════════════════════════════════════════════════════
#  STREAMING AI CHAT BUBBLE  — typewriter label
# ═══════════════════════════════════════════════════════════════════════════════

def _hx(c): return "{:02x}{:02x}{:02x}".format(int(c[0]*255),int(c[1]*255),int(c[2]*255))

class StreamLabel(Label):
    """Label that animates text appearing character by character."""
    def __init__(self,**kw):
        self._full=""
        self._shown=""
        self._idx=0
        super().__init__(**kw)
        Clock.schedule_interval(self._type_tick,0.018)

    def set_full(self,text): self._full=text; self._shown=""; self._idx=0
    def append_chunk(self,chunk): self._full+=chunk

    def _type_tick(self,dt):
        if self._idx<len(self._full):
            step=max(1,int(len(self._full)*0.04))
            self._shown=self._full[:self._idx+step]
            self._idx+=step
            pal=P()
            self.text=(f"[color=#{_hx(pal['sub'])}]now[/color]  "
                       f"[b][color=#{_hx(pal['ai_col'])}]◈ VEDA[/color][/b]  "
                       f"[color=#{_hx(pal['text'])}]{self._shown}[/color]")


# ═══════════════════════════════════════════════════════════════════════════════
#  CHAT LOG
# ═══════════════════════════════════════════════════════════════════════════════

_SRC_NAMES={"gpt":"AI","google":"Web","vosk":"Vosk","local":"Local",
            "search":"Search","gpt-vision":"Vision","":""}

class ChatLog(ScrollView):
    def __init__(self,**kw):
        super().__init__(**kw)
        self.do_scroll_x=False; self.bar_width=4
        self._box=BoxLayout(orientation="vertical",size_hint_y=None,spacing=8,padding=[10,8])
        self._box.bind(minimum_height=self._box.setter("height"))
        self.add_widget(self._box)
        self._stream_lbl=None

    def add_bubble(self,who,role,text,src=""):
        pal=P(); ts=datetime.datetime.now().strftime("%H:%M")
        if role=="you":    col=pal["you_col"]; pfx="▸ YOU"
        elif role=="ai":   col=pal["ai_col"];  pfx="◈ VEDA"
        else:              col=pal["sys_col"]; pfx=f"• {who}"
        tag=_SRC_NAMES.get(src,"")
        src_tag=f" [color=#{_hx(pal['sub'])}][{tag}][/color]" if tag else ""
        msg=(f"[color=#{_hx(pal['sub'])}]{ts}[/color]  "
             f"[b][color=#{_hx(col)}]{pfx}[/color][/b]{src_tag}  "
             f"[color=#{_hx(pal['text'])}]{text}[/color]")
        lbl=Label(text=msg,markup=True,font_size=13,size_hint_y=None,
                  text_size=(max(self.width,320)-28,None),
                  halign="left",valign="top",padding=(6,5),opacity=0)
        lbl.bind(texture_size=lambda i,v:setattr(i,"height",v[1]+10))
        lbl.bind(width=lambda i,v:setattr(i,"text_size",(max(v,320)-14,None)))
        self._box.add_widget(lbl)
        Animation(opacity=1,duration=0.25).start(lbl)
        Clock.schedule_once(lambda dt:setattr(self,"scroll_y",0),0.05)

    def start_stream(self):
        """Create a streaming bubble for typewriter AI reply."""
        pal=P()
        self._stream_lbl=StreamLabel(
            text="",markup=True,font_size=13,size_hint_y=None,
            text_size=(max(self.width,320)-28,None),
            halign="left",valign="top",padding=(6,5))
        self._stream_lbl.bind(texture_size=lambda i,v:setattr(i,"height",v[1]+10))
        self._stream_lbl.bind(width=lambda i,v:setattr(i,"text_size",(max(v,320)-14,None)))
        self._box.add_widget(self._stream_lbl)
        Clock.schedule_once(lambda dt:setattr(self,"scroll_y",0),0.05)

    def append_stream(self,chunk):
        if self._stream_lbl: self._stream_lbl.append_chunk(chunk)

    def end_stream(self):
        self._stream_lbl=None

    def clear(self): self._box.clear_widgets(); self._stream_lbl=None


# ═══════════════════════════════════════════════════════════════════════════════
#  FLOATING AI CHAT PANEL  — slides in from right
# ═══════════════════════════════════════════════════════════════════════════════

class FloatingChatPanel(FloatLayout):
    """A slide-in AI chat panel pinned to the right edge."""
    def __init__(self,**kw):
        super().__init__(**kw)
        self._open=False; self._anim_x=0.0
        self._panel=BoxLayout(orientation="vertical",
                              size_hint=(None,None),
                              width=340,height=480)
        self._build_panel()
        self.add_widget(self._panel)
        Clock.schedule_once(self._init_pos,0.2)
        Clock.schedule_interval(self._theme_tick,1/10)

    def _init_pos(self,dt):
        self._panel.pos=(Window.width,Window.height//2-240)
        self._anim_x=Window.width

    def _build_panel(self):
        pal=P()
        # Header
        hdr=BoxLayout(size_hint=(1,None),height=36,padding=[8,4])
        with hdr.canvas.before:
            self._hdr_bg=Color(*pal["card"],1)
            self._hdr_rect=RoundedRectangle(pos=hdr.pos,size=hdr.size,radius=[8,8,0,0])
        hdr.bind(pos=lambda i,v:setattr(self._hdr_rect,"pos",v),
                 size=lambda i,v:setattr(self._hdr_rect,"size",v))
        self._chat_title=Label(text="◈ AI Chat",font_size=12,bold=True,
                               color=(*pal["primary"],1))
        btn_close=Button(text="✕",font_size=11,size_hint=(None,1),width=28,
                         background_color=(0,0,0,0),color=(*pal["sub"],1))
        btn_close.bind(on_press=lambda *_:self.toggle())
        hdr.add_widget(self._chat_title); hdr.add_widget(btn_close)
        self._panel.add_widget(hdr)

        # Chat area
        self._chat=ChatLog(size_hint=(1,1))
        with self._chat.canvas.before:
            self._chat_bg=Color(*pal["bg2"],1)
            self._chat_rect=Rectangle(pos=self._chat.pos,size=self._chat.size)
        self._chat.bind(pos=lambda i,v:setattr(self._chat_rect,"pos",v),
                        size=lambda i,v:setattr(self._chat_rect,"size",v))
        self._panel.add_widget(self._chat)

        # Input
        inp=BoxLayout(size_hint=(1,None),height=40,spacing=4,padding=[4,4])
        with inp.canvas.before:
            self._inp_bg=Color(*pal["card"],1)
            self._inp_rect=RoundedRectangle(pos=inp.pos,size=inp.size,radius=[0,0,8,8])
        inp.bind(pos=lambda i,v:setattr(self._inp_rect,"pos",v),
                 size=lambda i,v:setattr(self._inp_rect,"size",v))
        self._txt=TextInput(hint_text="Ask anything…",multiline=False,font_size=12,
                            background_color=(0.08,0.04,0.01,0.9),
                            foreground_color=(*pal["text"],1),
                            hint_text_color=(*pal["sub"],0.4),padding=[8,8])
        self._txt.bind(on_text_validate=self._send)
        btn_send=Button(text="→",font_size=13,bold=True,size_hint=(None,1),width=34,
                        background_color=(*pal["accent"],1),color=(1,1,1,1))
        btn_send.bind(on_press=self._send)
        inp.add_widget(self._txt); inp.add_widget(btn_send)
        self._panel.add_widget(inp)

    def _send(self,*_):
        q=self._txt.text.strip()
        if not q: return
        self._txt.text=""
        self._chat.add_bubble("YOU","you",q,"")
        db_save_chat("user",q,"chat-panel")
        def _reply():
            self._chat.start_stream()
            full=""
            def _cb(chunk):
                nonlocal full; full+=chunk
                _ui("stream",chunk)  # also streams to main chat
                Clock.schedule_once(lambda dt:self._chat.append_stream(chunk),0)
            reply,src=ask_chatgpt(q,stream_cb=_cb)
            Clock.schedule_once(lambda dt:self._chat.end_stream(),0)
            if reply:
                Clock.schedule_once(lambda dt:self._chat.add_bubble("VEDA","ai",reply,src or "gpt"),0.1)
        threading.Thread(target=_reply,daemon=True).start()

    def toggle(self):
        self._open=not self._open
        tx=Window.width-self._panel.width-8 if self._open else Window.width
        Animation(x=tx,duration=0.32,t='out_cubic').start(self._panel)

    def _theme_tick(self,dt):
        pal=P()
        self._chat_title.color=(*pal["primary"],1)
        self._hdr_bg.rgba=(*pal["card"],1)
        self._chat_bg.rgba=(*pal["bg2"],1)
        self._inp_bg.rgba=(*pal["card"],1)
        self._txt.foreground_color=(*pal["text"],1)
        self._txt.hint_text_color=(*pal["sub"],0.4)


# ═══════════════════════════════════════════════════════════════════════════════
#  TOAST OVERLAY
# ═══════════════════════════════════════════════════════════════════════════════

class ToastOverlay(FloatLayout):
    def __init__(self,**kw): super().__init__(**kw)
    def show(self,text):
        pal=P()
        lbl=Label(text=str(text),markup=False,font_size=13,
                  size_hint=(None,None),height=38,
                  halign="center",valign="middle",color=(*pal["text"],1))
        lbl.texture_update(); lbl.width=max(240,lbl.texture_size[0]+34)
        lbl.pos_hint={"center_x":0.5,"y":0.06}
        with lbl.canvas.before:
            Color(*pal["glow"],0.20); RoundedRectangle(pos=lbl.pos,size=lbl.size,radius=[12])
            Color(*pal["primary"],0.80); Line(rounded_rectangle=(*lbl.pos,*lbl.size,12),width=1.2)
        self.add_widget(lbl)
        lbl.bind(pos=lambda i,v:self._rebg(i))
        Animation(opacity=1,duration=0.2).start(lbl)
        Clock.schedule_once(lambda dt,l=lbl:Animation(opacity=0,duration=0.5).start(l),3.0)
        Clock.schedule_once(lambda dt,l=lbl:self.remove_widget(l) if l.parent else None,3.8)
    def _rebg(self,lbl):
        lbl.canvas.before.clear(); pal=P()
        with lbl.canvas.before:
            Color(*pal["glow"],0.20); RoundedRectangle(pos=lbl.pos,size=lbl.size,radius=[12])
            Color(*pal["primary"],0.80); Line(rounded_rectangle=(*lbl.pos,*lbl.size,12),width=1.2)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════════════════════════════════════

class VedaApp(App):
    title="VEDA v12 — Dharma Cyber Edition"

    def build(self):
        Window.clearcolor=(*SURYA_NET["bg"],1)
        root=FloatLayout()

        # ── Cyber grid background ────────────────────────────────────────
        self._grid=CyberGrid(size_hint=(1,1),pos_hint={"x":0,"y":0})
        root.add_widget(self._grid)

        main=BoxLayout(orientation="horizontal",size_hint=(1,1))

        # ════════════════════════════════════════════════════════
        # LEFT PANEL
        # ════════════════════════════════════════════════════════
        left=BoxLayout(orientation="vertical",size_hint=(0.54,1))

        # ── Header ───────────────────────────────────────────────
        hdr=BoxLayout(orientation="horizontal",size_hint=(1,None),height=46,padding=[12,5])
        with hdr.canvas.before:
            self._hdr_c=Color(*SURYA_NET["bg2"],1)
            self._hdr_r=Rectangle(pos=hdr.pos,size=hdr.size)
        hdr.bind(pos=lambda i,v:setattr(self._hdr_r,"pos",v),
                 size=lambda i,v:setattr(self._hdr_r,"size",v))

        self.lbl_top=Label(text="[b]V·E·D·A[/b]",markup=True,font_size=20,
                           color=(*SURYA_NET["primary"],1),size_hint=(None,1),
                           width=120,halign="left",valign="middle")
        self.lbl_badge=Label(text="☀ SURYA NET",font_size=11,bold=True,
                             color=(*SURYA_NET["sub"],1),size_hint=(1,1),
                             halign="center",valign="middle")
        hdr_right=BoxLayout(spacing=8,size_hint=(None,1),width=230)
        self.conn_dot=ConnDot(size_hint=(None,None),width=16,height=16)
        self.lbl_net=Label(text="● SURYA",font_size=10,bold=True,
                           color=(*SURYA_NET["primary"],1),size_hint=(None,1),width=68)
        self.clock=LiveClock(font_size=11,size_hint=(None,1),width=76,halign="right")

        # Sys monitor compact display
        self.lbl_sys=Label(text="CPU:-- RAM:--",font_size=9,
                           color=(*SURYA_NET["muted"],1),size_hint=(None,1),width=90)

        # AI Chat toggle button
        self.btn_chat=Button(text="💬",font_size=13,size_hint=(None,1),width=34,
                             background_color=(*SURYA_NET["accent"],0.80),color=(1,1,1,1))
        self.btn_chat.bind(on_press=self._toggle_ai_chat)

        hdr_right.add_widget(self.lbl_sys)
        hdr_right.add_widget(self.conn_dot)
        hdr_right.add_widget(self.lbl_net)
        hdr_right.add_widget(self.clock)
        hdr_right.add_widget(self.btn_chat)
        hdr.add_widget(self.lbl_top); hdr.add_widget(self.lbl_badge); hdr.add_widget(hdr_right)
        left.add_widget(hdr)

        # ── Visualiser ───────────────────────────────────────────
        self.vis=Visualiser(size_hint=(1,1))
        left.add_widget(self.vis)

        # ── Sys Monitor mini widget ───────────────────────────────
        self.sysmon=SysMonWidget(size_hint=(1,None),height=52)
        left.add_widget(self.sysmon)

        # ── Mode + status labels ──────────────────────────────────
        mid=BoxLayout(orientation="vertical",size_hint=(1,None),height=64,padding=[0,4])
        self.lbl_mode_main=Label(text="V  E  D  A",font_size=30,bold=True,
                                 color=(*SURYA_NET["primary"],1),
                                 size_hint=(1,None),height=40,halign="center")
        self.lbl_mode_sub=Label(text="Connected · Solar Grid Online",font_size=11,italic=True,
                                color=(*SURYA_NET["sub"],0.80),
                                size_hint=(1,None),height=18,halign="center")
        mid.add_widget(self.lbl_mode_main); mid.add_widget(self.lbl_mode_sub)
        left.add_widget(mid)

        # ── Status + heard ────────────────────────────────────────
        st=BoxLayout(orientation="vertical",size_hint=(1,None),height=40,padding=[10,2])
        self.lbl_status=Label(text="Initializing…",font_size=12,italic=True,
                              color=(*SURYA_NET["text"],1),size_hint=(1,None),height=20,halign="center")
        self.lbl_heard=Label(text="",font_size=10,italic=True,
                             color=(*SURYA_NET["sub"],0.70),size_hint=(1,None),height=16,halign="center")
        st.add_widget(self.lbl_status); st.add_widget(self.lbl_heard)
        left.add_widget(st)

        # ── Mic bar ───────────────────────────────────────────────
        self.mic_bar=MicBar(size_hint=(1,None),height=18)
        left.add_widget(self.mic_bar)

        # ── Mode slider ───────────────────────────────────────────
        sr=BoxLayout(orientation="horizontal",spacing=8,
                     size_hint=(1,None),height=32,padding=[12,2])
        self.lbl_sl=Label(text="☀ SURYA NET",font_size=9,bold=True,
                          color=(*SURYA_NET["primary"],1),size_hint=(0.32,1),halign="center")
        self.slider=ModeSlider(size_hint=(0.36,1))
        self.lbl_sr=Label(text="🌑 NIRVANA",font_size=9,bold=True,
                          color=(*NIRVANA_MODE["primary"],1),size_hint=(0.32,1),halign="center")
        sr.add_widget(self.lbl_sl); sr.add_widget(self.slider); sr.add_widget(self.lbl_sr)
        left.add_widget(sr)

        # ── Personality + Language quick buttons ──────────────────
        quick=BoxLayout(orientation="horizontal",spacing=4,
                        size_hint=(1,None),height=26,padding=[8,0])
        for lbl,cmd,col in [("🧘 Calm","personality calm",(0.20,0.62,0.80,0.75)),
                             ("⚡ Energy","personality energetic",(1.0,0.50,0.05,0.75)),
                             ("🕉 Guru","personality guru",(0.55,0.20,0.90,0.75)),
                             ("EN","language english",(0.10,0.50,0.20,0.72)),
                             ("HI","language hindi",(0.80,0.15,0.15,0.72))]:
            b=Button(text=lbl,font_size=9,bold=True,
                     background_color=col,color=(1,1,1,1))
            c2=cmd
            b.bind(on_press=lambda *_,c=c2:threading.Thread(target=execute,args=(c,),daemon=True).start())
            quick.add_widget(b)
        left.add_widget(quick)

        # ── Action buttons ────────────────────────────────────────
        br=BoxLayout(orientation="horizontal",spacing=4,
                     size_hint=(1,None),height=28,padding=[8,0])
        for lbl,fn,col in [
            ("📋 Help",   self._show_help,   (*SURYA_NET["primary"],0.75)),
            ("ℹ Cmds",   self._show_cmds,   (*SURYA_NET["accent"],0.75)),
            ("🎙 Calib",  self._calibrate,   (0.16,0.52,0.26,0.80)),
            ("📸 Vision", self._screenshot,  (0.12,0.35,0.65,0.80)),
            ("⏰ Remind", self._show_reminders,(0.60,0.12,0.80,0.75)),
        ]:
            b=Button(text=lbl,font_size=9,bold=True,
                     background_color=col,color=(1,1,1,1) if col[0]<0.8 else (0,0,0,1))
            b.bind(on_press=fn)
            br.add_widget(b)
        left.add_widget(br)

        # ── Input bar ─────────────────────────────────────────────
        inp=BoxLayout(orientation="horizontal",spacing=5,
                      size_hint=(1,None),height=42,padding=[8,4])
        self.txt=TextInput(
            hint_text="Type command or ask anything… (multi-cmd: use 'and')",
            multiline=False,font_size=12,
            background_color=(0.08,0.04,0.01,0.95),
            foreground_color=(*SURYA_NET["text"],1),
            hint_text_color=(*SURYA_NET["sub"],0.35),
            cursor_color=(*SURYA_NET["primary"],1),padding=[10,10])
        self.txt.bind(on_text_validate=self._on_type)
        self.btn_go=Button(text="GO",font_size=11,bold=True,
                           size_hint=(None,1),width=46,
                           background_color=(*SURYA_NET["accent"],1),color=(1,1,1,1))
        self.btn_go.bind(on_press=self._on_type)
        inp.add_widget(self.txt); inp.add_widget(self.btn_go)
        left.add_widget(inp)
        main.add_widget(left)

        # ════════════════════════════════════════════════════════
        # RIGHT PANEL — Tabbed: Samvaad | History | Reminders | Sysmon
        # ════════════════════════════════════════════════════════
        right=BoxLayout(orientation="vertical",size_hint=(0.46,1))

        # Tab header
        tab_hdr=BoxLayout(orientation="horizontal",size_hint=(1,None),height=36,padding=[6,3],spacing=2)
        with tab_hdr.canvas.before:
            self._thdr_c=Color(*SURYA_NET["bg2"],1)
            self._thdr_r=Rectangle(pos=tab_hdr.pos,size=tab_hdr.size)
        tab_hdr.bind(pos=lambda i,v:setattr(self._thdr_r,"pos",v),
                     size=lambda i,v:setattr(self._thdr_r,"size",v))

        self._tabs_btns=[]
        self._tab_names=["◈ Samvaad","📜 History","⏰ Reminders","💻 SysMon"]
        self._active_tab=0
        for i,n in enumerate(self._tab_names):
            b=Button(text=n,font_size=9,bold=True,
                     background_color=(*SURYA_NET["primary"],0.75) if i==0 else (*SURYA_NET["muted"],0.50),
                     color=(0,0,0,1) if i==0 else (*SURYA_NET["sub"],1))
            ii=i
            b.bind(on_press=lambda *_,idx=ii:self._switch_tab(idx))
            self._tabs_btns.append(b); tab_hdr.add_widget(b)

        # Clear + mode tag
        self.chat_mode_tag=Label(text="● SURYA",font_size=9,bold=True,
                                 color=(*SURYA_NET["primary"],1),
                                 size_hint=(None,1),width=58)
        btn_clr=Button(text="🗑",font_size=11,size_hint=(None,1),width=30,
                       background_color=(0.10,0.04,0.02,1),color=(*SURYA_NET["sub"],1))
        btn_clr.bind(on_press=lambda *_:self._clear_active_tab())
        tab_hdr.add_widget(self.chat_mode_tag); tab_hdr.add_widget(btn_clr)
        right.add_widget(tab_hdr)

        # Divider
        self._div=Widget(size_hint=(1,None),height=2)
        with self._div.canvas:
            self._dc=Color(*SURYA_NET["divider"],1)
            self._dr=Rectangle(pos=self._div.pos,size=self._div.size)
        self._div.bind(pos=lambda i,v:setattr(self._dr,"pos",v),
                       size=lambda i,v:setattr(self._dr,"size",v))
        right.add_widget(self._div)

        # Tab content area
        self._tab_host=FloatLayout(size_hint=(1,1))

        # Tab 0: Main chat (Samvaad)
        self.chat=ChatLog(size_hint=(1,1),pos_hint={"x":0,"y":0},
                          bar_color=(*SURYA_NET["accent"],0.5),
                          bar_inactive_color=(*SURYA_NET["sub"],0.3))
        self._tab_host.add_widget(self.chat)

        # Tab 1: History
        self._history_log=ChatLog(size_hint=(1,1),pos_hint={"x":0,"y":0},
                                  opacity=0)
        self._tab_host.add_widget(self._history_log)

        # Tab 2: Reminders panel
        self._reminder_panel=BoxLayout(orientation="vertical",
                                       size_hint=(1,1),pos_hint={"x":0,"y":0},
                                       opacity=0,padding=[10,8],spacing=6)
        self._reminder_scroll=ScrollView(size_hint=(1,1))
        self._reminder_box=BoxLayout(orientation="vertical",size_hint_y=None,spacing=5,padding=[4,4])
        self._reminder_box.bind(minimum_height=self._reminder_box.setter("height"))
        self._reminder_scroll.add_widget(self._reminder_box)
        # New reminder input
        ri=BoxLayout(size_hint=(1,None),height=36,spacing=5)
        self._rem_txt=TextInput(hint_text="e.g. in 10 minutes to call mom",
                                multiline=False,font_size=11,
                                background_color=(0.08,0.04,0.01,0.9),
                                foreground_color=(*SURYA_NET["text"],1),
                                padding=[8,8])
        self._rem_txt.bind(on_text_validate=self._add_reminder)
        rb=Button(text="Set",font_size=10,bold=True,size_hint=(None,1),width=40,
                  background_color=(*SURYA_NET["accent"],0.9),color=(1,1,1,1))
        rb.bind(on_press=self._add_reminder)
        ri.add_widget(self._rem_txt); ri.add_widget(rb)
        self._reminder_panel.add_widget(ri)
        self._reminder_panel.add_widget(self._reminder_scroll)
        self._tab_host.add_widget(self._reminder_panel)

        # Tab 3: System monitor large
        self._sysmon_large=BoxLayout(orientation="vertical",
                                     size_hint=(1,1),pos_hint={"x":0,"y":0},
                                     opacity=0,padding=[10,8],spacing=8)
        self._cpu_lbl=Label(text="CPU: --",font_size=14,bold=True,
                            color=(*SURYA_NET["primary"],1),size_hint=(1,None),height=24)
        self._ram_lbl=Label(text="RAM: --",font_size=14,bold=True,
                            color=(*SURYA_NET["teal"],1),size_hint=(1,None),height=24)
        self._batt_lbl=Label(text="Battery: --",font_size=14,bold=True,
                             color=(*SURYA_NET["sub"],1),size_hint=(1,None),height=24)
        self._sysmon_graph=SysMonWidget(size_hint=(1,1))
        self._sysmon_large.add_widget(self._cpu_lbl)
        self._sysmon_large.add_widget(self._ram_lbl)
        self._sysmon_large.add_widget(self._batt_lbl)
        self._sysmon_large.add_widget(self._sysmon_graph)
        self._tab_host.add_widget(self._sysmon_large)

        right.add_widget(self._tab_host)

        # Source legend
        legend=BoxLayout(size_hint=(1,None),height=20,padding=[8,1],spacing=10)
        for s,n in [("AI","GPT-4"),("Web","Google"),("Vosk","Offline STT"),("Local","Built-in")]:
            legend.add_widget(Label(text=f"[color=#666666][{s}]={n}[/color]",markup=True,
                                    font_size=8,size_hint=(None,1),width=80))
        right.add_widget(legend)
        main.add_widget(right)

        root.add_widget(main)

        # Floating AI chat panel
        self._ai_panel=FloatingChatPanel(size_hint=(1,1),pos_hint={"x":0,"y":0})
        root.add_widget(self._ai_panel)

        # Toast overlay
        self._toast=ToastOverlay(size_hint=(1,1),pos_hint={"x":0,"y":0})
        Clock.schedule_once(lambda dt:Window.add_widget(self._toast),0.5)

        # Theme tick
        Clock.schedule_interval(self._theme_tick,1/12)

        return root

    # ── Tab switching ────────────────────────────────────────────────────────
    _tab_widgets=None
    def _get_tab_widgets(self):
        if self._tab_widgets is None:
            self._tab_widgets=[self.chat,self._history_log,
                               self._reminder_panel,self._sysmon_large]
        return self._tab_widgets

    def _switch_tab(self,idx):
        self._active_tab=idx
        pal=P()
        for i,w in enumerate(self._get_tab_widgets()):
            w.opacity=1.0 if i==idx else 0.0
        for i,b in enumerate(self._tabs_btns):
            b.background_color=(*pal["primary"],0.80) if i==idx else (*pal["muted"],0.45)
            b.color=(0,0,0,1) if i==idx else (*pal["sub"],1)
        if idx==1: self._load_history()
        if idx==2: self._refresh_reminders()

    def _clear_active_tab(self):
        if self._active_tab==0: self.chat.clear()
        elif self._active_tab==1: self._history_log.clear()
        elif self._active_tab==2: self._reminder_box.clear_widgets()

    # ── History ──────────────────────────────────────────────────────────────
    def _load_history(self):
        self._history_log.clear()
        rows=db_load_history(60)
        for role,content,src in rows:
            r="you" if role=="user" else "ai"
            w="YOU" if role=="user" else "VEDA"
            self._history_log.add_bubble(w,r,content[:120],src)

    # ── Reminders UI ─────────────────────────────────────────────────────────
    def _refresh_reminders(self):
        self._reminder_box.clear_widgets()
        pal=P()
        rows=db_get_reminders()
        if not rows:
            l=Label(text="No pending reminders",font_size=12,italic=True,
                    color=(*pal["sub"],0.6),size_hint=(1,None),height=30)
            self._reminder_box.add_widget(l); return
        for rid,ts,label in rows:
            row=BoxLayout(size_hint=(1,None),height=32,spacing=4)
            try: dt=datetime.datetime.fromisoformat(ts); ts_show=dt.strftime("%d %b %H:%M")
            except: ts_show=ts[:16]
            l=Label(text=f"[b]{label}[/b]  [{ts_show}]",markup=True,
                    font_size=11,color=(*pal["text"],1),size_hint=(1,1),halign="left")
            bdone=Button(text="✓",font_size=10,size_hint=(None,1),width=28,
                         background_color=(0.15,0.65,0.25,0.8),color=(1,1,1,1))
            _rid=rid
            bdone.bind(on_press=lambda *_,r=_rid:self._done_reminder(r))
            row.add_widget(l); row.add_widget(bdone)
            self._reminder_box.add_widget(row)

    def _add_reminder(self,*_):
        t=self._rem_txt.text.strip()
        if t:
            self._rem_txt.text=""
            result=_parse_reminder("remind me "+t)
            self.show_toast(result)
            self._refresh_reminders()

    def _done_reminder(self,rid):
        db_done_reminder(rid); self._refresh_reminders()

    def reminder_due(self,label):
        self.show_toast(f"⏰ {label}")
        if self._active_tab==2: self._refresh_reminders()

    # ── Screenshot ───────────────────────────────────────────────────────────
    def _screenshot(self,*_):
        def _do():
            speak("Taking screenshot.")
            result=_screenshot_describe("")
            speak(result[:220])
        threading.Thread(target=_do,daemon=True).start()

    # ── Show reminders panel ──────────────────────────────────────────────────
    def _show_reminders(self,*_): self._switch_tab(2)

    # ── Theme tick ───────────────────────────────────────────────────────────
    def _theme_tick(self,dt):
        with _MORPH_LOCK: mt=_MORPH
        prev=getattr(self,"_last_mt",None)
        if prev is None or abs(mt-prev)>0.004:
            self._apply_theme()
        self._last_mt=mt

    def _apply_theme(self):
        pal=P()
        for w in [self.lbl_top,self.lbl_mode_main]:
            w.color=(*pal["primary"],1)
        self.lbl_badge.color        =(*pal["sub"],1)
        self.lbl_mode_sub.color     =(*pal["sub"],0.80)
        self.lbl_status.color       =(*pal["text"],1)
        self.lbl_heard.color        =(*pal["sub"],0.70)
        self.btn_go.background_color=(*pal["accent"],1)
        self._dc.rgba               =(*pal["divider"],1)
        self._hdr_c.rgba            =(*pal["bg2"],1)
        self._thdr_c.rgba           =(*pal["bg2"],1)
        Window.clearcolor           =(*pal["bg"],1)
        bg=(0.07,0.02,0.11,0.95) if _active_mode()=="nirvana" else (0.08,0.04,0.01,0.95)
        self.txt.background_color   =bg
        self.txt.foreground_color   =(*pal["text"],1)
        self.txt.hint_text_color    =(*pal["sub"],0.35)
        self.txt.cursor_color       =(*pal["primary"],1)
        # Sysmon labels
        self._cpu_lbl.color         =(*pal["primary"],1)
        self._ram_lbl.color         =(*pal["teal"],1)
        self._batt_lbl.color        =(*pal["sub"],1)

    # ── App lifecycle ─────────────────────────────────────────────────────────
    def on_start(self):
        threading.Thread(target=_stt_worker,   daemon=True).start()
        threading.Thread(target=_tts_worker,   daemon=True).start()
        threading.Thread(target=voice_loop,    daemon=True).start()
        threading.Thread(target=_sysmon_worker,daemon=True).start()
        threading.Thread(target=_reminder_worker,daemon=True).start()

    # ── Input ─────────────────────────────────────────────────────────────────
    def _on_type(self,*_):
        t=self.txt.text.strip()
        if t:
            self.txt.text=""
            threading.Thread(target=execute,args=(t,),daemon=True).start()

    # ── Help / Cmds ───────────────────────────────────────────────────────────
    def _show_help(self,*_):
        self._switch_tab(0); self.chat.clear()
        for l in [
            "══ VEDA v12 — DHARMA CYBER EDITION ══",
            "WAKE: Hey Veda / Ok Veda",
            "MULTI-TASK: 'open youtube and search X' ✓",
            "AI CHAT: 💬 button → floating panel (streaming!)",
            "PERSONALITY: say 'personality calm/energetic/guru'",
            "LANGUAGE: say 'language hindi' or 'language english'",
            "SYSTEM: say 'cpu' / 'system status' / 'battery'",
            "SPOTIFY: say 'media pause/next/previous/now playing'",
            "VISION: say 'screenshot' / 📸 button",
            "REMIND: say 'remind me in 10 minutes to call mom'",
            "WAKE TRAINER: say 'train wake word [phrase]'",
            "BRIEFING: say 'morning briefing'",
            "HISTORY: 📜 tab → full conversation history",
            "MODE: say 'surya net' (online) / 'nirvana' (offline)",
            "EXIT: say 'goodbye'"]: self.chat.add_bubble("SYS","sys",l,"")

    def _show_cmds(self,*_):
        self._switch_tab(0); self.chat.clear()
        for c in [
            "══ COMMAND LIST ══",
            "WEATHER   → weather in [city]",
            "SEARCH    → search for [query]",
            "YOUTUBE   → open youtube and search [query]",
            "APP       → open/launch/close [app]",
            "VOLUME    → volume up/down/mute/[0-100]",
            "TIMER     → set timer for [N] sec/min/hr",
            "REMIND    → remind me in [N] min to [label]",
            "MEMORY    → remember X is Y / what is X",
            "CALC      → calculate [expression]",
            "PC        → shutdown/restart pc | cancel",
            "MEDIA     → media pause/next/previous/now playing",
            "VISION    → screenshot / describe screen",
            "BRIEFING  → morning briefing",
            "MODE      → surya net | nirvana mode",
            "MULTI     → [cmd1] and [cmd2] and [cmd3]"]: self.chat.add_bubble("SYS","sys",c,"")

    def _calibrate(self,*_):
        def _do():
            speak("Calibrating. Please be silent for 2 seconds.")
            time.sleep(0.5)
            try:
                with sr.Microphone() as src: _rec.adjust_for_ambient_noise(src,2.0)
                db_save_noise(_rec.energy_threshold)
                speak(f"Done. Threshold {int(_rec.energy_threshold)}.")
                _ui("toast",f"🎙 Calibrated — {int(_rec.energy_threshold)}")
            except: speak("Calibration failed.")
        threading.Thread(target=_do,daemon=True).start()

    # ── Public API ────────────────────────────────────────────────────────────
    def set_status(self,text): self.lbl_status.text=text
    def set_heard(self,text):
        short=text[:58]+("…" if len(text)>58 else "")
        self.lbl_heard.text=f'"{short}"'
    def set_energy(self,e):
        self.mic_bar.set_energy(e); self.vis.set_energy(e)
    def set_online_dot(self,v):
        self.conn_dot.set_online(v)
        self.lbl_net.text=("● SURYA" if v else "○ NIRVANA")
        self.lbl_net.color=(*(( 0.12,1.0,0.42) if v else (1.0,0.25,0.15)),1)
        self.chat_mode_tag.text=("● SURYA" if v else "○ NIRVANA")
    def show_toast(self,text): self._toast.show(text)
    def add_bubble(self,who,role,text,src): self.chat.add_bubble(who,role,text,src)

    def update_sysmon(self,data):
        self.sysmon.update(data)
        self._sysmon_graph.update(data)
        cpu=data.get("cpu",0); ram=data.get("ram",0)
        batt=data.get("batt",-1); plug=data.get("plug",True)
        self.lbl_sys.text=f"CPU:{cpu:.0f}% RAM:{ram:.0f}%"
        self._cpu_lbl.text=f"CPU: {cpu:.1f}%"
        self._ram_lbl.text=f"RAM: {ram:.1f}%"
        if batt>=0:
            self._batt_lbl.text=f"Battery: {batt}% {'⚡' if plug else '🔋'}"

    def stream_chunk(self,chunk):
        if chunk=="__START__": self.chat.start_stream()
        else: self.chat.append_stream(chunk)
    def stream_end(self): self.chat.end_stream()
    def update_media(self,data): pass  # extend as needed

    def _toggle_ai_chat(self,*_): self._ai_panel.toggle()

    def set_state(self,state):
        self.vis.set_state(state)
        self.lbl_status.text={
            "listening":"🎙  Listening…",
            "speaking" :"🔊  Speaking…",
            "thinking" :"💭  Processing…",
            "ready"    :"◈  Ready — say Hey Veda",
        }.get(state,state)
        if state=="ready": self.lbl_heard.text=""

    def set_mode(self,mode):
        pal=P()
        self.vis.set_mode(mode); self.slider.set_mode(mode)
        if mode=="surya":
            self.lbl_badge.text    ="☀  SURYA NET"
            self.lbl_mode_sub.text ="Connected · Solar Grid Online"
            self.chat_mode_tag.text="● SURYA"
            self.chat.add_bubble("SYS","sys","⚡ SURYA NET — Online!","")
        else:
            self.lbl_badge.text    ="🌑  NIRVANA MODE"
            self.lbl_mode_sub.text ="Offline · Silent Void"
            self.chat_mode_tag.text="○ NIRVANA"
            self.chat.add_bubble("SYS","sys","🌌 NIRVANA MODE — Offline.","")


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY
# ═══════════════════════════════════════════════════════════════════════════════

if __name__=="__main__":
    try:
        # ← Paste your OpenAI key here:
        # OPENAI_API_KEY = "sk-proj-..."
        # CFG["openai_key"] = OPENAI_API_KEY; _save_cfg(CFG)
        VedaApp().run()
    except Exception as e:
        import traceback
        print("\n[CRASH]",e); traceback.print_exc()
        input("\nPress Enter to close…")