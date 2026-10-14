"""
Lógica de cálculo de Análisis de Precios Unitarios (APU).

Reglas:
- material:    costo = cantidad x precio
- mano_obra:   costo = cantidad x precio_hora x rendimiento (horas/unidad)
- equipo:      costo = cantidad x precio_hora x rendimiento (horas/unidad)

precio_unitario_rubro = costo_directo x (1 + indirectos_utilidad / 100)
"""


def costo_item(tipo: str, cantidad: float, precio: float, rendimiento: float | None) -> float:
    cantidad = cantidad or 0
    precio = precio or 0
    if tipo == "material":
        return cantidad * precio
    # mano_obra y equipo dependen del rendimiento (horas por unidad)
    rendimiento = rendimiento or 0
    return cantidad * precio * rendimiento


def calcular_apu(items: list[dict], indirectos_utilidad_pct: float) -> dict:
    """
    items: lista de dicts con llaves:
        tipo, cantidad, precio, rendimiento, descripcion, unidad
    Devuelve un resumen con subtotales por grupo y el precio unitario final.
    """
    grupos = {"material": 0.0, "mano_obra": 0.0, "equipo": 0.0}
    detalle = []

    for it in items:
        c = costo_item(it["tipo"], it["cantidad"], it["precio"], it.get("rendimiento"))
        grupos[it["tipo"]] += c
        detalle.append({**it, "costo": c})

    costo_directo = sum(grupos.values())
    monto_indirectos = costo_directo * (indirectos_utilidad_pct / 100)
    precio_unitario = costo_directo + monto_indirectos

    return {
        "detalle": detalle,
        "subtotal_materiales": grupos["material"],
        "subtotal_mano_obra": grupos["mano_obra"],
        "subtotal_equipo": grupos["equipo"],
        "costo_directo": costo_directo,
        "indirectos_utilidad_pct": indirectos_utilidad_pct,
        "monto_indirectos_utilidad": monto_indirectos,
        "precio_unitario": precio_unitario,
    }


def calcular_presupuesto(items_presupuesto: list[dict]) -> dict:
    """
    items_presupuesto: lista de dicts con llaves:
        rubro_descripcion, unidad, cantidad_obra, precio_unitario
    """
    filas = []
    total = 0.0
    for it in items_presupuesto:
        subtotal = (it["cantidad_obra"] or 0) * (it["precio_unitario"] or 0)
        total += subtotal
        filas.append({**it, "subtotal": subtotal})

    return {"filas": filas, "total": total}


def distribuir_automatico(periodo_inicio: int, periodo_fin: int) -> dict[int, float]:
    """Reparte 100% en partes iguales entre periodo_inicio y periodo_fin (inclusive)."""
    periodo_inicio = max(1, int(periodo_inicio))
    periodo_fin = max(periodo_inicio, int(periodo_fin))
    n = periodo_fin - periodo_inicio + 1
    pct = round(100 / n, 3)
    distribucion = {p: pct for p in range(periodo_inicio, periodo_fin + 1)}
    # Ajusta el último periodo para que la suma cierre exactamente en 100%
    suma = pct * n
    distribucion[periodo_fin] = round(distribucion[periodo_fin] + (100 - suma), 3)
    return distribucion


def calcular_cronograma(items: list[dict], num_periodos: int) -> dict:
    """
    items: lista de dicts con llaves:
        rubro_descripcion, unidad, subtotal (valor total del rubro en el presupuesto),
        distribucion: dict {periodo (int) -> porcentaje}
    Devuelve la matriz valorizada, los totales por periodo y el acumulado (curva S).
    """
    filas = []
    totales_periodo = [0.0] * num_periodos

    for it in items:
        valores = []
        for p in range(1, num_periodos + 1):
            pct = it["distribucion"].get(p, 0.0)
            valor = (it["subtotal"] or 0) * (pct / 100)
            valores.append(valor)
            totales_periodo[p - 1] += valor
        filas.append({
            "rubro_descripcion": it["rubro_descripcion"],
            "unidad": it.get("unidad", ""),
            "subtotal": it["subtotal"],
            "valores": valores,
        })

    acumulado = []
    corrido = 0.0
    for v in totales_periodo:
        corrido += v
        acumulado.append(corrido)

    total_general = acumulado[-1] if acumulado else 0.0
    pct_acumulado = [
        (a / total_general * 100) if total_general else 0.0 for a in acumulado
    ]

    return {
        "filas": filas,
        "totales_periodo": totales_periodo,
        "acumulado": acumulado,
        "pct_acumulado": pct_acumulado,
        "total_general": total_general,
    }
