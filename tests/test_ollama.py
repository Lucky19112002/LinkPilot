from config import Config
from ollama_manager import OllamaManager


def test_ollama_manager_constructs():
    manager = OllamaManager(Config())
    assert isinstance(manager.is_installed(), bool)
