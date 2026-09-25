"""Catálogo del avatar personalizable del niño.

Cada ítem se desbloquea según los puntos totales acumulados jugando
(suma de puntaje_total de todos sus ProgresoX). No depende de una tabla en
la base de datos a propósito: es un catálogo fijo, fácil de ajustar acá.
"""

CATEGORIAS = ['camisa', 'pantalon', 'zapatos', 'accesorio']

CATALOGO = {
    'camisa': [
        {'id': 'camisa_roja', 'nombre': 'Camisa roja', 'color': '#e85d4b', 'puntos': 0},
        {'id': 'camisa_amarilla', 'nombre': 'Camisa amarilla', 'color': '#f4b942', 'puntos': 50},
        {'id': 'camisa_verde', 'nombre': 'Camisa verde', 'color': '#4caf7d', 'puntos': 150},
        {'id': 'camisa_morada', 'nombre': 'Camisa morada', 'color': '#8e6fc4', 'puntos': 300},
        {'id': 'camisa_naranja', 'nombre': 'Camisa naranja', 'color': '#f2884b', 'puntos': 500},
    ],
    'pantalon': [
        {'id': 'pantalon_azul', 'nombre': 'Pantalón azul', 'color': '#4a90d3', 'puntos': 0},
        {'id': 'pantalon_gris', 'nombre': 'Pantalón gris', 'color': '#8a97a6', 'puntos': 80},
        {'id': 'pantalon_verde', 'nombre': 'Pantalón verde', 'color': '#2e8b57', 'puntos': 200},
        {'id': 'pantalon_negro', 'nombre': 'Pantalón negro', 'color': '#3a3a3a', 'puntos': 400},
    ],
    'zapatos': [
        {'id': 'zapatos_blancos', 'nombre': 'Zapatos blancos', 'color': '#f5f5f5', 'puntos': 0},
        {'id': 'zapatos_rojos', 'nombre': 'Zapatos rojos', 'color': '#c9463c', 'puntos': 100},
        {'id': 'zapatos_negros', 'nombre': 'Zapatos negros', 'color': '#2b2b2b', 'puntos': 250},
        {'id': 'zapatos_dorados', 'nombre': 'Zapatos dorados', 'color': '#d4af37', 'puntos': 450},
    ],
    'accesorio': [
        {'id': '', 'nombre': 'Sin accesorio', 'color': '', 'puntos': 0},
        {'id': 'gorra', 'nombre': 'Gorra', 'color': '#4a90d3', 'puntos': 120},
        {'id': 'lentes', 'nombre': 'Lentes', 'color': '#3a3a3a', 'puntos': 220},
        {'id': 'moño', 'nombre': 'Moño', 'color': '#e85d8f', 'puntos': 220},
        {'id': 'corona', 'nombre': 'Corona', 'color': '#d4af37', 'puntos': 600},
    ],
}

CAMPO_POR_CATEGORIA = {
    'camisa': 'avatar_camisa',
    'pantalon': 'avatar_pantalon',
    'zapatos': 'avatar_zapatos',
    'accesorio': 'avatar_accesorio',
}


def calcular_puntos_totales(niño):
    """Suma el puntaje_total acumulado en todos los trackers de progreso
    que tenga el niño (puede tener más de uno si jugó varios tipos de juego)."""
    from django.core.exceptions import ObjectDoesNotExist

    total = 0
    for atributo in ('progreso', 'progresocartas', 'progresodiscalculia'):
        try:
            tracker = getattr(niño, atributo)
        except ObjectDoesNotExist:
            continue
        total += float(tracker.puntaje_total or 0)
    return total


def item_por_id(categoria, item_id):
    for item in CATALOGO.get(categoria, []):
        if item['id'] == item_id:
            return item
    return None


def catalogo_con_estado(niño, puntos_totales):
    """Devuelve el catálogo anotado con si cada ítem está desbloqueado y
    si es el que el niño tiene equipado ahora mismo."""
    resultado = {}
    for categoria in CATEGORIAS:
        campo = CAMPO_POR_CATEGORIA[categoria]
        equipado_id = getattr(niño, campo)
        items = []
        for item in CATALOGO[categoria]:
            items.append({
                **item,
                'desbloqueado': puntos_totales >= item['puntos'],
                'equipado': item['id'] == equipado_id,
            })
        resultado[categoria] = items
    return resultado


def colores_equipados(niño):
    colores = {}
    for categoria, campo in CAMPO_POR_CATEGORIA.items():
        item = item_por_id(categoria, getattr(niño, campo))
        colores[categoria] = item['color'] if item else ''
    return colores
