import math

import pytest
from pyproj import Transformer

from geobr_mcp import calculos as c

# poligonal de exemplo (dados fictícios), a mesma da calculadora web
EXEMPLO = [
    {"nome": "P1", "angulo": "117°50'46\"", "distancia": "131.804"},
    {"nome": "P2", "angulo": "119°54'45\"", "distancia": "136.705"},
    {"nome": "P3", "angulo": "114°01'22\"", "distancia": "123.174"},
    {"nome": "P4", "angulo": "120°07'50\"", "distancia": "120.032"},
    {"nome": "P5", "angulo": "121°53'38\"", "distancia": "127.885"},
    {"nome": "P6", "angulo": "126°11'37\"", "distancia": "102.552"},
]


@pytest.mark.parametrize("lat,lon", [(-12.9714, -38.5014), (-23.5505, -46.6333), (-3.119, -60.0217), (-30.0346, -51.2177)])
def test_geo_para_utm_igual_ao_proj(lat, lon):
    r = c.geo_para_utm_pt(lat, lon)
    t = Transformer.from_crs(4674, r["epsg"], always_xy=True)
    e, n = t.transform(lon, lat)
    assert r["e"] == pytest.approx(e, abs=0.002)
    assert r["n"] == pytest.approx(n, abs=0.002)


def test_ida_e_volta_utm_e_gms():
    u = c.geo_para_utm_pt("12°58'17.04\"S", "38°30'05.04\"W")
    g = c.utm_para_geo_pt(u["e"], u["n"], u["fuso"], "S")
    assert g["lat"] == pytest.approx(-12.9714, abs=1e-7)
    assert g["lon"] == pytest.approx(-38.5014, abs=1e-7)
    assert g["lat_dms"].startswith("12°58'")


def test_sad69_para_sirgas_desloca_dezenas_de_metros_e_volta():
    r = c.transformar_datum(-12.97, -38.50, "SAD69", "SIRGAS2000")
    assert 50 < r["deslocamento_m"] < 80
    v = c.transformar_datum(r["lat"], r["lon"], "SIRGAS2000", "SAD69")
    assert v["lat"] == pytest.approx(-12.97, abs=1e-8)
    assert v["lon"] == pytest.approx(-38.50, abs=1e-8)
    with pytest.raises(ValueError, match="datum"):
        c.transformar_datum(0, 0, "CORREGO", "SIRGAS2000")


def test_converter_lote_utm_sad69_para_utm_sirgas_com_erro_isolado():
    pts = [{"nome": "A", "e": 552500, "n": 8565900, "fuso": 24}, {"nome": "B", "e": 553000, "n": 8566000, "fuso": 24},
           {"nome": "ruim", "e": 1}]
    r = c.converter_lote(pts, "UTM:SAD69", "UTM:SIRGAS2000")
    assert r["convertidos"] == 2 and len(r["erros"]) == 1 and r["erros"][0]["ponto"] == "ruim"
    a = r["pontos"][0]
    assert a["fuso"] == 24
    assert 40 < math.hypot(a["e"] - 552500, a["n"] - 8565900) < 80  # SAD69→SIRGAS no Brasil: dezenas de metros
    with pytest.raises(ValueError, match="sistema"):
        c.converter_lote(pts, "XYZ", "UTM:SIRGAS2000")


def test_area_utm_e_geodesica():
    q = [{"e": 0, "n": 0}, {"e": 100, "n": 0}, {"e": 100, "n": 50}, {"e": 0, "n": 50}]
    r = c.area(q)
    assert r["area_m2"] == 5000 and r["area_ha"] == 0.5 and r["perimetro_m"] == 300
    g = c.area([{"lat": -12.0, "lon": -38.0}, {"lat": -12.0, "lon": -37.99}, {"lat": -11.99, "lon": -37.99}, {"lat": -11.99, "lon": -38.0}], "geo")
    assert 1_190_000 < g["area_m2"] < 1_215_000
    with pytest.raises(ValueError):
        c.area(q[:2])


def test_rbmc_salvador():
    r = c.rbmc_mais_proximas(-12.9714, -38.5014, 3)
    assert r["estacoes"][0]["id"] == "SSA1"
    assert r["estacoes"][0]["distancia_km"] < 5
    assert len(r["estacoes"]) == 3
    assert r["estacoes"][0]["distancia_km"] <= r["estacoes"][1]["distancia_km"]
    assert "20 km" in r["orientacao"]


def test_vincenty_contra_proj():
    from pyproj import Geod
    g = Geod(ellps="GRS80")
    az, _, d = g.inv(-38.5, -12.9, -46.6, -23.5)
    dist, azv = c._vincenty(-12.9, -38.5, -23.5, -46.6)
    assert dist == pytest.approx(d, abs=0.001)
    assert azv == pytest.approx(az % 360, abs=1e-6)


def test_poligonal_fechada_igual_a_calculadora_web():
    r = c.poligonal(EXEMPLO, azimute_inicial="116°03'34\"", inicio={"e": 500000, "n": 8600000})
    assert r["fechamento_angular"]["erro_seg"] == pytest.approx(-2.0, abs=0.05)
    assert r["fechamento_angular"]["atende"]
    assert r["fechamento_linear"]["precisao"] == "1:116.595"
    assert r["area_m2"] == pytest.approx(39579.35, abs=0.05)
    assert r["coordenadas"][0] == {"nome": "P1", "e": 500000.0, "n": 8600000.0}
    assert r["coordenadas"][1]["e"] == pytest.approx(500118.406, abs=0.002)


def test_poligonal_enquadrada_e_validacoes():
    A, B, C, D = {"e": 1000, "n": 900}, {"e": 1000, "n": 1000}, {"e": 1250, "n": 1100}, {"e": 1350, "n": 1100}
    est = [{"nome": "B", "angulo": "233 07 52", "distancia": 100.004}, {"nome": "X1", "angulo": "229 23 55", "distancia": 92.195},
           {"nome": "X2", "angulo": "130 36 05", "distancia": 99.998}, {"nome": "C", "angulo": "216 52 12"}]
    r = c.poligonal(est, tipo="enquadrada", apoio={"re": A, "partida": B, "chegada": C, "vante": D})
    assert r["fechamento_angular"]["erro_seg"] == pytest.approx(4.0, abs=0.5)
    assert r["coordenadas"][-1]["e"] == pytest.approx(1250, abs=1e-6)
    with pytest.raises(ValueError, match="azimute_inicial"):
        c.poligonal(EXEMPLO)
    with pytest.raises(ValueError, match="3 estações"):
        c.poligonal(EXEMPLO[:2], azimute_inicial=0, inicio={"e": 0, "n": 0})


def test_gsd_drone():
    r = c.gsd_drone(altura_m=100, camera="Phantom 4 RTK")
    assert r["gsd_cm"] == pytest.approx(2.74, abs=0.01)
    h = c.gsd_drone(gsd_cm=2.0, camera="mavic 3 enterprise")
    assert c.gsd_drone(altura_m=h["altura_m"])["gsd_cm"] == pytest.approx(2.0, abs=0.01)
    assert c.gsd_drone(altura_m=150)["alerta"].startswith("Acima de 120 m")
    assert c.gsd_drone(altura_m=100, area_ha=50)["fotos_estimadas"] > 100
    with pytest.raises(ValueError, match="câmera"):
        c.gsd_drone(altura_m=100, camera="tijolo")


def test_fuso():
    assert c.fuso_utm(-38.5) == {"fuso": 24, "meridiano_central": -39}
