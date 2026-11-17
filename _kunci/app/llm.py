"""Lapisan tipis di atas LLM.

- mock : tidak memanggil LLM. Node memberi fungsi `fallback` yang deterministik (gratis, cocok untuk test & Studio).
- live : memanggil endpoint OpenAI-compatible (Sumopod, vLLM, Ollama, ...).
"""

from __future__ import annotations

from typing import Callable, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)


def is_live() -> bool:
    return get_settings().llm_mode == "live"


def chat_model():
    from langchain_openai import ChatOpenAI

    s = get_settings()
    if not s.llm_api_key:
        raise RuntimeError("LLM_MODE=live tetapi LLM_API_KEY kosong. Isi file .env dulu.")
    return ChatOpenAI(model=s.llm_model, base_url=s.llm_base_url, api_key=s.llm_api_key,
                      temperature=s.llm_temperature, timeout=60, max_retries=2)


def structured(schema: type[T], system: str, user: str, fallback: Callable[[], T]) -> T:
    """Output terstruktur (objek Pydantic). Mode mock: kembalikan fallback()."""
    if not is_live():
        return fallback()
    model = chat_model().with_structured_output(schema)
    return model.invoke([SystemMessage(content=system), HumanMessage(content=user)])


def teks(system: str, user: str, fallback: Callable[[], str]) -> str:
    """Output teks bebas. Mode mock: kembalikan fallback()."""
    if not is_live():
        return fallback()
    return chat_model().invoke([SystemMessage(content=system), HumanMessage(content=user)]).content
