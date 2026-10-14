import streamlit as st
import pandas as pd
from utils.auth import require_login, current_profile, es_staff
from utils.db import get_authed_client
from utils.calculos import calcular_apu
from utils.exportar import exportar_apu_excel

st.set_page_config(page_title="Rubros / APU", page_icon="📐", layout="wide")
require_login()
profile = current_profile()
puede_editar = es_staff(profile)  # admin o editor pueden gestionar rubros/APU
client = get_authed_client()

st.title("📐 Rubros y Análisis de Precios Unitarios (APU)")
st.caption("Cada rubro es una plantilla reutilizable: define qué insumos y en qué cantidad lo componen.")

insumos_data = client.table("insumos").select("*").order("descripcion").execute().data
if not insumos_data:
    st.warning("Primero registra insumos en la sección 'Insumos'.")
    st.stop()
insumos_df = pd.DataFrame(insumos_data)

rubros_data = client.table("rubros").select("*").order("descripcion").execute().data

# --- Crear nuevo rubro (solo admin) ---
if puede_editar:
    with st.expander("➕ Crear nuevo rubro"):
        with st.form("nuevo_rubro", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            codigo = c1.text_input("Código", placeholder="ALB-001")
            descripcion = c2.text_input("Descripción del rubro")
            unidad = c3.text_input("Unidad", placeholder="u, m, m2...")
            indirectos = c4.number_input("Indirectos + Utilidad (%)", min_value=0.0, value=20.0, step=1.0)
            if st.form_submit_button("Crear rubro"):
                if descripcion and unidad:
                    client.table("rubros").insert({
                        "codigo": codigo, "descripcion": descripcion, "unidad": unidad,
                        "indirectos_utilidad": indirectos, "created_by": profile["id"],
                    }).execute()
                    st.success("Rubro creado. Selecciónalo abajo para agregarle insumos.")
                    st.rerun()
                else:
                    st.error("Descripción y unidad son obligatorias.")

st.divider()

if not rubros_data:
    st.info("Aún no hay rubros creados.")
    st.stop()

rubro_map = {f"{r.get('codigo') or ''} — {r['descripcion']}".strip(" —"): r for r in rubros_data}
seleccion = st.selectbox("Selecciona un rubro", list(rubro_map.keys()))
rubro = rubro_map[seleccion]

col_izq, col_der = st.columns([3, 2])

with col_izq:
    st.subheader(f"Composición: {rubro['descripcion']} ({rubro['unidad']})")

    if puede_editar:
        with st.form("agregar_insumo_rubro"):
            c1, c2, c3 = st.columns([3, 1, 1])
            insumo_label = c1.selectbox(
                "Insumo",
                insumos_df.apply(lambda r: f"[{r['tipo']}] {r['descripcion']} ({r['unidad']}) - {r['precio']}", axis=1),
            )
            cantidad = c2.number_input("Cantidad", min_value=0.0, value=1.0, step=0.1)
            rendimiento = c3.number_input("Rendimiento (h/unidad)", min_value=0.0, value=0.0, step=0.01,
                                            help="Solo aplica a mano de obra y equipo")
            if st.form_submit_button("Agregar al rubro"):
                idx = list(insumos_df.apply(
                    lambda r: f"[{r['tipo']}] {r['descripcion']} ({r['unidad']}) - {r['precio']}", axis=1
                )).index(insumo_label)
                insumo_id = insumos_df.iloc[idx]["id"]
                client.table("rubro_insumos").insert({
                    "rubro_id": rubro["id"], "insumo_id": insumo_id,
                    "cantidad": cantidad, "rendimiento": rendimiento or None,
                }).execute()
                st.success("Insumo agregado al rubro.")
                st.rerun()

    detalle_data = (
        client.table("rubro_insumos")
        .select("*, insumos(tipo, descripcion, unidad, precio)")
        .eq("rubro_id", rubro["id"])
        .execute().data
    )

    if not detalle_data:
        st.info("Este rubro todavía no tiene insumos asignados.")
        items = []
    else:
        items = []
        for d in detalle_data:
            ins = d["insumos"]
            items.append({
                "rubro_insumo_id": d["id"],
                "tipo": ins["tipo"],
                "descripcion": ins["descripcion"],
                "unidad": ins["unidad"],
                "precio": ins["precio"],
                "cantidad": d["cantidad"],
                "rendimiento": d.get("rendimiento"),
            })

        tabla = pd.DataFrame(items)[["tipo", "descripcion", "unidad", "precio", "cantidad", "rendimiento"]]
        tabla.columns = ["Tipo", "Descripción", "Unidad", "Precio", "Cantidad", "Rendim. (h/u)"]
        st.dataframe(tabla, use_container_width=True, hide_index=True)

        if puede_editar:
            eliminar_opciones = {f"{it['descripcion']} ({it['tipo']})": it["rubro_insumo_id"] for it in items}
            a_eliminar = st.selectbox("Quitar insumo del rubro", ["—"] + list(eliminar_opciones.keys()))
            if a_eliminar != "—" and st.button("🗑️ Quitar del rubro"):
                client.table("rubro_insumos").delete().eq("id", eliminar_opciones[a_eliminar]).execute()
                st.rerun()

with col_der:
    st.subheader("Resumen del APU")
    if items:
        resultado = calcular_apu(items, rubro["indirectos_utilidad"])
        st.metric("Costo directo", f"$ {resultado['costo_directo']:.4f}")
        st.metric(f"Indirectos + Utilidad ({rubro['indirectos_utilidad']}%)",
                   f"$ {resultado['monto_indirectos_utilidad']:.4f}")
        st.metric("💰 Precio unitario", f"$ {resultado['precio_unitario']:.4f}")

        excel_bytes = exportar_apu_excel(rubro, resultado)
        st.download_button(
            "⬇️ Descargar APU en Excel", data=excel_bytes,
            file_name=f"APU_{rubro.get('codigo') or rubro['descripcion']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.write("Agrega insumos para ver el cálculo.")

    if puede_editar:
        st.divider()
        with st.expander("🗑️ Eliminar este rubro"):
            usos = (
                client.table("presupuesto_items")
                .select("proyecto_id, proyectos(nombre)")
                .eq("rubro_id", rubro["id"])
                .execute().data
            )
            if usos:
                proyectos_usando = sorted({u["proyectos"]["nombre"] for u in usos if u.get("proyectos")})
                st.warning(
                    "No se puede eliminar: este rubro está siendo usado en el presupuesto de "
                    f"{len(proyectos_usando)} proyecto(s): " + ", ".join(proyectos_usando) + ". "
                    "Quítalo primero de esos presupuestos y vuelve a intentarlo."
                )
            else:
                st.caption(
                    "Este rubro no está siendo usado en ningún presupuesto actualmente. "
                    "Al eliminarlo también se borra su composición de insumos (el APU)."
                )
                confirmar_rubro = st.checkbox(
                    f"Confirmo que quiero eliminar el rubro «{rubro['descripcion']}» permanentemente",
                    key="confirma_borrado_rubro",
                )
                if st.button("🗑️ Eliminar rubro", disabled=not confirmar_rubro):
                    client.table("rubros").delete().eq("id", rubro["id"]).execute()
                    st.success("Rubro eliminado.")
                    st.rerun()
