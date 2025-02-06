import openai
import os
from dotenv import load_dotenv

# Load the API key from the .env file
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

try:
    # This will list available models using your API key.
    models = openai.Model.list()
    print("API key is working. Here are some available models:")
    for model in models['data']:
        print(model['id'])
except Exception as e:
    print("Error with the API key:", e)
