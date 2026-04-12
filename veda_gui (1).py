"""
VEDA v15.3 Zenith Edition - GUI
Run: python veda_gui.py
All bugs fixed:
  • QuickPanel pos conflict resolved (no pos_hint, manual pos only)
  • Tab panel closure bug fixed (each panel gets its own bg rect reference)
  • ConnDot._check fixed (no bad lambda)
  • _apply_theme covers all color refs including _irc/_irr
  • FloatLayout tab panels use disabled=True to block touch on hidden panels
  • Tab active highlight uses proper rgba update
  • Quick panel card borders use correct lambda closures
  • AI panel positioned correctly after Window is ready
  • _ui bridge works via App.get_running_app() (no registration needed)
"""
from kivy.config import Config
Config.set("graphics","resizable","1")
Config.set("graphics","width","1440")
Config.set("graphics","height","860")

import veda as _vb
from veda import (
    CFG, _save_cfg, _APP_RUNNING,
    P, SURYA_NET, NIRVANA_MODE, _MORPH_LOCK, _lerp, _lc, _hsv,
    db_save_chat, db_load_history, db_get_reminders,
    db_done_reminder, db_load_noise, db_save_noise,
    _tts_worker, _stt_worker, _sysmon_worker, _reminder_worker, voice_loop,
    _seed_knowledge, execute, speak, _rec,
    _active_mode, _set_surya, _set_nirvana, _vosk_status,
    ask_chatgpt, _ping, _ui, _wait_tts, _parse_reminder,
)

import threading, time, math, random, datetime
import speech_recognition as sr

from kivy.app             import App
from kivy.uix.widget      import Widget
from kivy.uix.boxlayout   import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview  import ScrollView
from kivy.uix.label       import Label
from kivy.uix.button      import Button
from kivy.uix.textinput   import TextInput
from kivy.graphics        import Color, Line, Ellipse, Rectangle, RoundedRectangle
from kivy.clock           import Clock
from kivy.core.window     import Window
from kivy.animation       import Animation

# ── Design tokens ─────────────────────────────────────────────────────────────
_S = dict(
    bg=(0.04,0.03,0.01), bg2=(0.08,0.05,0.01), card=(0.11,0.06,0.02),
    card2=(0.16,0.09,0.03), primary=(1.00,0.78,0.08), accent=(1.00,0.30,0.04),
    glow=(1.00,0.55,0.00), teal=(0.00,0.88,0.76), text=(1.00,0.93,0.70),
    sub=(0.70,0.46,0.14), muted=(0.30,0.16,0.05), divider=(0.22,0.12,0.03),
    you_col=(1.00,0.74,0.16), ai_col=(1.00,0.93,0.70), sys_col=(0.50,0.30,0.08),
    tab_act=(0.22,0.12,0.02), online=(0.16,1.00,0.44), offline=(1.00,0.24,0.14),
)
_N = dict(
    bg=(0.01,0.01,0.08), bg2=(0.03,0.02,0.13), card=(0.06,0.04,0.18),
    card2=(0.09,0.06,0.24), primary=(0.62,0.20,1.00), accent=(0.00,0.88,0.84),
    glow=(0.40,0.06,0.86), teal=(0.00,0.88,0.84), text=(0.84,0.70,1.00),
    sub=(0.48,0.30,0.78), muted=(0.20,0.12,0.38), divider=(0.14,0.08,0.30),
    you_col=(0.55,0.22,0.96), ai_col=(0.00,0.88,0.84), sys_col=(0.32,0.18,0.52),
    tab_act=(0.10,0.07,0.24), online=(0.16,1.00,0.44), offline=(1.00,0.24,0.14),
)

def T():
    with _MORPH_LOCK: mt = _vb._MORPH
    if mt < 0.01: return _S
    if mt > 0.99: return _N
    out = {}
    for k in _S:
        sv, nv = _S[k], _N[k]
        out[k] = tuple(_lerp(sv[i], nv[i], mt) for i in range(len(sv)))
    return out

def _hx(c):
    return "{:02x}{:02x}{:02x}".format(
        max(0,min(255,int(c[0]*255))),
        max(0,min(255,int(c[1]*255))),
        max(0,min(255,int(c[2]*255))))

# ── Particles ─────────────────────────────────────────────────────────────────
class _Particle:
    __slots__ = ("x","y","vx","vy","life","ml","sz")
    def __init__(self,m,W,H): self.reset(m,W,H)
    def reset(self,m,W,H):
        self.x=random.uniform(0,W); self.y=random.uniform(0,H)
        if m=="surya":
            self.vx=random.uniform(-0.12,0.12); self.vy=random.uniform(0.15,0.70)
            self.life=random.uniform(0.3,1.0); self.sz=random.uniform(1.2,2.8)
        else:
            self.vx=random.uniform(-0.05,0.05); self.vy=random.uniform(-0.05,0.05)
            self.life=random.uniform(0.1,1.0); self.sz=random.uniform(0.8,2.0)
        self.ml=self.life
    def update(self,dt,m,W,H):
        self.x+=self.vx; self.y+=self.vy
        if m=="surya":
            self.life-=dt*0.38
            if self.life<=0 or self.y>H+5: self.reset(m,W,H); self.y=0
        else:
            self.life+=dt*random.choice((-1,1))*0.14
            self.life=max(0.05,min(self.ml,self.life))
            if not(0<=self.x<=W and 0<=self.y<=H): self.reset(m,W,H)

# ── Visualiser ────────────────────────────────────────────────────────────────
class Visualiser(Widget):
    def __init__(self,**kw):
        super().__init__(**kw)
        self.mode="surya"; self.state="ready"
        self._t=0.0; self._pulse=0.0; self._pdir=1
        self._energy=0.0; self._wave=[0.0]*64
        self._dots=[]; self._parts=[]; self._last_size=(0,0)
        self._blob_phase=[random.uniform(0,math.tau) for _ in range(64)]
        self._blob_freq=[random.uniform(0.8,2.4) for _ in range(64)]
        self._wake_flash=0.0; self._thinking_t=0.0
        Clock.schedule_once(self._init_p,0.3)
        Clock.schedule_interval(self._tick,1/60)
        self.bind(size=self._on_resize)

    def _on_resize(self,*_):
        sz=(int(self.width),int(self.height))
        if sz!=self._last_size and sz[0]>10:
            self._last_size=sz; Clock.schedule_once(self._init_p,0.1)

    def _init_p(self,dt):
        W,H=max(self.width,300),max(self.height,300); R=min(W,H)*0.32
        self._dots=[[random.uniform(0,math.tau),R*random.uniform(1.12,1.85),
                     random.uniform(0.002,0.007)*random.choice((-1,1)),
                     random.uniform(1.0,3.2),random.uniform(0.1,1.0),
                     random.uniform(0.012,0.050)] for _ in range(55)]
        self._parts=[_Particle(self.mode,W,H) for _ in range(35)]

    def set_mode(self,m):
        self.mode=m
        for p in self._parts: p.reset(m,self.width,self.height)

    def set_state(self,s):
        self.state=s
        if s!="thinking": self._thinking_t=0.0

    def set_energy(self,e): self._energy=e
    def wake_flash(self): self._wake_flash=1.0

    def _tick(self,dt):
        self._t+=dt
        self._pulse+=dt*1.8*self._pdir
        if self._pulse>=1: self._pdir=-1
        if self._pulse<=0: self._pdir=1
        for d in self._dots:
            d[0]+=d[2]; d[4]+=d[5]
            if d[4]>1.0 or d[4]<0.05: d[5]*=-1
        W,H=self.width,self.height
        for p in self._parts: p.update(dt,self.mode,W,H)
        amp=(0.55+self._energy*0.45) if self.state=="listening" else \
            (0.80 if self.state=="speaking" else 0.06)
        ns=amp*abs(math.sin(self._t*10.5+random.uniform(-0.2,0.2)))
        self._wave=self._wave[1:]+[ns]
        for i in range(64): self._blob_phase[i]+=dt*self._blob_freq[i]*1.8
        if self._wake_flash>0: self._wake_flash=max(0.0,self._wake_flash-dt*3.5)
        if self.state=="thinking": self._thinking_t+=dt
        self._draw()

    def _draw(self):
        self.canvas.clear(); pal=T(); W,H=self.width,self.height
        if W<2 or H<2: return
        cx=self.center_x; cy=self.center_y; R=min(W,H)*0.32
        sc={"listening":(0.12,1.00,0.48),"thinking":(0.95,0.88,0.08),
            "speaking":pal["accent"]}.get(self.state,pal["primary"])
        with self.canvas:
            Color(*pal["bg"],1); Rectangle(pos=self.pos,size=self.size)
            for p in self._parts:
                Color(*pal["accent"],p.life*0.15)
                Ellipse(pos=(p.x-p.sz/2,p.y-p.sz/2),size=(p.sz,p.sz))
            for d in self._dots:
                ox=cx+d[1]*math.cos(d[0]); oy=cy+d[1]*math.sin(d[0])
                Color(*pal["primary"],d[4]*0.22)
                Ellipse(pos=(ox-d[3]/2,oy-d[3]/2),size=(d[3],d[3]))
            with _MORPH_LOCK: mt=_vb._MORPH
            if mt<0.99: self._surya(cx,cy,R,pal,sc,1.0-mt)
            if mt>0.01: self._nirvana(cx,cy,R,pal,sc,mt)
            self._blob(cx,cy,R*0.50,pal,sc)
            if self._energy>0.02:
                er=R*(1.06+self._energy*0.18); Color(*sc,self._energy*0.60)
                Line(circle=(cx,cy,er),width=1.8+self._energy*3.0)
            if self._wake_flash>0:
                wf=self._wake_flash; Color(1.0,0.85,0.10,wf*0.30)
                Ellipse(pos=(cx-R*1.3,cy-R*1.3),size=(R*2.6,R*2.6))
                Color(1.0,0.85,0.10,wf*0.85); Line(circle=(cx,cy,R),width=2.2+wf*3.5)
            n=8; br=R*1.10
            pr=R*(0.09+(0.04 if self.state in("listening","speaking") else 0)+self._energy*0.04)
            for i in range(n):
                a=i*math.tau/n+self._t*0.18
                Color(*pal["glow"],0.22+0.18*abs(math.sin(self._t*1.3+i*math.pi/n)))
                Ellipse(pos=(cx+br*math.cos(a)-pr,cy+br*math.sin(a)-pr),size=(pr*2,pr*2))
            nw=len(self._wave); w2=R*0.44
            if self.state in("listening","speaking"):
                pts=[]; pts2=[]
                for i,s in enumerate(self._wave):
                    x=cx-w2+(i/(nw-1))*w2*2; env=math.sin(math.pi*i/(nw-1)); h=s*R*0.22*env
                    pts.extend([x,cy+h]); pts2.extend([x,cy-h])
                Color(*pal["primary"],0.92)
                if len(pts)>=4: Line(points=pts,width=2.0)
                Color(*pal["accent"],0.50)
                if len(pts2)>=4: Line(points=pts2,width=1.2)
            if self.state=="thinking":
                sp=R*0.22; yd=cy+R*1.34
                for i in range(3):
                    ph=self._t*3.2+i*(math.tau/3); sc2=0.4+0.6*abs(math.sin(ph)); dr=R*0.042*sc2
                    Color(*pal["primary"],0.50+0.44*sc2)
                    Ellipse(pos=(cx+(i-1)*sp-dr,yd-dr),size=(dr*2,dr*2))

    def _blob(self,cx,cy,R,pal,sc):
        N=64; e=self._energy; t=self._t; pts=[]
        for i in range(N):
            ang=i*math.tau/N; phase=self._blob_phase[i]; freq=self._blob_freq[i]
            amp=e*(0.24+0.14*math.sin(phase+freq*t))+(0.04 if self.state!="ready" else 0.01)
            r2=R*(0.62+amp+self._wake_flash*0.18)
            pts.extend([cx+r2*math.cos(ang),cy+r2*math.sin(ang)])
        if pts:
            pts.extend(pts[:2]); bc=_lc(pal["teal"],pal["primary"],min(1.0,e*2))
            Color(*bc,0.70+e*0.28); Line(points=pts,width=1.5+self._wake_flash*2.8,close=True)
            Color(*bc,0.05+e*0.07); Ellipse(pos=(cx-R*0.70,cy-R*0.70),size=(R*1.4,R*1.4))

    def _surya(self,cx,cy,R,pal,sc,alpha):
        t=self._t; pu=self._pulse; a=alpha
        with self.canvas:
            for fr,ba in [(1.50,0.025),(1.30,0.050),(1.12,0.085),(1.02,0.120)]:
                Color(*sc,min(1.0,(ba+pu*0.03)*a)); Ellipse(pos=(cx-R*fr,cy-R*fr),size=(R*fr*2,R*fr*2))
            Color(*pal["bg"],a); Ellipse(pos=(cx-R,cy-R),size=(R*2,R*2))
            for fr,col,ba in [(0.90,pal["glow"],0.18+pu*0.06),(0.72,pal["primary"],0.22+pu*0.07),
                              (0.52,pal["accent"],0.28+pu*0.09),(0.30,pal["glow"],0.35+pu*0.10),
                              (0.14,(1,0.95,0.8),0.40+pu*0.12)]:
                Color(*col,min(1.0,ba*a)); Ellipse(pos=(cx-R*fr,cy-R*fr),size=(R*fr*2,R*fr*2))
            for ri in range(6):
                Color(*pal["primary"],min(1.0,(0.08+pu*0.04)*a))
                Line(circle=(cx,cy,R*(0.30+ri*0.12)),width=0.8)
            wcs=[(0.42,0.12,0.95),(0.00,0.82,0.92),(0.55,0.18,1.00),(1.0,0.48,0.08),(0.20,0.95,0.55)]
            nwv=4 if self.state in("listening","speaking") else 2
            ab=R*(0.28+self._energy*0.10 if self.state in("listening","speaking") else 0.11)
            for wi in range(nwv):
                ph=t*(1.0+wi*0.38)+wi*math.pi/nwv
                amp=ab*(1.0+pu*0.16)*(0.8+0.4*math.sin(t*0.7+wi))
                pts=[]
                for si in range(81):
                    frac=si/80; lx=cx-R*0.78+frac*R*1.56
                    mx=math.sqrt(max(0,(R*0.80)**2-(lx-cx)**2))
                    wy=amp*math.sin((2.2+wi*0.72)*math.pi*frac+ph)
                    pts.extend([lx,cy+max(-mx,min(mx,wy))])
                Color(*wcs[wi%len(wcs)],min(1.0,(0.55-wi*0.08+pu*0.10)*a))
                if len(pts)>=4: Line(points=pts,width=1.6+(0.6 if wi==0 else 0))
            Color(*sc,min(1.0,(0.55+pu*0.16)*a)); Line(circle=(cx,cy,R),width=1.8)
            cr=R*(0.055+pu*0.02); Color(*sc,min(1.0,0.90*a)); Ellipse(pos=(cx-cr,cy-cr),size=(cr*2,cr*2))

    def _nirvana(self,cx,cy,R,pal,sc,alpha):
        t=self._t; pu=self._pulse
        with self.canvas:
            for fr,ba in [(1.48,0.04),(1.28,0.07),(1.10,0.11),(1.00,0.16)]:
                Color(*sc,min(1.0,(ba+pu*0.04)*alpha)); Ellipse(pos=(cx-R*fr,cy-R*fr),size=(R*fr*2,R*fr*2))
            Color(0,0,0,alpha); Ellipse(pos=(cx-R*0.78,cy-R*0.78),size=(R*1.56,R*1.56))
            for rr,w,ba in [(R,16.0,0.10),(R,8.5,0.20),(R,4.0,0.54)]:
                Color(*sc,min(1.0,(ba+pu*0.07)*alpha)); Line(circle=(cx,cy,rr),width=w)
            rot=0.16+self._energy*0.36 if self.state in("listening","speaking") else 0.10
            for i in range(200):
                a0=math.radians(i*1.8)+t*rot; a1=math.radians((i+1)*1.8)+t*rot
                r2,g2,b2=_hsv((i/200+t*0.05)%1.0,0.55,1.0)
                br=(0.44+0.44*abs(math.sin(i/200*math.pi*2.8+t*0.5)))*(0.68+pu*0.32)
                Color(r2,g2,b2,min(1.0,br*alpha))
                Line(points=[cx+R*math.cos(a0),cy+R*math.sin(a0),cx+R*math.cos(a1),cy+R*math.sin(a1)],width=3.0)
            Color(1,1,1,min(1.0,(0.52+pu*0.17)*alpha)); Line(circle=(cx,cy,R*0.94),width=1.2)

# ── MicBar ────────────────────────────────────────────────────────────────────
class MicBar(Widget):
    def __init__(self,**kw):
        super().__init__(**kw); self._e=0.0; self._tgt=0.0
        Clock.schedule_interval(self._tick,1/30)
    def set_energy(self,e):
        if e>self._tgt: self._tgt=e
        else: self._tgt=max(e,self._tgt*0.65)
    def _tick(self,dt):
        self._tgt=max(0,self._tgt-dt*1.4); self._e+=(self._tgt-self._e)*0.26; self._draw()
    def _draw(self):
        self.canvas.clear(); pal=T(); n=32; bw=self.width/n
        with self.canvas:
            Color(*pal["bg"],1); Rectangle(pos=self.pos,size=self.size)
            for i in range(n):
                tv=time.time()*7.0+i*0.70
                bh=max(2.0,self._e*(self.height*0.82)+self.height*0.026*abs(math.sin(tv)))
                t2=min(1.0,self._e*2.2)
                Color(_lerp(pal["primary"][0],pal["accent"][0],t2),
                      _lerp(pal["primary"][1],pal["accent"][1],t2),
                      _lerp(pal["primary"][2],pal["accent"][2],t2),0.46+self._e*0.54)
                RoundedRectangle(pos=(self.x+(i/n)*self.width+1,self.y+self.height/2-bh/2),size=(bw-2,bh),radius=[2])

# ── ConnDot ───────────────────────────────────────────────────────────────────
class ConnDot(Widget):
    def __init__(self,**kw):
        super().__init__(**kw); self._online=True; self._blink=0.0
        Clock.schedule_interval(self._tick,1/15)
        Clock.schedule_interval(self._check,22); Clock.schedule_once(self._check,0.6)
    def _check(self,dt):
        # FIX: clean thread, no bad lambda
        def _bg():
            try:
                v=_ping()
            except Exception:
                v=False
            self._online=v
        threading.Thread(target=_bg,daemon=True).start()
    def set_online(self,v): self._online=v
    def _tick(self,dt): self._blink=(self._blink+dt*2.4)%math.tau; self._draw()
    def _draw(self):
        self.canvas.clear()
        col=_S["online"] if self._online else _S["offline"]
        pulse=0.55+0.45*math.sin(self._blink); r=min(self.width,self.height)/2-1
        with self.canvas:
            Color(*col,pulse*0.28); Ellipse(pos=self.pos,size=self.size)
            Color(*col,0.95); Ellipse(pos=(self.x+r*0.45,self.y+r*0.45),size=(r*1.1,r*1.1))

# ── LiveClock ─────────────────────────────────────────────────────────────────
class LiveClock(Label):
    def __init__(self,**kw):
        super().__init__(**kw); Clock.schedule_interval(self._tick,1.0); self._tick(0)
    def _tick(self,dt):
        self.text=datetime.datetime.now().strftime("%H:%M:%S"); self.color=(*_S["sub"],0.90)

# ── StreamLabel ───────────────────────────────────────────────────────────────
class StreamLabel(Label):
    def __init__(self,**kw):
        self._full=""; self._idx=0; self._ev=None
        super().__init__(**kw)
        self._ev=Clock.schedule_interval(self._type_tick,0.020)
    def append_chunk(self,chunk): self._full+=chunk
    def finish(self):
        if self._ev: Clock.unschedule(self._ev); self._ev=None
    def _type_tick(self,dt):
        if self._idx>=len(self._full): return
        step=max(1,int(len(self._full)*0.04)); self._idx=min(self._idx+step,len(self._full))
        pal=T()
        self.text=(f"[color=#{_hx(pal['sub'])}]* VEDA[/color]  "
                   f"[color=#{_hx(pal['ai_col'])}]{self._full[:self._idx]}[/color]|")

# ── ChatLog ───────────────────────────────────────────────────────────────────
class ChatLog(ScrollView):
    def __init__(self,**kw):
        super().__init__(**kw); self.do_scroll_x=False; self.bar_width=3
        self._box=BoxLayout(orientation="vertical",size_hint_y=None,spacing=5,padding=[10,8])
        self._box.bind(minimum_height=self._box.setter("height"))
        self.add_widget(self._box); self._stream_lbl=None; self._sl=threading.Lock()

    def add_bubble(self,who,role,text,src="",save=True):
        pal=T(); ts=datetime.datetime.now().strftime("%H:%M")
        tag={"gpt":"GPT","kb":"KB","ollama":"Local AI","google":"Web",
             "vosk":"Vosk","gpt-vision":"Vision"}.get(src,"")
        row=BoxLayout(orientation="horizontal",size_hint=(1,None),spacing=4)
        if role=="you":
            col=pal["you_col"]
            txt=(f"[color=#{_hx(pal['sub'])}]{ts}[/color]  [b][color=#{_hx(col)}]> YOU[/color][/b]  "
                 f"[color=#{_hx(pal['text'])}]{text}[/color]")
            lbl=Label(text=txt,markup=True,font_size=14,size_hint=(0.86,None),
                      halign="right",valign="top",padding=(10,7))
            row.add_widget(Widget(size_hint=(0.14,1))); row.add_widget(lbl)
            bg_col=(*pal["you_col"],0.07)
        elif role=="ai":
            col=pal["ai_col"]
            tag_str=f"  [color=#{_hx(pal['sub'])}][{tag}][/color]" if tag else ""
            txt=(f"[color=#{_hx(pal['sub'])}]{ts}[/color]  [b][color=#{_hx(col)}]* VEDA[/color][/b]{tag_str}  "
                 f"[color=#{_hx(pal['text'])}]{text}[/color]")
            lbl=Label(text=txt,markup=True,font_size=14,size_hint=(0.86,None),
                      halign="left",valign="top",padding=(10,7))
            row.add_widget(lbl); row.add_widget(Widget(size_hint=(0.14,1)))
            bg_col=(*pal["ai_col"],0.05)
        else:  # sys
            col=pal["sys_col"]
            txt=f"[color=#{_hx(col)}]-- {text}[/color]"
            lbl=Label(text=txt,markup=True,font_size=12,italic=True,size_hint=(1,None),
                      halign="center",valign="top",padding=(6,4))
            row.add_widget(lbl); bg_col=(0,0,0,0)
        lbl.bind(texture_size=lambda i,v:setattr(i,"height",v[1]+8))
        lbl.bind(width=lambda i,v:setattr(i,"text_size",(max(v-16,180),None)))
        with lbl.canvas.before:
            Color(*bg_col); bg=RoundedRectangle(pos=lbl.pos,size=lbl.size,radius=[10])
        lbl.bind(pos=lambda i,v:setattr(bg,"pos",v),size=lambda i,v:setattr(bg,"size",v))
        row.size_hint=(1,None); row.height=10; row.opacity=0
        lbl.bind(height=lambda i,v:setattr(row,"height",v+6))
        self._box.add_widget(row)
        Animation(opacity=1,duration=0.20).start(row)
        Clock.schedule_once(lambda dt:setattr(self,"scroll_y",0),0.05)

    def start_stream(self):
        with self._sl:
            if self._stream_lbl: self._stream_lbl.finish()
            sl=StreamLabel(text="",markup=True,font_size=14,size_hint=(0.86,None),
                           halign="left",valign="top",padding=(10,7))
            sl.bind(texture_size=lambda i,v:setattr(i,"height",v[1]+8))
            sl.bind(width=lambda i,v:setattr(i,"text_size",(max(v-16,180),None)))
            row=BoxLayout(orientation="horizontal",size_hint=(1,None),spacing=4)
            row.add_widget(sl); row.add_widget(Widget(size_hint=(0.14,1)))
            row.size_hint=(1,None); row.height=32
            sl.bind(height=lambda i,v:setattr(row,"height",v+6))
            self._box.add_widget(row)
            self._stream_lbl=sl
            Clock.schedule_once(lambda dt:setattr(self,"scroll_y",0),0.05)

    def append_stream(self,chunk):
        with self._sl:
            if self._stream_lbl: self._stream_lbl.append_chunk(chunk)

    def end_stream(self):
        with self._sl:
            if self._stream_lbl: self._stream_lbl.finish(); self._stream_lbl=None

    def clear(self):
        with self._sl:
            if self._stream_lbl: self._stream_lbl.finish(); self._stream_lbl=None
        self._box.clear_widgets()

# ── SysMonWidget ──────────────────────────────────────────────────────────────
class SysMonWidget(Widget):
    def __init__(self,**kw):
        super().__init__(**kw); self._cpu=0; self._ram=0; self._batt=-1; self._plug=True
        self._hc=[0]*50; self._hr=[0]*50; self._dirty=False
        Clock.schedule_interval(self._tick,1/8)
    def update(self,data):
        self._cpu=data.get("cpu",0); self._ram=data.get("ram",0)
        self._batt=data.get("batt",-1); self._plug=data.get("plug",True)
        self._hc=self._hc[1:]+[self._cpu/100]; self._hr=self._hr[1:]+[self._ram/100]
        self._dirty=True
    def _tick(self,dt):
        if self._dirty: self._dirty=False; self._draw()
    def _draw(self):
        self.canvas.clear(); pal=T(); w,h=self.width,self.height
        if w<10 or h<10: return
        with self.canvas:
            Color(*pal["card"],1); RoundedRectangle(pos=(self.x,self.y),size=(w,h),radius=[8])
            Color(*pal["primary"],0.20); Line(rounded_rectangle=(self.x,self.y,w,h,8),width=0.9)
            ch=h*0.42; cw=w-18; cx0=self.x+9; cy0=self.y+h*0.53
            Color(*pal["primary"],0.10); Rectangle(pos=(cx0,cy0),size=(cw,ch))
            pts=[]
            for i,v in enumerate(self._hc): pts.extend([cx0+i*(cw/49),cy0+v*ch])
            Color(*pal["primary"],0.88)
            if len(pts)>=4: Line(points=pts,width=1.4)
            ry0=self.y+8; Color(*pal["teal"],0.10); Rectangle(pos=(cx0,ry0),size=(cw,h*0.37))
            pts2=[]
            for i,v in enumerate(self._hr): pts2.extend([cx0+i*(cw/49),ry0+v*h*0.37])
            Color(*pal["teal"],0.82)
            if len(pts2)>=4: Line(points=pts2,width=1.4)
            if self._batt>=0:
                bx=self.x+w-20; by=self.y+h/2; br=9
                Color(*pal["muted"],0.5); Line(circle=(bx,by,br),width=1.5)
                col=(0.15,1.0,0.42) if self._batt>20 else (1.0,0.28,0.15)
                Color(*col,0.92); Line(circle=(bx,by,br,90,90+360*(self._batt/100)),width=3.0)

# ── Toast ─────────────────────────────────────────────────────────────────────
class ToastOverlay(FloatLayout):
    def __init__(self,**kw): super().__init__(**kw)
    def show(self,text):
        pal=T()
        lbl=Label(text=str(text),markup=False,font_size=13,size_hint=(None,None),height=40,
                  halign="center",valign="middle",color=(*pal["text"],1),opacity=0)
        lbl.texture_update(); lbl.width=max(240,lbl.texture_size[0]+32)
        lbl.pos_hint={"right":0.99,"top":0.96}
        with lbl.canvas.before:
            self._tbg=Color(*pal["card"],0.96)
            self._trc=RoundedRectangle(pos=lbl.pos,size=lbl.size,radius=[12])
            self._tbd=Color(*pal["primary"],0.65)
            self._tbl=Line(rounded_rectangle=(*lbl.pos,*lbl.size,12),width=1.1)
        lbl.bind(pos=lambda i,v:self._upd_toast(i),size=lambda i,v:self._upd_toast(i))
        self.add_widget(lbl); Animation(opacity=1,duration=0.16).start(lbl)
        Clock.schedule_once(lambda dt,l=lbl:Animation(opacity=0,duration=0.4).start(l),3.2)
        Clock.schedule_once(lambda dt,l=lbl:(self.remove_widget(l) if l.parent else None),3.8)
    def _upd_toast(self,lbl):
        lbl.canvas.before.clear(); pal=T()
        with lbl.canvas.before:
            Color(*pal["card"],0.96); RoundedRectangle(pos=lbl.pos,size=lbl.size,radius=[12])
            Color(*pal["primary"],0.65); Line(rounded_rectangle=(*lbl.pos,*lbl.size,12),width=1.1)

# ── Canvas icon drawing helpers ───────────────────────────────────────────────
def _draw_icon_mic(canvas, cx, cy, s, col, alpha=1.0):
    """Draw a microphone icon at center cx,cy within square s."""
    r=s*0.28; h=s*0.38; bw=s*0.52; bh=s*0.22
    with canvas:
        Color(*col, alpha)
        # Mic body (rounded rectangle via ellipse approximation)
        RoundedRectangle(pos=(cx-r, cy-h*0.30), size=(r*2, h*0.85), radius=[r])
        # Stand arc
        Line(points=[cx-bw/2, cy-h*0.38, cx-bw/2, cy-h*0.38-bh*0.4,
                     cx+bw/2, cy-h*0.38-bh*0.4, cx+bw/2, cy-h*0.38], width=1.8)
        Line(ellipse=(cx-bw/2, cy-h*0.38-bh, bw, bh*1.8, 180, 360), width=1.8)
        # Base line
        Line(points=[cx-bw*0.30, cy-h*0.38-bh, cx+bw*0.30, cy-h*0.38-bh], width=1.8)

def _draw_icon_camera(canvas, cx, cy, s, col, alpha=1.0):
    bw=s*0.70; bh=s*0.46; lr=s*0.14
    with canvas:
        Color(*col, alpha)
        RoundedRectangle(pos=(cx-bw/2, cy-bh/2), size=(bw, bh), radius=[lr])
        Color(*col, alpha*0.15)
        Ellipse(pos=(cx-s*0.20, cy-s*0.18), size=(s*0.40, s*0.40))
        Color(*col, alpha)
        Line(circle=(cx, cy, s*0.17), width=1.6)
        # Viewfinder notch
        Line(points=[cx-s*0.10, cy+bh/2-2, cx-s*0.04, cy+bh/2+s*0.10,
                     cx+s*0.04, cy+bh/2+s*0.10, cx+s*0.10, cy+bh/2-2], width=1.5)

def _draw_icon_bell(canvas, cx, cy, s, col, alpha=1.0):
    r=s*0.30; br=s*0.10
    with canvas:
        Color(*col, alpha)
        Line(ellipse=(cx-r, cy-r*0.40, r*2, r*2.0, 0, 180), width=2.0)
        Line(points=[cx-r, cy-r*0.40, cx-r, cy-r*0.55], width=2.0)
        Line(points=[cx+r, cy-r*0.40, cx+r, cy-r*0.55], width=2.0)
        Line(points=[cx-r*1.18, cy-r*0.55, cx+r*1.18, cy-r*0.55], width=2.0)
        Line(circle=(cx, cy+r*0.94), width=1.6)
        Line(ellipse=(cx-br, cy-r*0.55-br*0.5, br*2, br), width=1.5)

def _draw_icon_monitor(canvas, cx, cy, s, col, alpha=1.0):
    bw=s*0.68; bh=s*0.46; sw=s*0.20; sh=s*0.12; lr=s*0.06
    with canvas:
        Color(*col, alpha)
        Line(rounded_rectangle=(cx-bw/2, cy-bh/2+sh*0.5, bw, bh, lr), width=1.8)
        # Stand
        Line(points=[cx-sw/2, cy-bh/2+sh*0.5, cx-sw/2, cy-bh/2-sh*0.4], width=1.8)
        Line(points=[cx+sw/2, cy-bh/2+sh*0.5, cx+sw/2, cy-bh/2-sh*0.4], width=1.8)
        Line(points=[cx-sw*0.9, cy-bh/2-sh*0.4, cx+sw*0.9, cy-bh/2-sh*0.4], width=1.8)
        # Screen lines
        Color(*col, alpha*0.50)
        for i in range(3):
            lx=cx-bw*0.34; ly=cy-bh*0.08+i*s*0.09
            Line(points=[lx, ly, lx+bw*0.68, ly], width=1.2)

def _draw_icon_news(canvas, cx, cy, s, col, alpha=1.0):
    bw=s*0.62; bh=s*0.56; lr=s*0.06
    with canvas:
        Color(*col, alpha)
        Line(rounded_rectangle=(cx-bw/2, cy-bh/2, bw, bh, lr), width=1.8)
        Color(*col, alpha*0.60)
        # Lines
        Line(points=[cx-bw*0.36, cy+bh*0.15, cx+bw*0.36, cy+bh*0.15], width=1.4)
        Line(points=[cx-bw*0.36, cy+bh*0.01, cx+bw*0.36, cy+bh*0.01], width=1.4)
        Line(points=[cx-bw*0.36, cy-bh*0.13, cx+bw*0.10, cy-bh*0.13], width=1.4)
        # Small rect top-left
        Color(*col, alpha)
        RoundedRectangle(pos=(cx-bw*0.36, cy+bh*0.25), size=(bw*0.40, bh*0.18), radius=[2])

def _draw_icon_cloud(canvas, cx, cy, s, col, alpha=1.0):
    with canvas:
        Color(*col, alpha)
        # Cloud body using overlapping circles
        r1=s*0.24; r2=s*0.18; r3=s*0.14
        Ellipse(pos=(cx-r1-r2*0.5, cy-r1*0.3), size=(r1*2, r1*2))
        Ellipse(pos=(cx+r1*0.2, cy), size=(r2*2, r2*2))
        Ellipse(pos=(cx-r1*0.9, cy-r1*0.1), size=(r3*2, r3*2))
        Rectangle(pos=(cx-r1-r2*0.5, cy-r1*0.30), size=(r1*2+r2+r3*0.5, r1*0.80))
        # Rain drops
        Color(*col, alpha*0.65)
        for i in range(3):
            rx=cx-s*0.16+i*s*0.16; ry=cy-r1*0.60
            Line(points=[rx, ry, rx-s*0.04, ry-s*0.14], width=1.5)

def _draw_icon_trash(canvas, cx, cy, s, col, alpha=1.0):
    bw=s*0.44; bh=s*0.42; tw=s*0.52
    with canvas:
        Color(*col, alpha)
        # Lid
        Line(points=[cx-tw/2, cy+bh/2+s*0.05, cx+tw/2, cy+bh/2+s*0.05], width=2.0)
        Line(rounded_rectangle=(cx-bw/2, cy+bh*0.10, s*0.18, s*0.10, 2), width=1.6)
        # Body
        Line(rounded_rectangle=(cx-bw/2, cy-bh/2, bw, bh*0.85, s*0.06), width=1.8)
        # Stripes
        Color(*col, alpha*0.45)
        for i in range(3):
            lx=cx-bw*0.25+i*bw*0.25; ly=cy-bh*0.42
            Line(points=[lx, ly, lx, cy+bh*0.30], width=1.2)

def _draw_icon_om(canvas, cx, cy, s, col, alpha=1.0):
    """Draw stylised OM / spiritual symbol (circle with inner 3-petal)."""
    r=s*0.32; r2=s*0.14
    with canvas:
        Color(*col, alpha)
        Line(circle=(cx, cy, r), width=1.8)
        # Three inner arcs representing AUM
        for i in range(3):
            a=i*math.tau/3+math.pi/6
            x2=cx+r*0.42*math.cos(a); y2=cy+r*0.42*math.sin(a)
            Line(circle=(x2, y2, r2), width=1.5)
        Color(*col, alpha*0.80)
        Ellipse(pos=(cx-s*0.06, cy-s*0.06), size=(s*0.12, s*0.12))

def _draw_icon_voice(canvas, cx, cy, s, col, alpha=1.0):
    """Sound-wave bars icon."""
    with canvas:
        Color(*col, alpha)
        for i,h in enumerate([0.22,0.38,0.56,0.38,0.22]):
            x=cx-s*0.26+i*s*0.13; bh=s*h
            RoundedRectangle(pos=(x-s*0.045, cy-bh/2), size=(s*0.090, bh), radius=[s*0.04])

def _draw_icon_chat(canvas, cx, cy, s, col, alpha=1.0):
    bw=s*0.64; bh=s*0.48; lr=s*0.12
    with canvas:
        Color(*col, alpha)
        RoundedRectangle(pos=(cx-bw/2, cy-bh/2+s*0.05), size=(bw, bh), radius=[lr])
        # Tail
        Line(points=[cx-bw*0.10, cy-bh/2+s*0.05, cx-bw*0.30, cy-bh/2-s*0.10,
                     cx+bw*0.05, cy-bh/2+s*0.05], width=1.6)
        # Dots
        Color(*col, alpha*0.35)
        for i in range(3):
            dx=cx-s*0.10+i*s*0.10
            Ellipse(pos=(dx-s*0.04, cy-s*0.04+s*0.05), size=(s*0.08, s*0.08))

def _draw_icon_history(canvas, cx, cy, s, col, alpha=1.0):
    r=s*0.30
    with canvas:
        Color(*col, alpha)
        Line(circle=(cx, cy, r), width=1.8)
        # Clock hands
        Line(points=[cx, cy, cx, cy+r*0.68], width=2.0)
        Line(points=[cx, cy, cx+r*0.50, cy-r*0.38], width=2.0)
        # Arrow arc
        Line(ellipse=(cx-r*1.24, cy-r*1.24, r*2.48, r*2.48, 100, 360), width=1.5)
        Line(points=[cx-r*1.18, cy+r*0.26, cx-r*1.54, cy+r*0.52,
                     cx-r*0.84, cy+r*0.52], width=1.5)

def _draw_icon_settings(canvas, cx, cy, s, col, alpha=1.0):
    r=s*0.30; ri=s*0.14; n=8
    with canvas:
        Color(*col, alpha)
        for i in range(n):
            a=i*math.tau/n; a2=(i+0.5)*math.tau/n
            x1=cx+r*math.cos(a); y1=cy+r*math.sin(a)
            x2=cx+(r+s*0.11)*math.cos(a2); y2=cy+(r+s*0.11)*math.sin(a2)
            Line(points=[cx+ri*math.cos(a), cy+ri*math.sin(a), x2, y2], width=2.0)
        Color(*col, alpha*0.55)
        Line(circle=(cx, cy, ri), width=1.6)

def _draw_icon_ai(canvas, cx, cy, s, col, alpha=1.0):
    """Neural net / AI brain icon."""
    r=s*0.30
    with canvas:
        Color(*col, alpha)
        Line(circle=(cx, cy, r), width=1.8)
        # Neural connections
        nodes=[(cx,cy+r*0.55),(cx-r*0.55,cy-r*0.30),(cx+r*0.55,cy-r*0.30)]
        for i,n1 in enumerate(nodes):
            for j,n2 in enumerate(nodes):
                if i<j:
                    Color(*col, alpha*0.40)
                    Line(points=[n1[0],n1[1],n2[0],n2[1]], width=1.2)
        for nx,ny in nodes:
            Color(*col, alpha)
            Ellipse(pos=(nx-s*0.06, ny-s*0.06), size=(s*0.12, s*0.12))
        Color(*col, alpha*0.65)
        Ellipse(pos=(cx-s*0.06, cy-s*0.06), size=(s*0.12, s*0.12))

def _draw_icon_power(canvas, cx, cy, s, col, alpha=1.0):
    r=s*0.30
    with canvas:
        Color(*col, alpha)
        Line(ellipse=(cx-r, cy-r, r*2, r*2, 40, 320), width=2.2)
        Line(points=[cx, cy+r*0.28, cx, cy+r*1.06], width=2.4)

_ICON_DRAW_FNS = {
    "mic":      _draw_icon_mic,
    "camera":   _draw_icon_camera,
    "bell":     _draw_icon_bell,
    "monitor":  _draw_icon_monitor,
    "news":     _draw_icon_news,
    "cloud":    _draw_icon_cloud,
    "trash":    _draw_icon_trash,
    "om":       _draw_icon_om,
    "voice":    _draw_icon_voice,
    "chat":     _draw_icon_chat,
    "history":  _draw_icon_history,
    "settings": _draw_icon_settings,
    "ai":       _draw_icon_ai,
    "power":    _draw_icon_power,
}

# ── IconCanvas — a Widget that draws one named icon ───────────────────────────
class IconCanvas(Widget):
    def __init__(self, icon_key="chat", col=None, size_hint=(None,None),
                 width=40, height=40, alpha=1.0, **kw):
        super().__init__(size_hint=size_hint, width=width, height=height, **kw)
        self._key=icon_key; self._col=col or _S["primary"]; self._alpha=alpha
        self.bind(pos=self._redraw, size=self._redraw)
        Clock.schedule_once(self._redraw, 0.05)
    def set_alpha(self, a): self._alpha=a; self._redraw()
    def set_col(self, c): self._col=c; self._redraw()
    def _redraw(self, *_):
        self.canvas.clear()
        cx=self.center_x; cy=self.center_y; s=min(self.width, self.height)
        fn=_ICON_DRAW_FNS.get(self._key)
        if fn: fn(self.canvas, cx, cy, s, self._col, self._alpha)

# ── SideNav — left sidebar with all VEDA feature shortcuts ────────────────────
_SIDENAV_ITEMS = [
    # (icon_key, label, tab_idx_or_action)
    ("voice",    "Voice",      None),        # highlights the orb area — just visual
    ("chat",     "Chat",       "tab:0"),
    ("history",  "History",    "tab:1"),
    ("bell",     "Reminders",  "tab:2"),
    ("monitor",  "System",     "tab:3"),
    ("settings", "Settings",   "tab:4"),
    ("mic",      "Calibrate",  "cmd:calibrate"),
    ("cloud",    "Weather",    "cmd:weather"),
    ("news",     "News",       "cmd:news"),
    ("camera",   "Screenshot", "cmd:screenshot"),
    ("ai",       "AI Chat",    "ai_panel"),
    ("om",       "Guru Mode",  "cmd:personality guru"),
    ("trash",    "Clear Chat", "cmd:clear_chat"),
    ("power",    "Shutdown",   "cmd:shutdown in 60 seconds"),
]

class SideNav(BoxLayout):
    COLLAPSED_W = 54
    EXPANDED_W  = 180

    def __init__(self, app_ref, **kw):
        kw.setdefault("orientation","vertical")
        kw.setdefault("size_hint",(None,1))
        kw.setdefault("width", self.COLLAPSED_W)
        kw.setdefault("spacing", 2)
        kw.setdefault("padding", [0, 8, 0, 8])
        super().__init__(**kw)
        self._app = app_ref
        self._expanded = False
        self._anim = None
        self._items = []   # list of (IconCanvas, Label, action)
        self._active = 0

        with self.canvas.before:
            self._bg_c = Color(*_S["bg2"], 1.0)
            self._bg_r = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda i,v: setattr(self._bg_r,"pos",v),
                  size=lambda i,v: setattr(self._bg_r,"size",v))

        # Toggle button at top
        self._toggle_btn = Button(
            text=">>", font_size=14, bold=True,
            size_hint=(1, None), height=46,
            background_color=(0,0,0,0),
            color=(*_S["primary"],1))
        self._toggle_btn.bind(on_press=self._toggle)
        self.add_widget(self._toggle_btn)

        # Divider
        div=Widget(size_hint=(1,None),height=1)
        with div.canvas:
            Color(*_S["divider"],0.6); Rectangle(pos=div.pos,size=div.size)
        div.bind(pos=lambda i,v:(i.canvas.clear(),
                                  i.canvas.add(Color(*_S["divider"],0.6)),
                                  i.canvas.add(Rectangle(pos=v,size=i.size))))
        self.add_widget(div)

        # Nav items
        for ico, lbl_txt, action in _SIDENAV_ITEMS:
            row = BoxLayout(orientation="horizontal", size_hint=(1,None),
                            height=46, spacing=0, padding=[4,4,4,4])
            with row.canvas.before:
                row._hl_c = Color(0,0,0,0)
                row._hl_r = RoundedRectangle(pos=row.pos, size=row.size, radius=[6])
            row.bind(pos=lambda i,v: setattr(i._hl_r,"pos",v),
                     size=lambda i,v: setattr(i._hl_r,"size",v))

            ic = IconCanvas(icon_key=ico, col=_S["sub"],
                            size_hint=(None,1), width=46)
            lbl = Label(text=lbl_txt, font_size=12, bold=True,
                        color=(*_S["sub"],0), halign="left", valign="middle",
                        size_hint=(1,1), opacity=0)
            lbl.bind(size=lambda i,v: setattr(i,"text_size",(v[0]-4, v[1])))

            row.add_widget(ic)
            row.add_widget(lbl)
            self._items.append((ic, lbl, row, action))

            act=action
            def _on_press(inst, touch, a=act, r=row):
                if r.collide_point(*touch.pos):
                    self._handle_action(a)
                    return True
            row.bind(on_touch_down=_on_press)
            self.add_widget(row)

        self.add_widget(Widget(size_hint=(1,1)))  # spacer

    def _toggle(self, *_):
        self._expanded = not self._expanded
        target_w = self.EXPANDED_W if self._expanded else self.COLLAPSED_W
        self._toggle_btn.text = "<<" if self._expanded else ">>"
        Animation(width=target_w, duration=0.22, t="out_quad").start(self)
        for ic, lbl, row, action in self._items:
            if self._expanded:
                lbl.opacity=1; lbl.color=(*_S["sub"],1)
            else:
                lbl.opacity=0; lbl.color=(*_S["sub"],0)

    def set_active_tab(self, idx):
        """Highlight the nav item that corresponds to a tab index."""
        tab_map = {"tab:0":0,"tab:1":1,"tab:2":2,"tab:3":3,"tab:4":4}
        for i,(ic,lbl,row,action) in enumerate(self._items):
            active = (action in tab_map and tab_map[action]==idx)
            if active:
                row._hl_c.rgba=(*_S["tab_act"],1)
                ic.set_col(_S["primary"]); ic.set_alpha(1.0)
                lbl.color=(*_S["primary"],1 if self._expanded else 0)
            else:
                row._hl_c.rgba=(0,0,0,0)
                ic.set_col(_S["sub"]); ic.set_alpha(0.70)
                lbl.color=(*_S["sub"],1 if self._expanded else 0)

    def update_theme(self, pal):
        self._bg_c.rgba=(*pal["bg2"],1)
        for ic,lbl,row,action in self._items:
            # preserve active highlight
            pass

    def _handle_action(self, action):
        if action is None: return
        if action.startswith("tab:"):
            self._app._switch_tab(int(action[4:]))
        elif action=="ai_panel":
            self._app._ai_panel.toggle()
        elif action.startswith("cmd:"):
            cmd=action[4:]
            threading.Thread(target=execute,args=(cmd,),daemon=True).start()

# ── QuickPanel — big icon cards matching screenshot ───────────────────────────
# FIX: No pos_hint on panel. We place it with y=-height and animate y to 0.
# FIX: lambda closures in card borders use default arg capture correctly.
class QuickPanel(Widget):
    _ACTIONS=[
        ("mic",    "Calibrate\nMic",   "calibrate"),
        ("camera", "Screenshot",       "screenshot"),
        ("bell",   "Reminders",        "reminders"),
        ("monitor","System\nInfo",     "system status"),
        ("news",   "Latest\nNews",     "news"),
        ("cloud",  "Weather",          "weather"),
        ("trash",  "Clear\nChat",      "clear_chat"),
        ("om",     "Guru\nMode",       "personality guru"),
    ]
    def __init__(self,**kw):
        super().__init__(**kw); self._open=False
        # Panel is a BoxLayout child placed manually
        self._panel=BoxLayout(orientation="vertical",
                              size_hint=(None,None),width=420,height=450,
                              padding=[14,12],spacing=10)
        with self._panel.canvas.before:
            self._bg_c=Color(*_S["card"],0.97)
            self._bg_r=RoundedRectangle(pos=self._panel.pos,size=self._panel.size,radius=[18,18,0,0])
        self._panel.bind(
            pos=lambda i,v:(setattr(self._bg_r,"pos",v)),
            size=lambda i,v:(setattr(self._bg_r,"size",v)))
        self._build()
        self.add_widget(self._panel)
        # Position off-screen below. Done after first frame so widget has pos.
        Clock.schedule_once(self._init_pos,0.1)

    def _init_pos(self,dt):
        # Place panel at bottom-left, hidden below screen
        self._panel.pos=(0,-self._panel.height-10)

    def _build(self):
        # Header
        hdr=BoxLayout(size_hint=(1,None),height=40)
        tl=Label(text="Quick Actions",font_size=14,bold=True,
                 color=(*_S["primary"],1),halign="left",size_hint=(1,1))
        tl.bind(size=lambda i,v:setattr(i,"text_size",v))
        bx=Button(text="X",font_size=13,bold=True,size_hint=(None,1),width=34,
                  background_color=(0,0,0,0),color=(*_S["sub"],1))
        bx.bind(on_press=lambda *_:self.close())
        hdr.add_widget(tl); hdr.add_widget(bx); self._panel.add_widget(hdr)

        # Divider
        div=Widget(size_hint=(1,None),height=1)
        with div.canvas: Color(*_S["divider"],0.8); Rectangle(pos=div.pos,size=div.size)
        div.bind(pos=lambda i,v:(i.canvas.clear(),
                  i.canvas.add(Color(*_S["divider"],0.8)),
                  i.canvas.add(Rectangle(pos=v,size=i.size))))
        self._panel.add_widget(div)

        # 2-row x 4-col grid
        row1=BoxLayout(size_hint=(1,0.5),spacing=8)
        row2=BoxLayout(size_hint=(1,0.5),spacing=8)
        for idx,(ico,lbl,cmd) in enumerate(self._ACTIONS):
            card=self._make_card(ico,lbl,cmd)
            if idx<4: row1.add_widget(card)
            else:     row2.add_widget(card)
        self._panel.add_widget(row1)
        self._panel.add_widget(row2)

    def _make_card(self,ico_key,lbl,cmd):
        card=BoxLayout(orientation="vertical",spacing=2,padding=[4,6,4,4])
        with card.canvas.before:
            c_bg=Color(*_S["card2"],1.0)
            r_bg=RoundedRectangle(pos=card.pos,size=card.size,radius=[12])
            c_bd=Color(*_S["primary"],0.32)
            r_bd=Line(rounded_rectangle=(*card.pos,*card.size,12),width=1.1)
        def _upd_card(inst,val,rb=r_bg,lb=r_bd):
            rb.pos=inst.pos; rb.size=inst.size
            lb.rounded_rectangle=(*inst.pos,*inst.size,12)
        card.bind(pos=_upd_card,size=_upd_card)

        # Canvas-drawn icon
        ic=IconCanvas(icon_key=ico_key, col=_S["primary"], alpha=0.92,
                      size_hint=(1,0.58))
        txt_lbl=Label(text=lbl,font_size=11,bold=True,size_hint=(1,0.42),
                      halign="center",valign="top",color=(*_S["text"],1))
        txt_lbl.bind(size=lambda i,v:setattr(i,"text_size",(v[0],None)))
        card.add_widget(ic)
        card.add_widget(txt_lbl)

        # Hover glow on touch
        c2=cmd
        def _on_touch(inst,touch,c=c2,rb=r_bg,lb=r_bd,cbg=c_bg,cbd=c_bd):
            if not inst.collide_point(*touch.pos): return False
            cbg.rgba=(*_S["primary"],0.18); cbd.rgba=(*_S["primary"],0.80)
            def _reset(dt,cbg_=cbg,cbd_=cbd):
                cbg_.rgba=(*_S["card2"],1.0); cbd_.rgba=(*_S["primary"],0.32)
            Clock.schedule_once(_reset,0.18)
            self._run(c); return True
        card.bind(on_touch_down=_on_touch)
        return card

    def _run(self,cmd):
        self.close()
        if cmd=="clear_chat":
            a=App.get_running_app()
            if a: Clock.schedule_once(lambda dt: a.chat.clear(), 0)
        elif cmd=="reminders":
            a=App.get_running_app()
            if a: Clock.schedule_once(lambda dt: a._switch_tab(2), 0)
        elif cmd=="calibrate":
            def _cal():
                speak("Calibrating. Please be silent for 2 seconds.",save=False); time.sleep(0.5)
                try:
                    with sr.Microphone() as src: _rec.adjust_for_ambient_noise(src,2.0)
                    db_save_noise(_rec.energy_threshold)
                    speak(f"Calibrated. Threshold {int(_rec.energy_threshold)}.",save=False)
                    _ui("toast",f"Calibrated — {int(_rec.energy_threshold)}")
                except Exception: speak("Calibration failed.",save=False)
            threading.Thread(target=_cal,daemon=True).start()
        else:
            threading.Thread(target=execute,args=(cmd,),daemon=True).start()

    def toggle(self):
        self._open=not self._open
        if self._open:
            self._panel.pos=(0,0)
            self._panel.opacity=1
            Animation(y=0,opacity=1,duration=0.26,t='out_cubic').start(self._panel)
        else:
            self.close()

    def close(self):
        if self._open or self._panel.y>=0:
            self._open=False
            Animation(y=-self._panel.height-10,opacity=0,duration=0.22).start(self._panel)

# ── AIChatPanel ───────────────────────────────────────────────────────────────
class AIChatPanel(FloatLayout):
    def __init__(self,**kw):
        super().__init__(**kw); self._open=False; self._loaded=False
        self._panel=BoxLayout(orientation="vertical",size_hint=(None,None),width=340,height=520)
        self._build(); self.add_widget(self._panel)
        # Position off right edge after window ready
        Clock.schedule_once(self._init_pos,0.15)
        Clock.schedule_interval(self._theme,1/10)

    def _init_pos(self,dt):
        self._panel.pos=(Window.width+10, int(Window.height*0.15))

    def _build(self):
        hdr=BoxLayout(size_hint=(1,None),height=46,padding=[12,6])
        with hdr.canvas.before:
            self._hc=Color(*_S["card"],1)
            self._hr=RoundedRectangle(pos=hdr.pos,size=hdr.size,radius=[12,12,0,0])
        hdr.bind(pos=lambda i,v:setattr(self._hr,"pos",v),
                 size=lambda i,v:setattr(self._hr,"size",v))
        self._tl=Label(text="[AI] Chat",font_size=14,bold=True,color=(*_S["primary"],1))
        bc=Button(text="[X]",font_size=13,size_hint=(None,1),width=36,
                  background_color=(0,0,0,0),color=(*_S["sub"],1))
        bc.bind(on_press=lambda *_:self.toggle())
        hdr.add_widget(self._tl); hdr.add_widget(bc); self._panel.add_widget(hdr)

        self._chat=ChatLog(size_hint=(1,1))
        with self._chat.canvas.before:
            self._cc=Color(*_S["bg2"],1)
            self._cr=Rectangle(pos=self._chat.pos,size=self._chat.size)
        self._chat.bind(pos=lambda i,v:setattr(self._cr,"pos",v),
                        size=lambda i,v:setattr(self._cr,"size",v))
        self._panel.add_widget(self._chat)

        inp=BoxLayout(size_hint=(1,None),height=48,spacing=5,padding=[8,6])
        with inp.canvas.before:
            self._ic=Color(*_S["card"],1)
            self._ir=RoundedRectangle(pos=inp.pos,size=inp.size,radius=[0,0,12,12])
        inp.bind(pos=lambda i,v:setattr(self._ir,"pos",v),
                 size=lambda i,v:setattr(self._ir,"size",v))
        self._txt=TextInput(hint_text="Ask anything…",multiline=False,font_size=13,
                            background_color=(0,0,0,0),foreground_color=(*_S["text"],1),
                            hint_text_color=(*_S["sub"],0.4),padding=[10,10])
        self._txt.bind(on_text_validate=self._send)
        bs=Button(text=">>",font_size=14,bold=True,size_hint=(None,1),width=42,
                  background_color=(*_S["accent"],1),color=(1,1,1,1))
        bs.bind(on_press=self._send)
        inp.add_widget(self._txt); inp.add_widget(bs); self._panel.add_widget(inp)

    def _send(self,*_):
        q=self._txt.text.strip()
        if not q: return
        self._txt.text=""
        self._chat.add_bubble("YOU","you",q,"",True)
        db_save_chat("user",q,"ai-panel",is_conv=True)
        def _reply():
            Clock.schedule_once(lambda dt:self._chat.start_stream(),0)
            full=""
            def _cb(chunk):
                nonlocal full; full+=chunk
                Clock.schedule_once(lambda dt,c=chunk:self._chat.append_stream(c),0)
            reply,src=ask_chatgpt(q,stream_cb=_cb)
            Clock.schedule_once(lambda dt:self._chat.end_stream(),0)
            msg=reply if reply else "No OpenAI key configured. Add key in [CFG] Settings."
            Clock.schedule_once(lambda dt:self._chat.add_bubble("VEDA","ai",msg,src or "",""),0.1)
        threading.Thread(target=_reply,daemon=True).start()

    def toggle(self):
        self._open=not self._open
        if self._open and not self._loaded:
            self._loaded=True
            rows=db_load_history(20,conv_only=True)
            for role,content,src in rows:
                r2="you" if role=="user" else "ai"
                w2="YOU" if role=="user" else "VEDA"
                Clock.schedule_once(
                    lambda dt,ww=w2,rr=r2,cc=content,ss=src:
                        self._chat.add_bubble(ww,rr,cc,ss,False),0)
        # FIX: always compute from current Window width
        if self._open:
            tx=Window.width-self._panel.width-6
        else:
            tx=Window.width+10
        Animation(x=tx,duration=0.28,t='out_cubic').start(self._panel)

    def _theme(self,dt):
        pal=T()
        self._tl.color=(*pal["primary"],1)
        self._hc.rgba=(*pal["card"],1)
        self._cc.rgba=(*pal["bg2"],1)
        self._ic.rgba=(*pal["card"],1)
        self._txt.foreground_color=(*pal["text"],1)
        self._txt.hint_text_color=(*pal["sub"],0.4)

# ── RemindersTab ──────────────────────────────────────────────────────────────
class RemindersTab(BoxLayout):
    def __init__(self,**kw):
        super().__init__(orientation="vertical",spacing=10,padding=[14,12],**kw)
        self._build()

    def _build(self):
        self.add_widget(Label(text="[b][ALM] Reminders[/b]",markup=True,font_size=16,
                              color=(*_S["primary"],1),size_hint=(1,None),height=34))
        quick=BoxLayout(size_hint=(1,None),height=46,spacing=6)
        for lbl,mins in [("5 min",5),("15 min",15),("30 min",30),("1 hour",60),("Custom",0)]:
            b=Button(text=lbl,font_size=12,bold=True,
                     background_color=(*_S["primary"],0.18),color=(*_S["text"],1))
            m2=mins; b.bind(on_press=lambda *_,m=m2:self._quick(m))
            quick.add_widget(b)
        self.add_widget(quick)
        self._what=TextInput(hint_text="What to remind you about?",multiline=False,font_size=13,
                             size_hint=(1,None),height=42,background_color=(*_S["card"],1),
                             foreground_color=(*_S["text"],1),
                             hint_text_color=(*_S["sub"],0.4),padding=[10,10])
        self.add_widget(self._what)
        self._crow=BoxLayout(size_hint=(1,None),height=0,spacing=6,opacity=0)
        self._ct=TextInput(hint_text="e.g. in 2 hours / at 6pm / tomorrow 9am",
                           multiline=False,font_size=12,background_color=(*_S["card"],1),
                           foreground_color=(*_S["text"],1),
                           hint_text_color=(*_S["sub"],0.4),padding=[10,10])
        bs=Button(text="Set [ALM]",font_size=12,bold=True,size_hint=(None,1),width=70,
                  background_color=(*_S["accent"],1),color=(1,1,1,1))
        bs.bind(on_press=self._set_custom)
        self._crow.add_widget(self._ct); self._crow.add_widget(bs)
        self.add_widget(self._crow)
        self._sv=ScrollView(size_hint=(1,1))
        self._rb=BoxLayout(orientation="vertical",size_hint_y=None,spacing=6)
        self._rb.bind(minimum_height=self._rb.setter("height"))
        self._sv.add_widget(self._rb); self.add_widget(self._sv)
        self.refresh()

    def _quick(self,mins):
        if mins==0:
            self._crow.height=44; self._crow.opacity=1; return
        what=self._what.text.strip() or "reminder"
        _ui("toast",_parse_reminder(f"remind me in {mins} minutes to {what}"))
        self._what.text=""; self.refresh()

    def _set_custom(self,*_):
        t=self._ct.text.strip(); what=self._what.text.strip() or "reminder"
        if t:
            _ui("toast",_parse_reminder(f"remind me {t} to {what}"))
            self._what.text=""; self._ct.text=""
            self._crow.height=0; self._crow.opacity=0; self.refresh()

    def refresh(self):
        self._rb.clear_widgets(); pal=T(); rows=db_get_reminders()
        if not rows:
            self._rb.add_widget(Label(text="No upcoming reminders",font_size=13,italic=True,
                                      color=(*pal["sub"],0.6),size_hint=(1,None),height=38))
            return
        for rid,ts_str,label in rows:
            try: ts_show=datetime.datetime.fromisoformat(ts_str).strftime("%d %b  %I:%M %p")
            except: ts_show=ts_str[:16]
            row=BoxLayout(size_hint=(1,None),height=46,spacing=8)
            with row.canvas.before:
                Color(*pal["card"],1); RoundedRectangle(pos=row.pos,size=row.size,radius=[8])
            lt=(f"[b][color=#{_hx(pal['text'])}]{label}[/color][/b]  "
                f"[color=#{_hx(pal['sub'])}]{ts_show}[/color]")
            l=Label(text=lt,markup=True,font_size=13,size_hint=(1,1),
                    halign="left",valign="middle")
            l.bind(size=lambda i,v:setattr(i,"text_size",(v[0]-8,None)))
            db=Button(text="[OK]",font_size=11,bold=True,size_hint=(None,1),width=62,
                      background_color=(0.15,0.65,0.25,0.9),color=(1,1,1,1))
            db.bind(on_press=lambda *_,r=rid:self._done(r))
            row.add_widget(l); row.add_widget(db); self._rb.add_widget(row)

    def _done(self,rid): db_done_reminder(rid); self.refresh()

# ── SettingsTab ───────────────────────────────────────────────────────────────
class SettingsTab(BoxLayout):
    def __init__(self,**kw):
        super().__init__(orientation="vertical",spacing=10,padding=[14,12],**kw)
        self._build()

    def _field(self,label,val,hint,pw=False):
        self.add_widget(Label(text=label,font_size=13,color=(*_S["sub"],1),
                              size_hint=(1,None),height=26,halign="left"))
        ti=TextInput(text=val,hint_text=hint,password=pw,multiline=False,font_size=13,
                     size_hint=(1,None),height=40,background_color=(*_S["card"],1),
                     foreground_color=(*_S["text"],1),hint_text_color=(*_S["sub"],0.4),
                     padding=[10,10])
        self.add_widget(ti); return ti

    def _build(self):
        self.add_widget(Label(text="[b][CFG] Settings[/b]",markup=True,font_size=16,
                              color=(*_S["primary"],1),size_hint=(1,None),height=34))
        self._name   =self._field("Your name:",CFG.get("user_name",""),"Enter your name")
        self._city   =self._field("City (weather):",CFG.get("city","Hyderabad"),"City name")
        self._key    =self._field("OpenAI API key:",CFG.get("openai_key",""),"sk-...",pw=True)
        self._ollama =self._field("Ollama model:",CFG.get("ollama_model","mistral"),
                                  "mistral / llama3 / phi3")
        bs=Button(text="[SAVE] Settings",font_size=14,bold=True,
                  size_hint=(1,None),height=46,
                  background_color=(*_S["accent"],1),color=(1,1,1,1))
        bs.bind(on_press=self._save); self.add_widget(bs)
        self.add_widget(Label(text="[b]VEDA v15.3  —  Dharma Zenith Edition[/b]",
                              markup=True,font_size=11,color=(*_S["muted"],0.8),
                              size_hint=(1,None),height=30,halign="center"))
        self.add_widget(Widget())

    def _save(self,*_):
        CFG["user_name"]   =self._name.text.strip()
        CFG["city"]        =self._city.text.strip() or "Hyderabad"
        CFG["openai_key"]  =self._key.text.strip()
        CFG["ollama_model"]=self._ollama.text.strip() or "mistral"
        _vb.OPENAI_API_KEY =CFG["openai_key"]
        _save_cfg(); _ui("toast","✅ Settings saved!")

# ── HistoryInput ──────────────────────────────────────────────────────────────
class HistoryInput(TextInput):
    def __init__(self,**kw):
        super().__init__(**kw); self._history=[]; self._hidx=-1
    def keyboard_on_key_down(self,window,keycode,text,modifiers):
        if keycode[1]=="up":
            if self._history:
                self._hidx=min(self._hidx+1,len(self._history)-1)
                self.text=self._history[-(self._hidx+1)]; self.cursor=(len(self.text),0)
            return True
        if keycode[1]=="down":
            if self._hidx>0:
                self._hidx-=1
                self.text=self._history[-(self._hidx+1)]; self.cursor=(len(self.text),0)
            elif self._hidx==0: self._hidx=-1; self.text=""
            return True
        return super().keyboard_on_key_down(window,keycode,text,modifiers)
    def add_history(self,text):
        if text and (not self._history or self._history[-1]!=text):
            self._history.append(text)
            if len(self._history)>50: self._history.pop(0)
        self._hidx=-1

# ── Main App ──────────────────────────────────────────────────────────────────
class VedaApp(App):
    title="VEDA v15 — Zenith Edition"

    def build(self):
        Window.clearcolor=(*_S["bg"],1)
        root=FloatLayout()
        TAB_H=64

        # OUTER: tab bar on top, main content below
        outer=BoxLayout(orientation="vertical",size_hint=(1,1))

        # ── TOP TAB BAR ───────────────────────────────────────────────────────
        bar=BoxLayout(size_hint=(1,None),height=TAB_H)
        with bar.canvas.before:
            self._bc=Color(*_S["bg2"],1)
            self._br=Rectangle(pos=bar.pos,size=bar.size)
        bar.bind(pos=lambda i,v:setattr(self._br,"pos",v),
                 size=lambda i,v:setattr(self._br,"size",v))

        # Left: brand + status info
        info=BoxLayout(size_hint=(None,1),width=490,padding=[14,6],spacing=10)
        self.lbl_veda=Label(text="[b]VEDA[/b]",markup=True,font_size=26,
                            color=(*_S["primary"],1),size_hint=(None,1),width=80)
        self.lbl_mode_badge=Label(text="[*] SURYA NET",font_size=12,bold=True,
                                  color=(*_S["online"],1),size_hint=(None,1),width=130)
        self.lbl_cpu=Label(text="CPU 0%",font_size=11,color=(*_S["sub"],1),
                           size_hint=(None,1),width=68)
        self.conn_dot=ConnDot(size_hint=(None,None),width=14,height=14)
        self.lbl_clock=LiveClock(font_size=12,size_hint=(None,1),width=82)
        info.add_widget(self.lbl_veda)
        info.add_widget(self.lbl_mode_badge)
        info.add_widget(Widget(size_hint=(None,1),width=6))
        info.add_widget(self.lbl_cpu)
        info.add_widget(self.conn_dot)
        info.add_widget(Widget(size_hint=(None,1),width=4))
        info.add_widget(self.lbl_clock)
        bar.add_widget(info)

        # Tab buttons (Chat active by default)
        _TABS=[("CHAT","Chat",0),("HIST","History",1),
               ("ALMS","Reminders",2),("SYS","System",3),("CFG","Settings",4)]
        self._tab_btns=[]; self._active_tab=0
        for ico,name,idx in _TABS:
            is_first=(idx==0)
            b=Button(text=f"{ico}  {name}",font_size=12,bold=True,
                     halign="center",valign="middle",
                     background_color=(0,0,0,0),
                     color=(*_S["primary"],1) if is_first else (*_S["sub"],1))
            # FIX: store color ref on button for updates
            with b.canvas.before:
                # FIX: store Color object on button, not just in local var
                b._tab_bg_color=Color(*_S["tab_act"],1) if is_first else Color(0,0,0,0)
                b._tab_bg_rect=Rectangle(pos=b.pos,size=b.size)
            b.bind(pos=lambda i,v:setattr(i._tab_bg_rect,"pos",v),
                   size=lambda i,v:setattr(i._tab_bg_rect,"size",v))
            b.bind(on_press=lambda inst,i=idx:self._switch_tab(i))
            self._tab_btns.append(b); bar.add_widget(b)

        # AI Chat panel button (far right)
        self.btn_ai=Button(text="[AI]\nPanel",font_size=11,bold=True,
                           size_hint=(None,1),width=72,
                           background_color=(*_S["accent"],0.90),color=(1,1,1,1))
        self.btn_ai.bind(on_press=lambda *_:self._ai_panel.toggle())
        bar.add_widget(self.btn_ai)
        outer.add_widget(bar)

        # ── MAIN CONTENT: sidebar | left orb | right tabs ─────────────────────
        content=BoxLayout(orientation="horizontal",size_hint=(1,1))

        # SIDEBAR (left-most, collapsible icon nav)
        self._sidenav=SideNav(app_ref=self, size_hint=(None,1),
                              width=SideNav.COLLAPSED_W)
        content.add_widget(self._sidenav)

        # LEFT panel (44%): orb, state labels, mic bar, mode btn, input row
        left=BoxLayout(orientation="vertical",size_hint=(0.44,1))
        self.vis=Visualiser(size_hint=(1,1)); left.add_widget(self.vis)

        self.lbl_state=Label(text="*  Ready — say  Hey Veda",font_size=14,italic=True,
                             color=(*_S["text"],0.85),size_hint=(1,None),height=38,
                             halign="center")
        left.add_widget(self.lbl_state)

        self.lbl_heard=Label(text="",font_size=12,italic=True,color=(*_S["sub"],0.65),
                             size_hint=(1,None),height=22,halign="center")
        left.add_widget(self.lbl_heard)

        self.mic_bar=MicBar(size_hint=(1,None),height=18)
        left.add_widget(self.mic_bar)

        self.btn_mode=Button(text="[*] SURYA NET  —  tap to go offline",
                             font_size=13,bold=True,
                             size_hint=(1,None),height=44,
                             background_color=(*_S["primary"],0.15),
                             color=(*_S["primary"],1))
        self.btn_mode.bind(on_press=self._toggle_mode)
        left.add_widget(self.btn_mode)

        # Input row: [=] quick | text field | GO >>
        inp_row=BoxLayout(size_hint=(1,None),height=50,padding=[8,4],spacing=6)
        with inp_row.canvas.before:
            self._irc=Color(*_S["bg2"],1)
            self._irr=Rectangle(pos=inp_row.pos,size=inp_row.size)
        inp_row.bind(pos=lambda i,v:setattr(self._irr,"pos",v),
                     size=lambda i,v:setattr(self._irr,"size",v))

        self.btn_quick=Button(text="[=]",font_size=22,bold=True,
                              size_hint=(None,1),width=48,
                              background_color=(*_S["card2"],1),
                              color=(*_S["primary"],1))
        self.btn_quick.bind(on_press=lambda *_:self._quick_panel.toggle())

        self.txt=HistoryInput(hint_text="Type a command…  or say  Hey Veda",
                              multiline=False,font_size=13,
                              background_color=(*_S["card"],1),
                              foreground_color=(*_S["text"],1),
                              hint_text_color=(*_S["sub"],0.30),
                              cursor_color=(*_S["primary"],1),
                              padding=[12,12])
        self.txt.bind(on_text_validate=self._on_type)

        self.btn_go=Button(text="GO >>",font_size=13,bold=True,
                           size_hint=(None,1),width=64,
                           background_color=(*_S["accent"],1),color=(1,1,1,1))
        self.btn_go.bind(on_press=self._on_type)

        inp_row.add_widget(self.btn_quick)
        inp_row.add_widget(self.txt)
        inp_row.add_widget(self.btn_go)
        left.add_widget(inp_row)
        content.add_widget(left)

        # RIGHT panel (56%): stacked tab panels in FloatLayout
        right=FloatLayout(size_hint=(0.56,1))
        with right.canvas.before:
            self._rtc=Color(*_S["bg"],1)
            self._rtr=Rectangle(pos=right.pos,size=right.size)
        right.bind(pos=lambda i,v:setattr(self._rtr,"pos",v),
                   size=lambda i,v:setattr(self._rtr,"size",v))

        # FIX: _tab_panel now stores per-panel bg color/rect to avoid closure bug
        def _make_tab_panel(widget):
            """Add bg canvas.before to widget and return (Color, Rect)."""
            with widget.canvas.before:
                c=Color(*_S["bg"],1)
                r=Rectangle(pos=widget.pos,size=widget.size)
            # Capture c and r correctly via default args
            widget.bind(pos=lambda i,v,_r=r:setattr(_r,"pos",v),
                        size=lambda i,v,_r=r:setattr(_r,"size",v))
            return c,r

        # Tab 0: Chat (visible)
        self.chat=ChatLog(size_hint=(1,1),pos_hint={"x":0,"y":0},
                          bar_color=(*_S["accent"],0.5),
                          bar_inactive_color=(*_S["sub"],0.2))
        self._cc,_=_make_tab_panel(self.chat)
        right.add_widget(self.chat)

        # Tab 1: History
        self._hist_chat=ChatLog(size_hint=(1,1),pos_hint={"x":0,"y":0},
                                opacity=0,disabled=True)
        self._hcc,_=_make_tab_panel(self._hist_chat)
        right.add_widget(self._hist_chat)

        # Tab 2: Reminders
        self._rem_tab=RemindersTab(size_hint=(1,1),pos_hint={"x":0,"y":0},
                                   opacity=0,disabled=True)
        self._rmc,_=_make_tab_panel(self._rem_tab)
        right.add_widget(self._rem_tab)

        # Tab 3: System Monitor
        self._sys_tab=BoxLayout(orientation="vertical",size_hint=(1,1),
                                pos_hint={"x":0,"y":0},
                                opacity=0,disabled=True,
                                padding=[14,12],spacing=10)
        self._sysc,_=_make_tab_panel(self._sys_tab)
        self._sys_tab.add_widget(
            Label(text="[b][SYS] System Monitor[/b]",markup=True,font_size=16,
                  color=(*_S["primary"],1),size_hint=(1,None),height=34))
        self._cpu_lbl2=Label(text="CPU: --",font_size=15,bold=True,
                             color=(*_S["primary"],1),size_hint=(1,None),height=28)
        self._ram_lbl2=Label(text="RAM: --",font_size=15,bold=True,
                             color=(*_S["teal"],1),size_hint=(1,None),height=28)
        self._bat_lbl2=Label(text="Battery: --",font_size=13,
                             color=(*_S["sub"],1),size_hint=(1,None),height=24)
        self._sys_graph=SysMonWidget(size_hint=(1,1))
        _ol=Label(text="[b]Offline stack:[/b] Vosk STT  +  Ollama AI  +  cached data",
                  markup=True,font_size=12,halign="left",valign="top",
                  size_hint=(1,None),height=30,color=(*_S["sub"],0.75))
        _ol.bind(width=lambda i,v:setattr(i,"text_size",(v-10,None)))
        for w in [self._cpu_lbl2,self._ram_lbl2,self._bat_lbl2,self._sys_graph,_ol]:
            self._sys_tab.add_widget(w)
        right.add_widget(self._sys_tab)

        # Tab 4: Settings
        self._settings_tab=SettingsTab(size_hint=(1,1),pos_hint={"x":0,"y":0},
                                       opacity=0,disabled=True)
        self._stc,_=_make_tab_panel(self._settings_tab)
        right.add_widget(self._settings_tab)

        content.add_widget(right)
        outer.add_widget(content)
        root.add_widget(outer)

        # ── Overlays (above everything) ───────────────────────────────────────
        # QuickPanel: anchored to bottom-left corner of root FloatLayout
        self._quick_panel=QuickPanel(size_hint=(None,None),width=420,height=450,
                                     pos=(0,0))
        root.add_widget(self._quick_panel)

        self._ai_panel=AIChatPanel(size_hint=(1,1),pos_hint={"x":0,"y":0})
        root.add_widget(self._ai_panel)

        self._toast=ToastOverlay(size_hint=(1,1),pos_hint={"x":0,"y":0})
        root.add_widget(self._toast)

        Clock.schedule_interval(self._theme_tick,1/10)
        Clock.schedule_once(self._check_first_run,1.5)
        return root

    # ── First run welcome messages ────────────────────────────────────────────
    def _check_first_run(self,dt):
        if CFG.get("first_run",True):
            CFG["first_run"]=False; _save_cfg()
            for text in [
                "Welcome to VEDA v15 — Zenith Edition!",
                "Say 'Hey Veda' then anything — talk naturally",
                "Online: GPT-4o-mini (add API key in [CFG] Settings)",
                "Offline: Ollama + 500 built-in knowledge facts",
                "Screenshot + vision AI, timers, reminders, music",
                "Quick Actions: big icon cards for common tasks",
                "Dynamic voice orb reacts to your speech energy!",
            ]: self.chat.add_bubble("SYS","sys",text,"")

    # ── Tab switching ─────────────────────────────────────────────────────────
    def _switch_tab(self,idx):
        self._active_tab=idx
        tabs=[self.chat,self._hist_chat,self._rem_tab,self._sys_tab,self._settings_tab]
        for i,w in enumerate(tabs):
            vis=(i==idx)
            w.opacity=1.0 if vis else 0.0
            w.disabled=not vis
        for i,b in enumerate(self._tab_btns):
            act=(i==idx)
            b.color=(*_S["primary"],1) if act else (*_S["sub"],1)
            # FIX: update Color object stored on button
            b._tab_bg_color.rgba=(*_S["tab_act"],1) if act else (0,0,0,0)
        # Update sidenav highlight
        if hasattr(self,"_sidenav"): self._sidenav.set_active_tab(idx)
        if idx==1: self._load_history()
        if idx==2: self._rem_tab.refresh()

    def _load_history(self):
        self._hist_chat.clear()
        for role,content,src in db_load_history(60,conv_only=True):
            r2="you" if role=="user" else "ai"
            w2="YOU" if role=="user" else "VEDA"
            self._hist_chat.add_bubble(w2,r2,content[:140],src,False)

    # ── Mode toggle ───────────────────────────────────────────────────────────
    def _toggle_mode(self,*_):
        if _active_mode()=="surya":
            threading.Thread(target=_set_nirvana,daemon=True).start()
        else:
            threading.Thread(target=_set_surya,daemon=True).start()

    # ── Text input ────────────────────────────────────────────────────────────
    def _on_type(self,*_):
        t=self.txt.text.strip()
        if t:
            self.txt.add_history(t); self.txt.text=""
            threading.Thread(target=execute,args=(t,),daemon=True).start()

    # ── Theme tick ────────────────────────────────────────────────────────────
    def _theme_tick(self,dt):
        with _MORPH_LOCK: mt=_vb._MORPH
        prev=getattr(self,"_last_mt",None)
        if prev is None or abs(mt-prev)>0.005:
            self._apply_theme()
        self._last_mt=mt

    def _apply_theme(self):
        pal=T()
        Window.clearcolor=(*pal["bg"],1)
        self.lbl_veda.color=(*pal["primary"],1)
        self.lbl_state.color=(*pal["text"],0.85)
        self.lbl_heard.color=(*pal["sub"],0.65)
        self.lbl_cpu.color=(*pal["sub"],1)
        self.btn_ai.background_color=(*pal["accent"],0.90)
        self.btn_go.background_color=(*pal["accent"],1)
        self._bc.rgba=(*pal["bg2"],1)        # tab bar bg
        self._rtc.rgba=(*pal["bg"],1)        # right panel bg
        self._cc.rgba=(*pal["bg"],1)         # chat tab bg
        self._hcc.rgba=(*pal["bg"],1)        # history tab bg
        self._rmc.rgba=(*pal["bg"],1)        # reminders tab bg
        self._sysc.rgba=(*pal["bg"],1)       # system tab bg
        self._stc.rgba=(*pal["bg"],1)        # settings tab bg
        self._irc.rgba=(*pal["bg2"],1)       # input row bg
        self._cpu_lbl2.color=(*pal["primary"],1)
        self._ram_lbl2.color=(*pal["teal"],1)
        self._bat_lbl2.color=(*pal["sub"],1)
        self.txt.background_color=(*pal["card"],1)
        self.txt.foreground_color=(*pal["text"],1)
        self.txt.hint_text_color=(*pal["sub"],0.30)
        self.txt.cursor_color=(*pal["primary"],1)
        self.btn_mode.color=(*pal["primary"],1)
        self.btn_mode.background_color=(*pal["primary"],0.15)

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def on_start(self):
        _seed_knowledge()
        threading.Thread(target=_stt_worker,    daemon=True).start()
        threading.Thread(target=_tts_worker,    daemon=True).start()
        threading.Thread(target=voice_loop,     daemon=True).start()
        threading.Thread(target=_sysmon_worker, daemon=True).start()
        threading.Thread(target=_reminder_worker,daemon=True).start()

    def on_stop(self):
        _APP_RUNNING.clear()

    # ── Public API (called by backend _ui bridge) ─────────────────────────────
    def set_status(self,text): self.lbl_state.text=text

    def set_heard(self,text):
        self.lbl_heard.text=f'"{text[:65]}{"…" if len(text)>65 else ""}"'

    def set_energy(self,e):
        self.mic_bar.set_energy(e); self.vis.set_energy(e)

    def set_online_dot(self,v): self.conn_dot.set_online(v)

    def show_toast(self,text): self._toast.show(text)

    def show_offline_warning(self,text):
        # BUG-11: chat only, no duplicate popup
        self.chat.add_bubble("SYS","sys",f"⚠️ {text}","")

    def add_bubble(self,who,role,text,src,save=True):
        self.chat.add_bubble(who,role,text,src,save)

    def reminder_due(self,label):
        if label: self.show_toast(f"[ALM] {label}")
        if self._active_tab==2: self._rem_tab.refresh()

    def update_sysmon(self,data):
        self._sys_graph.update(data)
        cpu=data.get("cpu",0); ram=data.get("ram",0)
        batt=data.get("batt",-1); plug=data.get("plug",True)
        self.lbl_cpu.text=f"CPU {cpu:.0f}%"
        self._cpu_lbl2.text=f"CPU: {cpu:.1f}%"
        self._ram_lbl2.text=f"RAM: {ram:.1f}%"
        if batt>=0:
            self._bat_lbl2.text=(f"Battery: {batt}%  "
                                  f"{'(charging)' if plug else '(on battery)'}")

    def stream_chunk(self,chunk):
        if chunk=="__START__": self.chat.start_stream()
        else: self.chat.append_stream(chunk)

    def stream_end(self): self.chat.end_stream()

    def wake_flash(self): self.vis.wake_flash()

    def set_state(self,state):
        self.vis.set_state(state)
        self.lbl_state.text={
            "listening":"[MIC] Listening...",
            "speaking": "[SPK] Speaking...",
            "thinking": "[...] Thinking...",
            "ready":    "*  Ready — say  Hey Veda"
        }.get(state,state)
        if state=="ready": self.lbl_heard.text=""

    def set_mode(self,mode):
        self.vis.set_mode(mode)
        if mode=="surya":
            self.lbl_mode_badge.text="[*] SURYA NET"
            self.lbl_mode_badge.color=(*_S["online"],1)
            self.btn_mode.text="[*] SURYA NET  —  tap to go offline"
            self.btn_mode.color=(*_S["primary"],1)
            self.chat.add_bubble("SYS","sys","Connected — Surya Net online","")
        else:
            self.lbl_mode_badge.text="[~] NIRVANA"
            self.lbl_mode_badge.color=(*_S["offline"],1)
            self.btn_mode.text="[~] NIRVANA MODE  —  tap to go online"
            self.btn_mode.color=(*_N["primary"],1)
            vs=_vosk_status()
            msg={
                "ok":       "Offline — Vosk STT active 🔕",
                "no_model": "Offline — download Vosk model 🔕"
            }.get(vs,"Offline — pip install vosk 🔕")
            self.chat.add_bubble("SYS","sys",msg,"")


if __name__=="__main__":
    try:
        VedaApp().run()
    except Exception as e:
        import traceback
        print("\n[CRASH]",e); traceback.print_exc()
        input("\nPress Enter to close…")
