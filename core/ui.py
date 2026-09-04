from __future__ import annotations

import streamlit as st

from core.config import get_settings
from core.db import DatabaseNotConfigured, get_client


def page_header(title: str, caption: str | None = None) -> None:
    st.title(title)
    if caption:
        st.caption(caption)


def require_client():
    settings = get_settings()
    if not settings.database_configured:
        st.warning("Supabase aún no está configurado. Copia `.streamlit/secrets.example.toml` a `secrets.toml` o configura Secrets en Streamlit Cloud.")
        st.code('SUPABASE_URL = "https://...supabase.co"\nSUPABASE_SERVICE_ROLE_KEY = "..."', language="toml")
        st.stop()
    try:
        return get_client(settings.supabase_url, settings.supabase_key)
    except DatabaseNotConfigured as exc:
        st.error(str(exc))
        st.stop()
