from datetime import date
from app import contar_dias_laborables


def test_viernes_a_lunes_son_2_dias():
    # Viernes 11 y lunes 14 de diciembre: el fin de semana no cuenta
    assert contar_dias_laborables(date(2026, 12, 11), date(2026, 12, 14)) == 2


def test_semana_completa_son_5_dias():
    # Del lunes 14 al domingo 20 de diciembre
    assert contar_dias_laborables(date(2026, 12, 14), date(2026, 12, 20)) == 5


def test_solo_fin_de_semana_son_0_dias():
    # Sábado 12 y domingo 13 de diciembre
    assert contar_dias_laborables(date(2026, 12, 12), date(2026, 12, 13)) == 0


def test_un_solo_dia():
    # Solo el lunes 14 de diciembre
    assert contar_dias_laborables(date(2026, 12, 14), date(2026, 12, 14)) == 1