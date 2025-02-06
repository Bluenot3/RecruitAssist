import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, Canvas, filedialog
import openai
import os
import json
from dotenv import load_dotenv
import subprocess
import webbrowser
import threading
import schedule
import time
from datetime import datetime
import speech_recognition as sr
import pyttsx3
import requests
from playsound import playsound

try:
    from ttkthemes import ThemedTk
except ImportError:
    ThemedTk = tk.Tk

# -----------------------------
# Load Environment Variables
# -----------------------------
load_dotenv(override=True)
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = os.getenv("MODEL_NAME", "gpt-4o")
openai.api_key = DEFAULT_API_KEY

# Eleven Labs credentials (optional)
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")  # e.g., "29vD33N1CtxCmqQRPOHJ"

# -----------------------------
# Global Settings & Usage Tracking
# -----------------------------
current_temperature = 0.7
current_max_tokens = 150
total_prompt_tokens = 0
total_completion_tokens = 0
cost_per_1k_prompt = 0.03    # dollars per 1K prompt tokens
cost_per_1k_completion = 0.06  # dollars per 1K completion tokens

# For API Key Manager: keys stored in a JSON file.
API_KEYS_FILE = "api_keys.json"
api_keys = []  # will be loaded from file

usage_lock = threading.Lock()

# -----------------------------
# Helper Functions: API Key Manager
# -----------------------------
def load_api_keys():
    global api_keys
    if os.path.exists(API_KEYS_FILE):
        try:
            with open(API_KEYS_FILE, "r") as f:
                api_keys = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load API keys: {e}")
    else:
        api_keys = [{
            "provider": "OpenAI",
            "key": DEFAULT_API_KEY,
            "model": DEFAULT_MODEL,
            "active": True,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0}
        }]
        save_api_keys()

def save_api_keys():
    try:
        with open(API_KEYS_FILE, "w") as f:
            json.dump(api_keys, f, indent=2)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save API keys: {e}")

def get_active_key():
    for entry in api_keys:
        if entry.get("active", False):
            return entry
    return None

def add_api_key(provider, key, model):
    for entry in api_keys:
        entry["active"] = False
    new_entry = {
        "provider": provider,
        "key": key,
        "model": model,
        "active": True,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0}
    }
    api_keys.append(new_entry)
    save_api_keys()
    update_api_key_listbox()
    set_active_key(new_entry)

def set_active_key(entry):
    openai.api_key = entry["key"]
    global DEFAULT_MODEL
    DEFAULT_MODEL = entry["model"]

def update_api_key_listbox():
    api_key_listbox.delete(0, tk.END)
    for i, entry in enumerate(api_keys):
        active_flag = "[Active]" if entry.get("active", False) else ""
        display_text = f"{entry['provider']} - {entry['model']} {active_flag}"
        api_key_listbox.insert(tk.END, display_text)

def toggle_active_key(event=None):
    selection = api_key_listbox.curselection()
    if selection:
        idx = selection[0]
        for entry in api_keys:
            entry["active"] = False
        api_keys[idx]["active"] = True
        set_active_key(api_keys[idx])
        save_api_keys()
        update_api_key_listbox()
        messagebox.showinfo("API Key Changed", f"Active key set to {api_keys[idx]['provider']} - {api_keys[idx]['model']}.")

# -----------------------------
# Helper: Update Usage from API Response
# -----------------------------
def update_usage(usage):
    global total_prompt_tokens, total_completion_tokens
    with usage_lock:
        total_prompt_tokens += usage.get("prompt_tokens", 0)
        total_completion_tokens += usage.get("completion_tokens", 0)
    active = get_active_key()
    if active:
        active["usage"]["prompt_tokens"] += usage.get("prompt_tokens", 0)
        active["usage"]["completion_tokens"] += usage.get("completion_tokens", 0)
        save_api_keys()
        update_api_key_usage_display()

# -----------------------------
# Chat Tab Functions (Text & Voice)
# -----------------------------
def chat_get_response():
    prompt = chat_input.get("1.0", tk.END).strip()
    if not prompt:
        return
    try:
        response = openai.ChatCompletion.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=current_temperature,
            max_tokens=current_max_tokens
        )
        if "usage" in response:
            update_usage(response["usage"])
        output = response.choices[0].message["content"]
    except Exception as e:
        output = f"Error: {e}"
    chat_output.config(state=tk.NORMAL)
    chat_output.insert(tk.END, f"> {prompt}\n{output}\n\n")
    chat_output.config(state=tk.DISABLED)
    chat_input.delete("1.0", tk.END)
    update_usage_tracker_tab()

def clear_chat():
    chat_output.config(state=tk.NORMAL)
    chat_output.delete("1.0", tk.END)
    chat_output.config(state=tk.DISABLED)

# Voice Chat Function with Eleven Labs fallback
def voice_chat():
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    engine = pyttsx3.init()
    elevenlabs_key = ELEVENLABS_API_KEY
    elevenlabs_voice = os.getenv("ELEVENLABS_VOICE_ID")  # should be set in .env; if empty, fallback occurs
    try:
        with microphone as source:
            voice_status_label.config(text="Listening...")
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
        voice_status_label.config(text="Processing...")
        user_text = recognizer.recognize_google(audio)
        voice_input_text.config(state=tk.NORMAL)
        voice_input_text.delete("1.0", tk.END)
        voice_input_text.insert(tk.END, user_text)
        voice_input_text.config(state=tk.DISABLED)
        response = openai.ChatCompletion.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_text}
            ],
            temperature=current_temperature,
            max_tokens=current_max_tokens
        )
        if "usage" in response:
            update_usage(response["usage"])
        output = response.choices[0].message["content"]
        voice_output_text.config(state=tk.NORMAL)
        voice_output_text.delete("1.0", tk.END)
        voice_output_text.insert(tk.END, output)
        voice_output_text.config(state=tk.DISABLED)
        if elevenlabs_key and elevenlabs_voice:
            tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{elevenlabs_voice}"
            headers = {
                "xi-api-key": elevenlabs_key,
                "Content-Type": "application/json"
            }
            payload = {
                "text": output,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }
            r = requests.post(tts_url, json=payload, headers=headers)
            if r.status_code == 200:
                with open("temp_audio.mp3", "wb") as f:
                    f.write(r.content)
                playsound("temp_audio.mp3")
            else:
                engine.say(output)
                engine.runAndWait()
        else:
            engine.say(output)
            engine.runAndWait()
        update_usage_tracker_tab()
        voice_status_label.config(text="Idle")
    except sr.WaitTimeoutError:
        voice_status_label.config(text="Idle")
        messagebox.showerror("Voice Error", "Listening timed out. Please try again.")
    except sr.UnknownValueError:
        voice_status_label.config(text="Idle")
        messagebox.showerror("Voice Error", "Could not understand the audio. Please try again.")
    except Exception as e:
        voice_status_label.config(text="Idle")
        messagebox.showerror("Voice Error", f"An error occurred: {e}")

# -----------------------------
# Local Commands Tab Function
# -----------------------------
def execute_local_command():
    command = local_cmd_entry.get().strip()
    if not command:
        return
    try:
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
    except subprocess.CalledProcessError as e:
        result = f"Command failed: {e.output}"
    local_cmd_output.config(state=tk.NORMAL)
    local_cmd_output.insert(tk.END, f"> {command}\n{result}\n\n")
    local_cmd_output.config(state=tk.DISABLED)
    local_cmd_entry.delete(0, tk.END)

# -----------------------------
# Web Browser Tab Function
# -----------------------------
def open_webpage():
    url = web_entry.get().strip()
    if not url:
        messagebox.showwarning("Input Required", "Please enter a URL.")
        return
    if not url.startswith("http"):
        url = "http://" + url
    webbrowser.open(url)

# -----------------------------
# Settings Tab Function
# -----------------------------
def update_settings():
    global current_temperature, current_max_tokens, cost_per_1k_prompt, cost_per_1k_completion
    try:
        current_temperature = float(temp_scale.get())
        current_max_tokens = int(tokens_entry.get())
        cost_per_1k_prompt = float(prompt_cost_entry.get())
        cost_per_1k_completion = float(completion_cost_entry.get())
        messagebox.showinfo("Settings Updated", "Settings have been updated.")
    except Exception as e:
        messagebox.showerror("Error", f"Invalid settings: {e}")

# -----------------------------
# File Search Tab Functions
# -----------------------------
def search_files():
    query = file_search_entry.get().strip().lower()
    if not query:
        messagebox.showwarning("Input Required", "Please enter a search query.")
        return
    file_search_listbox.delete(0, tk.END)
    results = []
    search_dirs = [
        r"C:\Users\AlexLeschik\Desktop",
        r"C:\Users\AlexLeschik\OneDrive - BGCGW",
        r"C:\Users\AlexLeschik\Documents"
    ]
    for directory in search_dirs:
        for root_dir, dirs, files in os.walk(directory):
            for file in files:
                if query in file.lower():
                    full_path = os.path.join(root_dir, file)
                    results.append(full_path)
    if results:
        for item in results:
            file_search_listbox.insert(tk.END, item)
    else:
        file_search_listbox.insert(tk.END, "No matching files found.")

def open_selected_file(event):
    selection = file_search_listbox.curselection()
    if selection:
        file_path = file_search_listbox.get(selection[0])
        try:
            os.startfile(file_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {e}")

# -----------------------------
# Recruiter Agent Tab Functions
# -----------------------------
def run_recruiter_agent():
    prompt = "Generate a daily summary of candidate profiles and schedule follow-up interviews."
    try:
        response = openai.ChatCompletion.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are a recruiting assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=current_temperature,
            max_tokens=current_max_tokens
        )
        if "usage" in response:
            update_usage(response["usage"])
        output = response.choices[0].message["content"]
    except Exception as e:
        output = f"Error: {e}"
    recruiter_output.config(state=tk.NORMAL)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    recruiter_output.insert(tk.END, f"[{timestamp}] {output}\n\n")
    recruiter_output.config(state=tk.DISABLED)
    update_usage_tracker_tab()

def schedule_recruiter_agent():
    schedule_time = schedule_entry.get().strip()  # expected "HH:MM"
    if not schedule_time:
        messagebox.showwarning("Input Required", "Please enter a schedule time in HH:MM format.")
        return
    try:
        schedule.clear("recruiter")
        schedule.every().day.at(schedule_time).do(run_recruiter_agent).tag("recruiter")
        messagebox.showinfo("Scheduled", f"Recruiter Agent scheduled daily at {schedule_time}.")
    except Exception as e:
        messagebox.showerror("Error", f"Could not schedule: {e}")

def run_schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(30)

# -----------------------------
# Usage Tracker Tab Functions
# -----------------------------
def update_usage_tracker_tab():
    with usage_lock:
        total_tokens = total_prompt_tokens + total_completion_tokens
        cost_prompt = (total_prompt_tokens / 1000) * cost_per_1k_prompt
        cost_completion = (total_completion_tokens / 1000) * cost_per_1k_completion
        total_cost = cost_prompt + cost_completion
        usage_text = (
            f"Total Prompt Tokens: {total_prompt_tokens}\n"
            f"Total Completion Tokens: {total_completion_tokens}\n"
            f"Total Tokens: {total_tokens}\n"
            f"Estimated Cost: ${total_cost:.4f}\n"
        )
    usage_tracker_text.config(state=tk.NORMAL)
    usage_tracker_text.delete("1.0", tk.END)
    usage_tracker_text.insert(tk.END, usage_text)
    usage_tracker_text.config(state=tk.DISABLED)
    update_api_key_usage_display()

def update_api_key_usage_display():
    active = get_active_key()
    if active:
        usage_str = (f"Usage for active key:\nPrompt: {active['usage']['prompt_tokens']} tokens\n"
                     f"Completion: {active['usage']['completion_tokens']} tokens")
        api_key_usage_label.config(text=usage_str)
    else:
        api_key_usage_label.config(text="No active key selected.")

# -----------------------------
# Build the Main GUI with Enhanced Styling
# -----------------------------
root = ThemedTk(theme="arc")
root.title("Dreamcore Recruiter Assistant")
root.geometry("1000x800")

# Create a gradient background using Canvas
canvas = Canvas(root, width=1000, height=800)
canvas.pack(fill="both", expand=True)
r1, g1, b1 = (40, 40, 60)
r2, g2, b2 = (90, 90, 120)
steps = 100
for i in range(steps):
    r = int(r1 + (r2 - r1) * (i / steps))
    g = int(g1 + (g2 - g1) * (i / steps))
    b = int(b1 + (b2 - b1) * (i / steps))
    color = f"#{r:02x}{g:02x}{b:02x}"
    y0 = int((800 / steps) * i)
    y1 = int((800 / steps) * (i + 1))
    canvas.create_rectangle(0, y0, 1000, y1, outline="", fill=color)
    
notebook = ttk.Notebook(root)
notebook.place(relx=0.02, rely=0.02, relwidth=0.96, relheight=0.96)

# --- Tab 1: Chat ---
chat_frame = ttk.Frame(notebook)
notebook.add(chat_frame, text="Chat")

chat_input_label = ttk.Label(chat_frame, text="Enter your prompt:")
chat_input_label.pack(pady=(10, 0))
chat_input = tk.Text(chat_frame, height=5, width=80)
chat_input.pack(padx=10, pady=5)
chat_send_button = ttk.Button(chat_frame, text="Send", command=chat_get_response)
chat_send_button.pack(pady=5)
clear_chat_button = ttk.Button(chat_frame, text="Clear Chat", command=clear_chat)
clear_chat_button.pack(pady=5)
chat_output_label = ttk.Label(chat_frame, text="Conversation:")
chat_output_label.pack(pady=(10, 0))
chat_output = scrolledtext.ScrolledText(chat_frame, height=15, width=80, state=tk.DISABLED)
chat_output.pack(padx=10, pady=5)

# --- Tab 2: Local Commands ---
local_frame = ttk.Frame(notebook)
notebook.add(local_frame, text="Local Commands")

local_cmd_label = ttk.Label(local_frame, text="Enter a local command (shell command):")
local_cmd_label.pack(pady=(10, 0))
local_cmd_entry = ttk.Entry(local_frame, width=80)
local_cmd_entry.pack(padx=10, pady=5)
local_cmd_button = ttk.Button(local_frame, text="Execute", command=execute_local_command)
local_cmd_button.pack(pady=5)
local_cmd_output_label = ttk.Label(local_frame, text="Command Output:")
local_cmd_output_label.pack(pady=(10, 0))
local_cmd_output = scrolledtext.ScrolledText(local_frame, height=10, width=80, state=tk.DISABLED)
local_cmd_output.pack(padx=10, pady=5)

# --- Tab 3: Web Browser ---
web_frame = ttk.Frame(notebook)
notebook.add(web_frame, text="Web Browser")

web_label = ttk.Label(web_frame, text="Enter a URL to open:")
web_label.pack(pady=(10, 0))
web_entry = ttk.Entry(web_frame, width=80)
web_entry.pack(padx=10, pady=5)
web_button = ttk.Button(web_frame, text="Open Webpage", command=open_webpage)
web_button.pack(pady=5)

# --- Tab 4: Settings ---
settings_frame = ttk.Frame(notebook)
notebook.add(settings_frame, text="Settings")

temp_label = ttk.Label(settings_frame, text="Temperature (0.0 - 1.0):")
temp_label.pack(pady=(10, 0))
temp_scale = ttk.Scale(settings_frame, from_=0.0, to=1.0, orient=tk.HORIZONTAL)
temp_scale.set(current_temperature)
temp_scale.pack(padx=10, pady=5)
tokens_label = ttk.Label(settings_frame, text="Max Tokens (e.g., 150):")
tokens_label.pack(pady=(10, 0))
tokens_entry = ttk.Entry(settings_frame, width=20)
tokens_entry.insert(0, str(current_max_tokens))
tokens_entry.pack(padx=10, pady=5)
prompt_cost_label = ttk.Label(settings_frame, text="Cost per 1K Prompt Tokens ($):")
prompt_cost_label.pack(pady=(10, 0))
prompt_cost_entry = ttk.Entry(settings_frame, width=20)
prompt_cost_entry.insert(0, str(cost_per_1k_prompt))
prompt_cost_entry.pack(padx=10, pady=5)
completion_cost_label = ttk.Label(settings_frame, text="Cost per 1K Completion Tokens ($):")
completion_cost_label.pack(pady=(10, 0))
completion_cost_entry = ttk.Entry(settings_frame, width=20)
completion_cost_entry.insert(0, str(cost_per_1k_completion))
completion_cost_entry.pack(padx=10, pady=5)
update_settings_button = ttk.Button(settings_frame, text="Update Settings", command=update_settings)
update_settings_button.pack(pady=10)

# --- Tab 5: File Search ---
file_search_frame = ttk.Frame(notebook)
notebook.add(file_search_frame, text="File Search")

file_search_label = ttk.Label(file_search_frame, text="Enter file search query:")
file_search_label.pack(pady=(10, 0))
file_search_entry = ttk.Entry(file_search_frame, width=80)
file_search_entry.pack(padx=10, pady=5)
file_search_button = ttk.Button(file_search_frame, text="Search", command=search_files)
file_search_button.pack(pady=5)
file_search_listbox = tk.Listbox(file_search_frame, width=100, height=15)
file_search_listbox.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
file_search_listbox.bind("<Double-Button-1>", open_selected_file)

# --- Tab 6: Recruiter Agent ---
recruiter_frame = ttk.Frame(notebook)
notebook.add(recruiter_frame, text="Recruiter Agent")

recruiter_info = ttk.Label(recruiter_frame, text="Schedule daily recruiter tasks and view outputs.")
recruiter_info.pack(pady=(10, 0))
schedule_label = ttk.Label(recruiter_frame, text="Enter daily schedule time (HH:MM, 24hr):")
schedule_label.pack(pady=(10, 0))
schedule_entry = ttk.Entry(recruiter_frame, width=20)
schedule_entry.insert(0, "09:00")
schedule_entry.pack(padx=10, pady=5)
schedule_button = ttk.Button(recruiter_frame, text="Schedule Agent Task", command=schedule_recruiter_agent)
schedule_button.pack(pady=5)
run_agent_button = ttk.Button(recruiter_frame, text="Run Agent Now", command=run_recruiter_agent)
run_agent_button.pack(pady=5)
recruiter_output_label = ttk.Label(recruiter_frame, text="Agent Output:")
recruiter_output_label.pack(pady=(10, 0))
recruiter_output = scrolledtext.ScrolledText(recruiter_frame, height=10, width=80, state=tk.DISABLED)
recruiter_output.pack(padx=10, pady=5)

# --- Tab 7: Usage Tracker ---
usage_tracker_frame = ttk.Frame(notebook)
notebook.add(usage_tracker_frame, text="Usage Tracker")

usage_tracker_label = ttk.Label(usage_tracker_frame, text="API Usage Summary:")
usage_tracker_label.pack(pady=(10, 0))
usage_tracker_text = scrolledtext.ScrolledText(usage_tracker_frame, height=10, width=80, state=tk.DISABLED)
usage_tracker_text.pack(padx=10, pady=5)
update_usage_tracker_button = ttk.Button(usage_tracker_frame, text="Refresh Usage", command=update_usage_tracker_tab)
update_usage_tracker_button.pack(pady=5)

# --- Tab 8: API Key Manager ---
api_key_manager_frame = ttk.Frame(notebook)
notebook.add(api_key_manager_frame, text="API Key Manager")

api_key_listbox = tk.Listbox(api_key_manager_frame, width=80, height=8)
api_key_listbox.pack(padx=10, pady=5)
api_key_listbox.bind("<<ListboxSelect>>", toggle_active_key)
api_key_usage_label = ttk.Label(api_key_manager_frame, text="Usage for active key will appear here.")
api_key_usage_label.pack(pady=(5, 0))

add_key_frame = ttk.Frame(api_key_manager_frame)
add_key_frame.pack(pady=10)
provider_label = ttk.Label(add_key_frame, text="Provider:")
provider_label.grid(row=0, column=0, padx=5)
provider_entry = ttk.Entry(add_key_frame, width=20)
provider_entry.grid(row=0, column=1, padx=5)
key_label = ttk.Label(add_key_frame, text="API Key:")
key_label.grid(row=0, column=2, padx=5)
key_entry = ttk.Entry(add_key_frame, width=40)
key_entry.grid(row=0, column=3, padx=5)
model_label = ttk.Label(add_key_frame, text="Model:")
model_label.grid(row=0, column=4, padx=5)
model_entry = ttk.Entry(add_key_frame, width=20)
model_entry.grid(row=0, column=5, padx=5)
add_key_button = ttk.Button(api_key_manager_frame, text="Add/Set Active API Key",
                            command=lambda: add_api_key(provider_entry.get().strip(),
                                                        key_entry.get().strip(),
                                                        model_entry.get().strip()))
add_key_button.pack(pady=5)

load_api_keys()
update_api_key_listbox()
update_api_key_usage_display()

# --- Tab 9: Voice Chat ---
voice_frame = ttk.Frame(notebook)
notebook.add(voice_frame, text="Voice Chat")

voice_instructions = ttk.Label(voice_frame, text="Click 'Start Voice Chat' and speak your prompt.")
voice_instructions.pack(pady=(10, 0))
start_voice_button = ttk.Button(voice_frame, text="Start Voice Chat", 
                                command=lambda: threading.Thread(target=voice_chat, daemon=True).start())
start_voice_button.pack(pady=5)
voice_status_label = ttk.Label(voice_frame, text="Idle")
voice_status_label.pack(pady=5)
voice_input_label = ttk.Label(voice_frame, text="Recognized Input:")
voice_input_label.pack(pady=(10, 0))
voice_input_text = scrolledtext.ScrolledText(voice_frame, height=3, width=80, state=tk.DISABLED)
voice_input_text.pack(padx=10, pady=5)
voice_output_label = ttk.Label(voice_frame, text="Response:")
voice_output_label.pack(pady=(10, 0))
voice_output_text = scrolledtext.ScrolledText(voice_frame, height=5, width=80, state=tk.DISABLED)
voice_output_text.pack(padx=10, pady=5)

# -----------------------------
# Start Background Scheduler Thread for Recruiter Agent
# -----------------------------
scheduler_thread = threading.Thread(target=run_schedule_loop, daemon=True)
scheduler_thread.start()

# -----------------------------
# Start the Main Event Loop
# -----------------------------
root.mainloop()
