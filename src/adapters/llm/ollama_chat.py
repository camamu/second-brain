"""Class to test LangChain with Ollama."""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

SYSTEM_PROMPT = "You are a helpful assistant."


class OllamaChat:
    """Wraps LangChain + Ollama for basic conversational testing.

    Attributes:
        model: Name of the Ollama model to use.
        base_url: Ollama API endpoint.
        chat: Underlying ChatOllama instance.
    """

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.7,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.chat = ChatOllama(
            model=self.model,
            base_url=self.base_url,
            temperature=temperature,
        )
        self._messages: list = [SystemMessage(content=system_prompt)]

    def send(self, user_message: str) -> str:
        """Send a message and return the assistant response.

        Args:
            user_message: The text to send to the model.

        Returns:
            The model's response string.
        """
        self._messages.append(HumanMessage(content=user_message))
        response = self.chat.invoke(self._messages)
        self._messages.append(response)
        return response.content
