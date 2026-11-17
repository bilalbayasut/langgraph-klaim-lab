"""Pengaturan dari environment (.env). Satu tempat untuk semua angka yang bisa diubah."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _project_root() -> Path:
    """Folder yang berisi pyproject.toml (supaya path data benar dari mana pun kode dijalankan)."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


ROOT = _project_root()
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    llm_mode: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_temperature: float
    max_revisi: int
    runtime_dir: Path
    data_dir: Path
    hr_gagal_n_kali: int
    crash_setelah_bayar: bool
    mock_draf_pertama_kurang: bool


def get_settings() -> Settings:
    """Dibaca ulang setiap dipanggil, supaya test bisa mengubah env dengan monkeypatch."""
    runtime = Path(os.getenv("RUNTIME_DIR", "./runtime"))
    if not runtime.is_absolute():
        runtime = ROOT / runtime
    runtime.mkdir(parents=True, exist_ok=True)
    return Settings(
        llm_mode=os.getenv("LLM_MODE", "mock"),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://ai.sumopod.com/v1"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", "glm-5.3-flash"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
        max_revisi=int(os.getenv("MAX_REVISI", "2")),
        runtime_dir=runtime,
        data_dir=ROOT / "data",
        hr_gagal_n_kali=int(os.getenv("HR_GAGAL_N_KALI", "0")),
        crash_setelah_bayar=os.getenv("CRASH_SETELAH_BAYAR", "0") == "1",
        mock_draf_pertama_kurang=os.getenv("MOCK_DRAF_PERTAMA_KURANG", "1") == "1",
    )
