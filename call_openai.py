import tkinter as tk
from tkinter import scrolledtext
import openai
import os
from dotenv import load_dotenv

# Force dotenv to override any existing environment variables with values from .env
load_dotenv(override=True)

# Set your API key (loaded from the .env file)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Use the GPT-4o model identifier (ensure your account has access to this model)
MODEL_NAME = "gpt-4o"

def get_response():
    # Retrieve the user's prompt from the text widget.
    prompt = prompt_entry.get("1.0", tk.END).strip()
    if not prompt:
        return

    try:
        # Call the OpenAI ChatCompletion endpoint using the GPT-4o model.
        response = openai.ChatCompletion.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        output = response.choices[0].message["content"]
    except Exception as e:
        output = f"Error: {e}"

    # Display the output in the scrollable text area.
    output_text.config(state=tk.NORMAL)
    output_text.delete("1.0", tk.END)
    output_text.insert(tk.END, output)
    output_text.config(state=tk.DISABLED)

# Set up the main Tkinter window.
window = tk.Tk()
window.title("GPT-4o Chatbot Interface")

# Label for the prompt input.
prompt_label = tk.Label(window, text="Enter your prompt:")
prompt_label.pack(pady=(10, 0))

# Text widget where the user enters the prompt.
prompt_entry = tk.Text(window, height=5, width=60)
prompt_entry.pack(padx=10, pady=5)

# Button to send the prompt.
send_button = tk.Button(window, text="Send", command=get_response)
send_button.pack(pady=5)

# Label for the model response.
output_label = tk.Label(window, text="Response:")
output_label.pack(pady=(10, 0))

# Scrollable text widget to display the response.
output_text = scrolledtext.ScrolledText(window, height=10, width=60, state=tk.DISABLED)
output_text.pack(padx=10, pady=5)

# Start the Tkinter event loop.
window.mainloop()
