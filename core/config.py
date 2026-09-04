from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import streamlit as st


@dataclass(frozen=True)
class Settings:
    supabase_url: Optional[str]
    supabase_key: Optional[str]
    app_name: str = "ICC Control Territorial"

    @property
    def database_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


def _secret(name: str) -> Optional[str]:
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return value or os.getenv(name)


def get_settings() -> Settings:
    return Settings(
        supabase_url=_secret("SUPABASE_URL"),
        supabase_key=_secret("SUPABASE_SERVICE_ROLE_KEY") or _secret("SUPABASE_KEY"),
    )
