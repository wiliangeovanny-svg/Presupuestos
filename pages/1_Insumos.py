import streamlit as st
import pandas as pd
from utils.auth import require_login, current_profile, es_staff
from utils.db import get_authed_client

st.set_page_config(page_title="Insumos", page_icon="🧱", layout="wide")
require_login()
profile = current_profile()
puede_editar = es_staff(profile)  # admin o editor pueden gestionar insumos
client = get_authed_client()

st.title("🧱 Biblioteca de Insumos")
st.caption("Materiales, mano de obra y equipos usados para construir los APU de cada rubro.")

TIPOS = {"material": "Material", "mano_obra": "Mano de Obra", "equipo": "Equipo"}

# --- Formulario para crear insumo (solo admin) ---
if puede_editar:
    with st.expander("➕ Agregar nuevo insumo"):
        with st.form("nuevo_insumo", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            tipo = c1.selectbox("Tipo", list(TIPOS.keys()), format_func=lambda t: TIPOS[t])
            descripcion = c2.text_input("Descripción")
            unidad = c3.text_input("Unidad", placeholder="m3, kg, hora, u...")
            precio = c4.number_input("Precio", min_value=0.0, step=0.01, format="%.4f")
            if st.form_submit_button("Guardar insumo"):
                if descripcion and unidad:
                    client.table("insumos").insert({
                        "tipo": tipo, "descripcion": descripcion,
                        "unidad": unidad, "precio": precio,
                        "created_by": profile["id"],
                    }).execute()
                    st.success("Insumo agregado.")
                    st.rerun()
                else:
                    st.error("Descripción y unidad son obligatorias.")
else:
    st.info("Solo un administrador o editor puede agregar o editar insumos. Puedes consultarlos abajo.")

st.divider()

# --- Listado y edición ---
data = client.table("insumos").select("*").order("tipo").order("descripcion").execute().data

if not data:
    st.warning("Aún no hay insumos registrados.")
    st.stop()

df = pd.DataFrame(data)
filtro_tipo = st.multiselect("Filtrar por tipo", list(TIPOS.keys()), format_func=lambda t: TIPOS[t])
if filtro_tipo:
    df = df[df["tipo"].isin(filtro_tipo)]

busqueda = st.text_input("Buscar por descripción")
if busqueda:
    df = df[df["descripcion"].str.contains(busqueda, case=False, na=False)]

df_view = df[["tipo", "descripcion", "unidad", "precio"]].copy()
df_view["tipo"] = df_view["tipo"].map(TIPOS)
df_view.columns = ["Tipo", "Descripción", "Unidad", "Precio"]

if puede_editar:
    st.caption("Edita precios directamente en la tabla y presiona 'Guardar cambios'.")
    edited = st.data_editor(
        df_view, use_container_width=True, hide_index=True, key="editor_insumos",
        disabled=["Tipo", "Descripción", "Unidad"],
    )
    if st.button("💾 Guardar cambios de precios"):
        cambios = 0
        for idx, row in edited.iterrows():
            nuevo_precio = float(row["Precio"])
            original_id = df.loc[idx, "id"]
            if nuevo_precio != df.loc[idx, "precio"]:
                client.table("insumos").update({"precio": nuevo_precio}).eq("id", original_id).execute()
                cambios += 1
        if cambios:
            st.success(f"Se actualizaron {cambios} precio(s). Esto afecta a todos los APU que usan estos insumos.")
            st.rerun()
        else:
            st.info("No hubo cambios.")

    st.divider()
    st.subheader("🗑️ Eliminar un insumo")

    opciones_eliminar = {
        f"[{TIPOS[row['tipo']]}] {row['descripcion']} ({row['unidad']})": row["id"]
        for _, row in df.iterrows()
    }
    etiqueta_sel = st.selectbox("Selecciona el insumo a eliminar", ["—"] + list(opciones_eliminar.keys()))

    if etiqueta_sel != "—":
        insumo_id = opciones_eliminar[etiqueta_sel]

        # Verifica si el insumo está siendo usado en algún rubro antes de permitir borrarlo
        usos = (
            client.table("rubro_insumos")
            .select("rubro_id, rubros(descripcion)")
            .eq("insumo_id", insumo_id)
            .execute().data
        )

        if usos:
            rubros_usando = sorted({u["rubros"]["descripcion"] for u in usos if u.get("rubros")})
            st.warning(
                "No se puede eliminar: este insumo está siendo usado en "
                f"{len(rubros_usando)} rubro(s): " + ", ".join(rubros_usando) + ". "
                "Quítalo primero de esos rubros desde 'Rubros / APU' y vuelve a intentarlo."
            )
        else:
            st.caption("Este insumo no está siendo usado en ningún rubro actualmente. Es seguro eliminarlo.")
            confirmar = st.checkbox(f"Confirmo que quiero eliminar «{etiqueta_sel}» permanentemente", key="confirma_borrado_insumo")
            if st.button("🗑️ Eliminar insumo", disabled=not confirmar):
                client.table("insumos").delete().eq("id", insumo_id).execute()
                st.success("Insumo eliminado.")
                st.rerun()
else:
    st.dataframe(df_view, use_container_width=True, hide_index=True)
