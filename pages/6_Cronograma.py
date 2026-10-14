from datetime import date
import streamlit as st
import pandas as pd
from utils.auth import require_login, current_profile, es_staff
from utils.db import get_authed_client
from utils.negocio import calcular_apu_de_rubro
from utils.calculos import distribuir_automatico, calcular_cronograma
from utils.fechas import generar_etiquetas
from utils.exportar import exportar_cronograma_excel

st.set_page_config(page_title="Cronograma", page_icon="📅", layout="wide")
require_login()
profile = current_profile()
client = get_authed_client()

st.title("📅 Cronograma Valorado")
st.caption(
    "Función opcional: úsala solo en los proyectos donde necesites planificar la "
    "ejecución del presupuesto en el tiempo. Si no la necesitas, el presupuesto por "
    "sí solo es suficiente."
)

proyectos = client.table("proyectos").select("*").order("created_at", desc=True).execute().data
if not proyectos:
    st.warning("Primero crea un proyecto en la sección 'Proyectos'.")
    st.stop()

proyecto_map = {p["nombre"]: p for p in proyectos}
seleccion = st.selectbox("Proyecto", list(proyecto_map.keys()))
proyecto = proyecto_map[seleccion]
puede_editar = proyecto["owner_id"] == profile["id"] or es_staff(profile)

st.divider()

# --- Activación opcional del cronograma para este proyecto ---
if not proyecto.get("requiere_cronograma"):
    st.info(
        "Este proyecto todavía no tiene activado el cronograma valorado. "
        "Es una función opcional — actívala solo si necesitas planificar este "
        "presupuesto en el tiempo (por periodos)."
    )
    if puede_editar:
        if st.button("📅 Activar cronograma valorado para este proyecto"):
            client.table("proyectos").update({"requiere_cronograma": True}).eq("id", proyecto["id"]).execute()
            st.rerun()
    else:
        st.caption("Solo el dueño del proyecto (o un admin/editor) puede activarlo.")
    st.stop()

# --- Configuración de periodos ---
with st.expander("⚙️ Configuración del cronograma", expanded=not proyecto.get("fecha_inicio")):
    if puede_editar:
        with st.form("config_cronograma"):
            c1, c2, c3 = st.columns(3)
            fecha_inicio = c1.date_input(
                "Fecha de inicio", value=proyecto.get("fecha_inicio") or date.today()
            )
            unidad_periodo = c2.selectbox(
                "Duración del periodo", ["semana", "quincena", "mes"],
                index=["semana", "quincena", "mes"].index(proyecto.get("unidad_periodo") or "mes"),
            )
            num_periodos = c3.number_input(
                "Número de periodos", min_value=1, max_value=60,
                value=proyecto.get("num_periodos") or 12,
            )
            if st.form_submit_button("Guardar configuración"):
                client.table("proyectos").update({
                    "fecha_inicio": fecha_inicio.isoformat(),
                    "unidad_periodo": unidad_periodo,
                    "num_periodos": int(num_periodos),
                }).eq("id", proyecto["id"]).execute()
                st.success("Configuración guardada.")
                st.rerun()
        if st.button("🚫 Desactivar cronograma para este proyecto"):
            client.table("proyectos").update({"requiere_cronograma": False}).eq("id", proyecto["id"]).execute()
            st.rerun()
    else:
        st.caption("Solo el dueño del proyecto (o un admin/editor) puede cambiar esta configuración.")

if not proyecto.get("fecha_inicio"):
    st.warning("Configura la fecha de inicio arriba para continuar.")
    st.stop()

fecha_inicio = date.fromisoformat(proyecto["fecha_inicio"]) if isinstance(proyecto["fecha_inicio"], str) else proyecto["fecha_inicio"]
unidad_periodo = proyecto["unidad_periodo"]
num_periodos = proyecto["num_periodos"]
etiquetas = generar_etiquetas(fecha_inicio, unidad_periodo, num_periodos)

# --- Ítems del presupuesto ---
items_bd = (
    client.table("presupuesto_items")
    .select("*, rubros(codigo, descripcion, unidad, indirectos_utilidad)")
    .eq("proyecto_id", proyecto["id"])
    .execute().data
)
if not items_bd:
    st.warning("Este proyecto todavía no tiene rubros en su presupuesto. Agrégalos primero en 'Presupuesto'.")
    st.stop()

rubros_cache = {}
for it in items_bd:
    if it["rubro_id"] not in rubros_cache:
        rubros_cache[it["rubro_id"]] = client.table("rubros").select("*").eq("id", it["rubro_id"]).single().execute().data

# Asegura que cada ítem del presupuesto tenga su fila de cronograma_items
pi_ids = [it["id"] for it in items_bd]
existentes = client.table("cronograma_items").select("*").in_("presupuesto_item_id", pi_ids).execute().data
ci_por_pi = {e["presupuesto_item_id"]: e for e in existentes}
faltantes = [pid for pid in pi_ids if pid not in ci_por_pi]
if faltantes and puede_editar:
    nuevos = client.table("cronograma_items").insert(
        [{"presupuesto_item_id": pid, "periodo_inicio": 1, "periodo_fin": 1} for pid in faltantes]
    ).execute().data
    for row in nuevos:
        ci_por_pi[row["presupuesto_item_id"]] = row

ci_ids = [c["id"] for c in ci_por_pi.values()]
detalle_bd = client.table("cronograma_detalle").select("*").in_("cronograma_item_id", ci_ids).execute().data if ci_ids else []
distribucion_por_ci = {}
for d in detalle_bd:
    distribucion_por_ci.setdefault(d["cronograma_item_id"], {})[d["periodo"]] = float(d["porcentaje"])

# Calcula subtotal (valor total) de cada ítem a partir de su APU vigente
filas_items = []
for it in items_bd:
    rubro = rubros_cache[it["rubro_id"]]
    precio_unitario = calcular_apu_de_rubro(client, rubro)["precio_unitario"]
    subtotal = float(it["cantidad"]) * precio_unitario
    ci = ci_por_pi.get(it["id"])
    filas_items.append({
        "presupuesto_item_id": it["id"],
        "cronograma_item_id": ci["id"] if ci else None,
        "rubro_descripcion": f"{rubro.get('codigo') or ''} {rubro['descripcion']}".strip(),
        "unidad": rubro["unidad"],
        "subtotal": subtotal,
        "periodo_inicio": ci["periodo_inicio"] if ci else 1,
        "periodo_fin": ci["periodo_fin"] if ci else 1,
        "distribucion": distribucion_por_ci.get(ci["id"], {}) if ci else {},
    })

st.divider()
st.subheader("1. Reparto rápido por rango de periodos")
st.caption("Define en qué periodos se ejecuta cada rubro; el % se reparte en partes iguales entre esos periodos.")

df_rangos = pd.DataFrame([{
    "Rubro": f["rubro_descripcion"],
    "Valor Total": round(f["subtotal"], 2),
    "Periodo Inicio": f["periodo_inicio"],
    "Periodo Fin": f["periodo_fin"],
} for f in filas_items])

if puede_editar:
    edited_rangos = st.data_editor(
        df_rangos, hide_index=True, use_container_width=True, key="editor_rangos",
        disabled=["Rubro", "Valor Total"],
        column_config={
            "Periodo Inicio": st.column_config.NumberColumn(min_value=1, max_value=num_periodos, step=1),
            "Periodo Fin": st.column_config.NumberColumn(min_value=1, max_value=num_periodos, step=1),
        },
    )
    if st.button("🔄 Aplicar reparto automático (sobrescribe los % actuales de cada rubro)"):
        for i, fila in enumerate(filas_items):
            ini = int(edited_rangos.loc[i, "Periodo Inicio"])
            fin = max(ini, int(edited_rangos.loc[i, "Periodo Fin"]))
            ci_id = fila["cronograma_item_id"]
            if not ci_id:
                continue
            client.table("cronograma_items").update({
                "periodo_inicio": ini, "periodo_fin": fin,
            }).eq("id", ci_id).execute()
            client.table("cronograma_detalle").delete().eq("cronograma_item_id", ci_id).execute()
            distribucion = distribuir_automatico(ini, fin)
            client.table("cronograma_detalle").insert([
                {"cronograma_item_id": ci_id, "periodo": p, "porcentaje": pct}
                for p, pct in distribucion.items()
            ]).execute()
        st.success("Reparto aplicado.")
        st.rerun()
else:
    st.dataframe(df_rangos, hide_index=True, use_container_width=True)

st.divider()
st.subheader("2. Ajuste fino por periodo (opcional)")
st.caption("Edita manualmente el % de cada rubro en cada periodo si el reparto automático no refleja bien la realidad.")

df_matriz = pd.DataFrame([
    {"Rubro": f["rubro_descripcion"], **{etiquetas[p - 1]: f["distribucion"].get(p, 0.0) for p in range(1, num_periodos + 1)}}
    for f in filas_items
])

if puede_editar:
    edited_matriz = st.data_editor(
        df_matriz, hide_index=True, use_container_width=True, key="editor_matriz",
        disabled=["Rubro"],
        column_config={et: st.column_config.NumberColumn(format="%.1f%%", min_value=0, max_value=100) for et in etiquetas},
    )
    if st.button("💾 Guardar cambios del cronograma"):
        avisos = []
        for i, fila in enumerate(filas_items):
            ci_id = fila["cronograma_item_id"]
            if not ci_id:
                continue
            suma = sum(float(edited_matriz.loc[i, et] or 0) for et in etiquetas)
            if suma and abs(suma - 100) > 0.5:
                avisos.append(f"{fila['rubro_descripcion']} suma {suma:.1f}% (no 100%)")
            client.table("cronograma_detalle").delete().eq("cronograma_item_id", ci_id).execute()
            nuevas = [
                {"cronograma_item_id": ci_id, "periodo": p, "porcentaje": float(edited_matriz.loc[i, et] or 0)}
                for p, et in enumerate(etiquetas, start=1)
                if float(edited_matriz.loc[i, et] or 0) != 0
            ]
            if nuevas:
                client.table("cronograma_detalle").insert(nuevas).execute()
        st.success("Cronograma guardado.")
        if avisos:
            st.warning("Algunos rubros no suman 100% (puede ser intencional si aún no terminan): " + "; ".join(avisos))
        st.rerun()
else:
    st.dataframe(df_matriz, hide_index=True, use_container_width=True)

# --- Resumen y curva S ---
st.divider()
st.subheader("Resumen — Curva S")

items_calculo = [{
    "rubro_descripcion": f["rubro_descripcion"], "unidad": f["unidad"],
    "subtotal": f["subtotal"], "distribucion": f["distribucion"],
} for f in filas_items]
resultado = calcular_cronograma(items_calculo, num_periodos)

c1, c2 = st.columns(2)
c1.metric("💰 Valor total planificado", f"$ {resultado['total_general']:,.2f}")
c2.metric("Periodos", num_periodos)

resumen_df = pd.DataFrame({
    "Periodo": etiquetas,
    "Valor Periodo": resultado["totales_periodo"],
    "Acumulado": resultado["acumulado"],
    "% Acumulado": resultado["pct_acumulado"],
}).set_index("Periodo")

st.bar_chart(resumen_df["Valor Periodo"])
st.line_chart(resumen_df["Acumulado"])
st.dataframe(resumen_df.style.format({"Valor Periodo": "$ {:.2f}", "Acumulado": "$ {:.2f}", "% Acumulado": "{:.1f}%"}),
             use_container_width=True)

excel_bytes = exportar_cronograma_excel(proyecto, etiquetas, resultado)
st.download_button(
    "⬇️ Descargar cronograma valorado en Excel", data=excel_bytes,
    file_name=f"Cronograma_{proyecto['nombre']}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
