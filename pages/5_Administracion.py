import streamlit as st
import pandas as pd
from utils.auth import require_admin, current_profile
from utils.db import get_authed_client

st.set_page_config(page_title="Administración", page_icon="⚙️", layout="wide")
require_admin()  # solo 'admin' puede entrar a esta página, ni siquiera 'editor'
profile = current_profile()
client = get_authed_client()

st.title("⚙️ Administración de usuarios")
st.caption("Asigna roles al equipo. El rol 'editor' es un respaldo del administrador: "
           "puede editar precios e insumos/rubros y ve todos los proyectos, pero no "
           "puede cambiar roles de otros usuarios.")

ROLES = {"usuario": "Usuario", "editor": "Editor (respaldo admin)", "admin": "Administrador"}

usuarios = client.table("profiles").select("*").order("email").execute().data
if not usuarios:
    st.warning("No se encontraron usuarios.")
    st.stop()

total_admins = sum(1 for u in usuarios if u["rol"] == "admin")

st.divider()

for u in usuarios:
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 2, 2])
        with c1:
            st.markdown(f"**{u.get('nombre') or '(sin nombre)'}**")
            st.caption(u["email"])
        with c2:
            es_yo = u["id"] == profile["id"]
            st.caption("Este es tu propio usuario" if es_yo else "")
        with c3:
            nuevo_rol = st.selectbox(
                "Rol",
                list(ROLES.keys()),
                index=list(ROLES.keys()).index(u["rol"]),
                format_func=lambda r: ROLES[r],
                key=f"rol_{u['id']}",
                label_visibility="collapsed",
            )
            if nuevo_rol != u["rol"]:
                # Evita quedarse sin ningún administrador en el sistema
                se_quita_ultimo_admin = (
                    u["rol"] == "admin" and nuevo_rol != "admin" and total_admins <= 1
                )
                if se_quita_ultimo_admin:
                    st.error("Debe existir al menos un administrador.")
                else:
                    if st.button("Guardar", key=f"save_{u['id']}"):
                        client.table("profiles").update({"rol": nuevo_rol}).eq("id", u["id"]).execute()
                        st.success(f"Rol actualizado a {ROLES[nuevo_rol]}.")
                        st.rerun()
