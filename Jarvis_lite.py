import speech_recognition as sr
import pyttsx3
import whisper
import webbrowser
import subprocess
import os
import datetime
import threading
import time
from langdetect import detect

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.clock import Clock


# =============================
# INITIALIZE SYSTEMS
# =============================

recognizer = sr.Recognizer()
engine = pyttsx3.init()

WAKE_WORD = "jarvis"

print("Loading Whisper model...")
model = whisper.load_model("base")

conversation_memory = []

ui_status = None
ui_log = None


# =============================
# LOG SYSTEM
# =============================

def log(text):

    print(text)

    if ui_log:
        Clock.schedule_once(
            lambda dt: setattr(
                ui_log,
                "text",
                ui_log.text + text + "\n"
            )
        )


# =============================
# STATUS UPDATE
# =============================

def update_status(text):

    if ui_status:
        Clock.schedule_once(
            lambda dt: setattr(ui_status, "text", text)
        )


# =============================
# SPEAK
# =============================

def speak(text):

    update_status("Speaking")

    log("Jarvis: " + text)

    engine.say(text)
    engine.runAndWait()

    update_status("Listening")


# =============================
# LISTEN
# =============================

def listen():

    with sr.Microphone() as source:

        recognizer.adjust_for_ambient_noise(source)

        try:
            audio = recognizer.listen(source, timeout=5)
        except:
            return ""

    try:
        text = recognizer.recognize_google(audio)
        log("User: " + text)
        return text.lower()

    except:
        return ""


# =============================
# LISTEN WITH RETRY
# =============================

def listen_with_retry(attempts=3):

    for i in range(attempts):

        command = listen()

        if command:
            return command

        log(f"Voice attempt {i+1} failed")

    return None


# =============================
# WHISPER LISTEN
# =============================

def whisper_listen():

    with sr.Microphone() as source:

        audio = recognizer.listen(source)

    with open("temp.wav", "wb") as f:
        f.write(audio.get_wav_data())

    result = model.transcribe("temp.wav")

    text = result["text"].lower()

    log("User: " + text)

    return text


# =============================
# TEXT COMMAND FALLBACK
# =============================

def text_command():

    log("Voice failed. Please type your command.")

    cmd = input("Enter command: ")

    log("User (typed): " + cmd)

    return cmd.lower()


# =============================
# LANGUAGE DETECTION
# =============================

def detect_language(text):

    try:
        return detect(text)
    except:
        return "unknown"


# =============================
# COMMAND PARSER
# =============================

def parse_command(command):

    if "open" in command:

        target = command.split("open", 1)[1].strip()
        return ("open", target)

    if "search" in command:

        query = command.split("search", 1)[1].strip()
        return ("search", query)

    if "play" in command:

        query = command.split("play", 1)[1].strip()
        return ("play", query)

    if "time" in command:

        return ("time", None)

    if "shutdown" in command:

        return ("shutdown", None)

    return ("ai", command)


# =============================
# ACTION EXECUTOR
# =============================

def execute(action, target):

    if action == "open":

        try:
            subprocess.Popen(target)
        except:
            webbrowser.open("https://" + target + ".com")

        speak("Opening " + target)

    elif action == "search":

        webbrowser.open("https://google.com/search?q=" + target)
        speak("Searching " + target)

    elif action == "play":

        webbrowser.open("https://youtube.com/results?search_query=" + target)
        speak("Playing " + target)

    elif action == "time":

        now = datetime.datetime.now().strftime("%H:%M")
        speak("The time is " + now)

    elif action == "shutdown":

        speak("Shutting down")
        os.system("shutdown /s /t 5")

    elif action == "ai":

        speak("I am still learning that request")


# =============================
# COMMAND PROCESSOR
# =============================

def process_command(cmd):

    tasks = cmd.split(" and ")

    for task in tasks:

        action, target = parse_command(task)

        execute(action, target)


# =============================
# ASSISTANT LOOP
# =============================

def assistant_loop():

    speak("Jarvis online")

    while True:

        command = listen_with_retry()

        if command is None:

            update_status("Text Mode")

            command = text_command()

        if not command:
            continue

        if WAKE_WORD in command:

            log("Wake word detected")

            command = command.replace(WAKE_WORD, "").strip()

            speak("Yes")

            if command == "":
                command = whisper_listen()

            language = detect_language(command)

            log("Language: " + language)

            conversation_memory.append(command)

            process_command(command)

        time.sleep(0.3)


# =============================
# GUI
# =============================

class JarvisUI(BoxLayout):

    def __init__(self, **kwargs):

        super().__init__(orientation="vertical", spacing=10, padding=10, **kwargs)

        title = Label(
            text="JARVIS",
            font_size=48
        )

        global ui_status
        ui_status = Label(text="Initializing...")

        global ui_log
        ui_log = TextInput(
            readonly=True,
            font_size=16
        )

        self.cmd_input = TextInput(
            hint_text="Type command and press Enter",
            size_hint=(1, None),
            height=40
        )

        self.cmd_input.bind(on_text_validate=self.submit_text_command)

        self.add_widget(title)
        self.add_widget(ui_status)
        self.add_widget(ui_log)
        self.add_widget(self.cmd_input)

        Clock.schedule_once(lambda dt: self.start_assistant())

    def start_assistant(self):

        thread = threading.Thread(target=assistant_loop)

        thread.daemon = True

        thread.start()

    def submit_text_command(self, instance):

        command = instance.text.lower()

        instance.text = ""

        log("User (typed): " + command)

        process_command(command)


# =============================
# APP
# =============================

class JarvisApp(App):

    def build(self):

        return JarvisUI()


JarvisApp().run()
