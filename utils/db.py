"""
Conexión a Supabase. Requiere en .streamlit/secrets.toml:

[supabase]
url = "https://xxxx.supabase.co"
anon_key = "eyJ..."
"""
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["anon_key"]
    return create_client(url, key)


def get_authed_client() -> Client:
    """
    Devuelve un cliente Supabase con la sesión del usuario actual aplicada,
    necesario para que las políticas RLS (Row Level Security) funcionen
    correctamente en cada request.
    """
    client = get_client()
    session = st.session_state.get("auth_session")
    if session:
        client.postgrest.auth(session.access_token)
    return client
