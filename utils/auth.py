import streamlit as st
from utils.db import get_client, get_authed_client


def login(email: str, password: str) -> tuple[bool, str]:
    client = get_client()
    try:
        res = client.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state["auth_session"] = res.session
        st.session_state["auth_user"] = res.user
        return True, ""
    except Exception as e:
        return False, str(e)


def signup(email: str, password: str, nombre: str) -> tuple[bool, str]:
    client = get_client()
    try:
        client.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"nombre": nombre}},
        })
        return True, "Cuenta creada. Revisa tu correo para confirmar (si la confirmación está activada) e inicia sesión."
    except Exception as e:
        return False, str(e)


def logout():
    for key in ("auth_session", "auth_user", "profile"):
        st.session_state.pop(key, None)


def current_profile() -> dict | None:
    """Devuelve el perfil (con rol) del usuario logueado, cacheado en sesión."""
    if "profile" in st.session_state:
        return st.session_state["profile"]

    user = st.session_state.get("auth_user")
    if not user:
        return None

    client = get_authed_client()
    resp = client.table("profiles").select("*").eq("id", user.id).single().execute()
    st.session_state["profile"] = resp.data
    return resp.data


def require_login():
    """Detiene la ejecución de la página si no hay sesión activa."""
    if not st.session_state.get("auth_session"):
        st.warning("Debes iniciar sesión para ver esta página.")
        st.stop()


def require_admin():
    require_login()
    profile = current_profile()
    if not profile or profile.get("rol") != "admin":
        st.error("Esta sección es solo para administradores.")
        st.stop()


def es_staff(profile: dict | None) -> bool:
    """True si el perfil es admin o editor (editor = respaldo del admin:
    puede editar precios/rubros y ve todos los proyectos del equipo, pero
    no administra roles de otros usuarios)."""
    return bool(profile) and profile.get("rol") in ("admin", "editor")


def require_staff():
    require_login()
    profile = current_profile()
    if not es_staff(profile):
        st.error("Esta sección es solo para administradores o editores.")
        st.stop()
