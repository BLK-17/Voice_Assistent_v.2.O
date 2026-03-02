import tkinter as tk
import speech_recognition as sr
import pyttsx3
import datetime
import webbrowser
import os
import threading
import subprocess  # Import subprocess for opening applicationsgit init

# Initialize the recognizer and the text-to-speech engine
recognizer = sr.Recognizer()
tts_engine = pyttsx3.init()

# Define specific paths
DESKTOP_PATH = r"C:\Users\91903\Desktop"
DOCUMENTS_PATH = r"C:\Users\91903\OneDrive\Documents"
# Function to convert text to speech
def speak(text):
    tts_engine.say(text)
    tts_engine.runAndWait()

# Function to get the current time
def tell_time():
    now = datetime.datetime.now().strftime("%H:%M")
    speak(f"The time is {now}")

# Function to get the current date
def tell_date():
    today = datetime.datetime.today().strftime("%B %d, %Y")
    speak(f"Today's date is {today}")

# Function to listen and recognize voice commands
def listen():
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
        try:
            command = recognizer.recognize_google(audio)
            print(f"You said: {command}")
            return command.lower()
        except sr.UnknownValueError:
            speak("Sorry, I did not understand that.")
        except sr.RequestError:
            speak("Sorry, I am unable to process your request at the moment.")
        return ""

# Function to open websites in Chrome
def open_website(command):
    chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"  # Update if your path is different
    if "youtube" in command:
        speak("Opening YouTube")
        subprocess.Popen([chrome_path, "https://www.youtube.com"])
        
    elif "gmail" in command:
        speak("Opening Gmail")
        subprocess.Popen([chrome_path, "https://www.gmail.com"])
        
    elif "google" in command:
        speak("Opening Google")
        subprocess.Popen([chrome_path, "https://www.google.com"])
        
    else:
        speak("Website not recognized.")

# Function to open folders
def open_folder(folder_name):
    folders = {
        "desktop": DESKTOP_PATH,
        "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
        "documents": DOCUMENTS_PATH
    }
    folder_path = folders.get(folder_name.lower())
    if folder_path:
        os.startfile(folder_path)
        speak(f"Opening {folder_name.capitalize()}")
    else:
        speak("Folder not recognized.")

# Function to search the web
def search_web(query):
    url = f"https://www.google.com/search?q={query}"
    webbrowser.open(url)
    speak(f"Here are the search results for {query}")

# Function to handle commands
def handle_command(command):
    if "hello" in command:
        speak("Hello! How can I help you?")
    elif "time" in command:
        tell_time()
    elif "date" in command:
        tell_date()
    elif "search" in command:
        query = command.replace("search", "").strip()
        search_web(query)
    elif "open" in command:
        if "file explorer" in command:
            open_file_explorer()  # You might want to define this function as well
        elif any(folder in command for folder in ["desktop", "downloads", "documents"]):
            folder = command.split()[-1]
            open_folder(folder)
        else:
            open_website(command)
    elif "close" in command:
        if "youtube" in command:
            close_application("chrome.exe")
        elif "gmail" in command:
            close_application("chrome.exe")
        elif "google" in command:
            close_application("chrome.exe")
        elif "file explorer" in command:
            close_application("explorer.exe")
    elif "exit" in command:
        speak("Goodbye! See you next time.")
        app.quit()
    else:
        speak("I'm not sure how to help with that.")

# Function to close applications
def close_application(app_name):
    os.system(f"taskkill /im {app_name} /f")
    speak(f"Closing {app_name}")

# Function to start voice assistant in a separate thread
def start_voice_assistant():
    while True:
        command = listen()
        if command:
            handle_command(command)

# Function to handle button click
def on_turn_on():
    label.config(text="Voice Assistant is Turned ON, Give Your Commands...")
    threading.Thread(target=start_voice_assistant, daemon=True).start()

# Create main window
app = tk.Tk()
app.title("Voice Assistant")
app.geometry("700x350")
app.resizable(False, False)
app.config(bg="lightblue")  # Set background color to Light Blue

# Create and place title label with updated font
title_label = tk.Label(app, text="Voice Assistant", font=("Jokerman", 26, "bold"), bg="lightblue")
title_label.pack(pady=20)

# Create and place turn on button
turn_on_button = tk.Button(app, text="Turn ON", font=("Cooper Black", 16), command=on_turn_on)
turn_on_button.pack(pady=20)

# Create and place status label
label = tk.Label(app, text="", font=("Ink Free", 18), bg="lightblue")
label.pack(pady=20)

# Start the Tkinter main loop
app.mainloop()
