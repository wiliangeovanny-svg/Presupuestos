import calendar
from datetime import date, timedelta

MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _sumar_meses(f: date, n: int) -> date:
    total_meses = f.month - 1 + n
    anio = f.year + total_meses // 12
    mes = total_meses % 12 + 1
    dia = min(f.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def inicio_periodo(fecha_inicio: date, unidad: str, indice: int) -> date:
    """Fecha de inicio del periodo `indice` (1-based)."""
    n = indice - 1
    if unidad == "semana":
        return fecha_inicio + timedelta(weeks=n)
    if unidad == "quincena":
        return fecha_inicio + timedelta(days=15 * n)
    return _sumar_meses(fecha_inicio, n)  # mes


def fin_periodo(fecha_inicio: date, unidad: str, indice: int) -> date:
    """Último día del periodo `indice` (un día antes de que empiece el siguiente)."""
    return inicio_periodo(fecha_inicio, unidad, indice + 1) - timedelta(days=1)


def etiqueta_periodo(fecha_inicio: date, unidad: str, indice: int) -> str:
    ini = inicio_periodo(fecha_inicio, unidad, indice)
    fin = fin_periodo(fecha_inicio, unidad, indice)
    if unidad == "mes":
        return f"P{indice} · {MESES_ES[ini.month - 1]} {ini.year}"
    return f"P{indice} · {ini.day:02d}{MESES_ES[ini.month-1]}-{fin.day:02d}{MESES_ES[fin.month-1]}"


def generar_etiquetas(fecha_inicio: date | None, unidad: str, num_periodos: int) -> list[str]:
    if not fecha_inicio:
        return [f"Periodo {i}" for i in range(1, num_periodos + 1)]
    return [etiqueta_periodo(fecha_inicio, unidad, i) for i in range(1, num_periodos + 1)]
