import os
from xmlrpc import client
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

load_dotenv() # Load environment variables from .env file
API_KEY = os.environ.get("GEMINI_API_KEY")

def main():
    client = genai.Client()

    for level in ("low", "high"):
        interaction = client.interactions.create(
            model="gemini-3.8-flash",
            input="Explain how AI works in a sentence.",
            generation_config={
                "thinking_level": level
            },
        )
        usage = interaction.usage
        print(interaction.output_text)
        if usage:
            print(f"input tokens: {usage.total_input_tokens}")
            print(f"thought tokens: {usage.total_thought_tokens}")
            print(f"output tokens: {usage.total_output_tokens}")
            print(f"total tokens: {usage.total_tokens}")

if __name__ == "__main__":
    main()