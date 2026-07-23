"""Shared helpers for all dashboard pages."""
import os
import requests
import streamlit as st

def get_api_url() -> str:
    # st.secrets takes priority (Streamlit Cloud), then env var, then localhost
    try:
        return st.secrets["API_URL"]
    except Exception:
        return os.getenv("API_URL", "http://localhost:8000")


@st.cache_data(ttl=300)
def api_get(path: str, params: dict | None = None):
    url = get_api_url() + path
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def api_post(path: str, payload: dict):
    url = get_api_url() + path
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()
    return r.json()
