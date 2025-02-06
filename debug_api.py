import openai
import os
from dotenv import load_dotenv

# Force dotenv to override any existing environment variables with values from .env
load_dotenv(override=True)

api_key = os.getenv("OPENAI_API_KEY")
print("Loaded API Key:", api_key)

try:
    # This will list available models using your API key.
    models = openai.Model.list()
    print("API key is working. Here are some available models:")
    for model in models['data']:
        print(model['id'])
except Exception as e:
    print("Error with the API key:", e)