import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq
from typing import Optional, List, Dict, Any

# Load environment variables from backend/.env
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_FILE)


class GroqClient:
    """Client for interacting with Groq's LLM API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the Groq client.

        Args:
            api_key: Groq API key (defaults to GROQ_API_KEY environment variable)
            model: Model name (defaults to GROQ_MODEL environment variable)
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY not found in environment variables. "
                "Set it in backend/.env or pass it explicitly."
            )

        self.model = model or os.getenv("GROQ_MODEL", "mixtral-8x7b-32768")
        self.client = Groq(api_key=self.api_key)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a chat completion using Groq.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 - 1.0)
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters for Groq API

        Returns:
            Dictionary with 'response' (str) and raw 'raw_response' (Dict)

        Example:
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Explain quantum computing."}
            ]
            result = client.chat_completion(messages)
            print(result["response"])
        """
        try:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            response = chat_completion.choices[0].message.content

            return {
                "response": response,
                "raw_response": chat_completion.to_dict(),
                "model": self.model,
                "usage": {
                    "prompt_tokens": chat_completion.usage.prompt_tokens,
                    "completion_tokens": chat_completion.usage.completion_tokens,
                    "total_tokens": chat_completion.usage.total_tokens
                }
            }

        except Exception as e:
            raise Exception(f"Groq API error: {str(e)}")

    def simple_query(self, prompt: str, system_message: str = "You are a helpful assistant.") -> str:
        """
        Simple one-shot query interface.

        Args:
            prompt: User's question or prompt
            system_message: System role message

        Returns:
            String response from the model
        """
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]

        result = self.chat_completion(messages)
        return result["response"]

    def get_available_models(self) -> List[str]:
        """Get list of available models from Groq API."""
        try:
            models = self.client.models.list()
            return [model.id for model in models.data]
        except Exception as e:
            raise Exception(f"Failed to fetch available models: {str(e)}")


# Singleton instance for easy import
try:
    groq_client = GroqClient()
except ValueError:
    # Initialize without API key for now, will raise error when used
    groq_client = None