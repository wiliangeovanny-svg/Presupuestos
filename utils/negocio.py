from datetime import date
from utils.calculos import calcular_apu, calcular_cronograma
from utils.fechas import generar_etiquetas


def calcular_apu_de_rubro(client, rubro: dict) -> dict:
    """Calcula el APU completo vigente de un rubro, consultando sus insumos
    actuales (precios de hoy). Se usa desde Rubros/APU, Presupuesto y Cronograma
    para que el cálculo sea siempre el mismo en toda la app."""
    detalle = (
        client.table("rubro_insumos")
        .select("*, insumos(tipo, descripcion, unidad, precio)")
        .eq("rubro_id", rubro["id"])
        .execute().data
    )
    items = [{
        "tipo": d["insumos"]["tipo"],
        "descripcion": d["insumos"]["descripcion"],
        "unidad": d["insumos"]["unidad"],
        "precio": d["insumos"]["precio"],
        "cantidad": d["cantidad"],
        "rendimiento": d.get("rendimiento"),
    } for d in detalle]
    return calcular_apu(items, rubro["indirectos_utilidad"])


def calcular_cronograma_proyecto(client, proyecto: dict) -> tuple[list[str], dict] | None:
    """
    Calcula el cronograma valorado completo de un proyecto a partir de los datos
    ya guardados (cronograma_items / cronograma_detalle). Se usa para exportarlo
    junto al presupuesto sin repetir la lógica de captura de la página Cronograma.

    Devuelve (etiquetas, resultado) o None si el proyecto no tiene el cronograma
    activado, no tiene fecha de inicio configurada, o no tiene rubros en su
    presupuesto todavía.
    """
    if not proyecto.get("requiere_cronograma") or not proyecto.get("fecha_inicio"):
        return None

    items_bd = (
        client.table("presupuesto_items")
        .select("*, rubros(codigo, descripcion, unidad, indirectos_utilidad)")
        .eq("proyecto_id", proyecto["id"])
        .execute().data
    )
    if not items_bd:
        return None

    pi_ids = [it["id"] for it in items_bd]
    ci_rows = client.table("cronograma_items").select("*").in_("presupuesto_item_id", pi_ids).execute().data
    ci_por_pi = {c["presupuesto_item_id"]: c for c in ci_rows}
    ci_ids = [c["id"] for c in ci_por_pi.values()]
    detalle_bd = (
        client.table("cronograma_detalle").select("*").in_("cronograma_item_id", ci_ids).execute().data
        if ci_ids else []
    )
    distribucion_por_ci = {}
    for d in detalle_bd:
        distribucion_por_ci.setdefault(d["cronograma_item_id"], {})[d["periodo"]] = float(d["porcentaje"])

    items_calculo = []
    for it in items_bd:
        rubro_full = {"id": it["rubro_id"], **it["rubros"]}
        precio_unitario = calcular_apu_de_rubro(client, rubro_full)["precio_unitario"]
        subtotal = float(it["cantidad"]) * precio_unitario
        ci = ci_por_pi.get(it["id"])
        distribucion = distribucion_por_ci.get(ci["id"], {}) if ci else {}
        items_calculo.append({
            "rubro_descripcion": f"{rubro_full.get('codigo') or ''} {rubro_full['descripcion']}".strip(),
            "unidad": rubro_full["unidad"],
            "subtotal": subtotal,
            "distribucion": distribucion,
        })

    resultado = calcular_cronograma(items_calculo, proyecto["num_periodos"])
    fecha_inicio = proyecto["fecha_inicio"]
    if isinstance(fecha_inicio, str):
        fecha_inicio = date.fromisoformat(fecha_inicio)
    etiquetas = generar_etiquetas(fecha_inicio, proyecto["unidad_periodo"], proyecto["num_periodos"])
    return etiquetas, resultado
