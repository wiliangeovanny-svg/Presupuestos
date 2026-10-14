import streamlit as st
import pandas as pd
from utils.auth import require_login, current_profile, es_staff
from utils.db import get_authed_client

st.set_page_config(page_title="Proyectos", page_icon="📁", layout="wide")
require_login()
profile = current_profile()
es_staff_user = es_staff(profile)
client = get_authed_client()

st.title("📁 Proyectos")
st.caption(
    "Cada proyecto agrupa un presupuesto. Solo tú ves tus proyectos"
    + (" (como administrador/editor, ves también los de todo el equipo)." if es_staff_user else ".")
)

with st.expander("➕ Crear nuevo proyecto"):
    with st.form("nuevo_proyecto", clear_on_submit=True):
        nombre = st.text_input("Nombre del proyecto")
        ubicacion = st.text_input("Ubicación")
        descripcion = st.text_area("Descripción (opcional)")
        requiere_cronograma = st.checkbox(
            "Este proyecto necesita cronograma valorado",
            value=False,
            help="Opcional. Si lo activas ahora o más tarde, podrás planificar en el tiempo "
                 "los rubros de este proyecto desde la sección 'Cronograma'.",
        )
        if st.form_submit_button("Crear proyecto"):
            if nombre:
                client.table("proyectos").insert({
                    "nombre": nombre, "ubicacion": ubicacion,
                    "descripcion": descripcion, "owner_id": profile["id"],
                    "requiere_cronograma": requiere_cronograma,
                }).execute()
                st.success("Proyecto creado. Ve a la sección 'Presupuesto' para agregarle rubros.")
                st.rerun()
            else:
                st.error("El nombre es obligatorio.")

st.divider()

proyectos = client.table("proyectos").select("*, profiles(nombre, email)").order("created_at", desc=True).execute().data

if not proyectos:
    st.info("Aún no tienes proyectos. Crea el primero arriba.")
    st.stop()

for p in proyectos:
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.subheader(p["nombre"])
            if p.get("ubicacion"):
                st.caption(f"📍 {p['ubicacion']}")
            if p.get("descripcion"):
                st.write(p["descripcion"])
            if p.get("requiere_cronograma"):
                st.caption("📅 Con cronograma valorado")
            if es_staff_user and p.get("profiles"):
                st.caption(f"Creado por: {p['profiles'].get('nombre') or p['profiles'].get('email')}")
        with c2:
            if p["owner_id"] == profile["id"] or es_staff_user:
                if st.button("🗑️ Eliminar", key=f"del_{p['id']}"):
                    client.table("proyectos").delete().eq("id", p["id"]).execute()
                    st.rerun()
