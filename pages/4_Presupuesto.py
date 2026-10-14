import streamlit as st
import pandas as pd
from utils.auth import require_login, current_profile, es_staff
from utils.db import get_authed_client
from utils.calculos import calcular_presupuesto
from utils.negocio import calcular_apu_de_rubro, calcular_cronograma_proyecto
from utils.exportar import exportar_presupuesto_excel

st.set_page_config(page_title="Presupuesto", page_icon="💰", layout="wide")
require_login()
profile = current_profile()
client = get_authed_client()

st.title("💰 Presupuesto")
st.caption("Selecciona los rubros de tu proyecto e indica la cantidad de obra de cada uno.")

proyectos = client.table("proyectos").select("*").order("created_at", desc=True).execute().data
if not proyectos:
    st.warning("Primero crea un proyecto en la sección 'Proyectos'.")
    st.stop()

proyecto_map = {p["nombre"]: p for p in proyectos}
seleccion = st.selectbox("Proyecto", list(proyecto_map.keys()))
proyecto = proyecto_map[seleccion]

puede_editar = proyecto["owner_id"] == profile["id"] or es_staff(profile)

rubros = client.table("rubros").select("*").order("descripcion").execute().data
if not rubros:
    st.warning("Aún no hay rubros disponibles. Créalos en la sección 'Rubros / APU'.")
    st.stop()
rubro_map = {f"{r.get('codigo') or ''} — {r['descripcion']} ({r['unidad']})".strip(" —"): r for r in rubros}


# --- Agregar rubro al presupuesto ---
if puede_editar:
    with st.expander("➕ Agregar rubro al presupuesto"):
        with st.form("agregar_rubro_presupuesto", clear_on_submit=True):
            c1, c2 = st.columns([3, 1])
            rubro_label = c1.selectbox("Rubro", list(rubro_map.keys()))
            cantidad_obra = c2.number_input("Cantidad de obra", min_value=0.0, value=1.0, step=0.1)
            if st.form_submit_button("Agregar"):
                rubro_sel = rubro_map[rubro_label]
                client.table("presupuesto_items").insert({
                    "proyecto_id": proyecto["id"],
                    "rubro_id": rubro_sel["id"],
                    "cantidad": cantidad_obra,
                }).execute()
                st.success("Rubro agregado al presupuesto.")
                st.rerun()
else:
    st.info("Solo el dueño del proyecto (o un admin/editor) puede modificar este presupuesto.")

st.divider()

items_bd = (
    client.table("presupuesto_items")
    .select("*, rubros(codigo, descripcion, unidad, indirectos_utilidad)")
    .eq("proyecto_id", proyecto["id"])
    .execute().data
)

if not items_bd:
    st.info("Este proyecto todavía no tiene rubros en su presupuesto.")
    st.stop()

items_presupuesto = []
apus_por_rubro = {}  # rubro_id -> {"rubro": {...}, "resultado": {...}}, uno por cada rubro distinto

for it in items_bd:
    r = it["rubros"]
    rubro_completo = next(rb for rb in rubros if rb["id"] == it["rubro_id"])

    if it["rubro_id"] not in apus_por_rubro:
        apus_por_rubro[it["rubro_id"]] = {
            "rubro": rubro_completo,
            "resultado": calcular_apu_de_rubro(client, rubro_completo),
        }
    precio_unitario = apus_por_rubro[it["rubro_id"]]["resultado"]["precio_unitario"]

    items_presupuesto.append({
        "presupuesto_item_id": it["id"],
        "rubro_descripcion": f"{r.get('codigo') or ''} {r['descripcion']}".strip(),
        "unidad": r["unidad"],
        "cantidad_obra": it["cantidad"],
        "precio_unitario": precio_unitario,
    })

resultado = calcular_presupuesto(items_presupuesto)

tabla = pd.DataFrame(resultado["filas"])[
    ["rubro_descripcion", "unidad", "cantidad_obra", "precio_unitario", "subtotal"]
]
tabla.columns = ["Rubro", "Unidad", "Cantidad", "Precio Unit.", "Subtotal"]
st.dataframe(tabla, use_container_width=True, hide_index=True)

st.metric("💰 TOTAL PRESUPUESTO", f"$ {resultado['total']:,.2f}")

if puede_editar:
    st.divider()
    with st.expander("🗑️ Quitar un rubro del presupuesto"):
        eliminar_opciones = {f"{it['rubro_descripcion']}": it["presupuesto_item_id"] for it in items_presupuesto}
        a_eliminar = st.selectbox("Rubro a quitar", ["—"] + list(eliminar_opciones.keys()))
        if a_eliminar != "—":
            if proyecto.get("requiere_cronograma"):
                st.caption(
                    "⚠️ Este proyecto usa cronograma valorado: si este rubro ya tenía "
                    "periodos planificados, esa planificación también se eliminará."
                )
            confirmar_item = st.checkbox(
                f"Confirmo que quiero quitar «{a_eliminar}» de este presupuesto",
                key="confirma_borrado_presupuesto_item",
            )
            if st.button("🗑️ Quitar del presupuesto", disabled=not confirmar_item):
                client.table("presupuesto_items").delete().eq("id", eliminar_opciones[a_eliminar]).execute()
                st.success("Rubro quitado del presupuesto.")
                st.rerun()

incluir_apus = st.checkbox(
    "Incluir el detalle de cada APU en hojas adicionales del Excel", value=True
)

cronograma_data = None
if proyecto.get("requiere_cronograma"):
    incluir_cronograma = st.checkbox(
        "Incluir el cronograma valorado como hoja adicional del Excel", value=False
    )
    if incluir_cronograma:
        cronograma_data = calcular_cronograma_proyecto(client, proyecto)
        if cronograma_data is None:
            st.warning(
                "El cronograma de este proyecto aún no tiene fecha de inicio configurada "
                "(sección 'Cronograma'), así que no se incluirá en este Excel."
            )

excel_bytes = exportar_presupuesto_excel(
    proyecto, resultado,
    apus=list(apus_por_rubro.values()) if incluir_apus else None,
    cronograma=cronograma_data,
)
st.download_button(
    "⬇️ Descargar presupuesto en Excel", data=excel_bytes,
    file_name=f"Presupuesto_{proyecto['nombre']}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

if proyecto.get("requiere_cronograma"):
    st.caption("📅 Este proyecto usa cronograma valorado — ve a la sección **Cronograma** para planificarlo en el tiempo.")
