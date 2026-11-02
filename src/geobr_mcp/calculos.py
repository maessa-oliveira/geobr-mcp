"""Cálculos expostos pelo servidor MCP. Funções puras, sem dependência do protocolo.

Conversões e transformações usam a biblioteca geobr-tools (validada contra o PROJ).
Os resultados são dicionários simples, prontos para virar JSON.
"""

from __future__ import annotations

import json
import math
import os
import urllib.request
from collections.abc import Iterable, Sequence
from importlib import resources

from geobr_tools import (
    area_geodesica,
    area_plana,
    fuso_de,
    geo_para_utm,
    sad69_para_sirgas2000,
    sirgas2000_para_sad69,
    utm_para_geo,
)
from geobr_tools.formatos import dms_para_graus, graus_para_dms

DATUNS = {"SIRGAS2000", "SAD69"}
RAD = math.pi / 180


def _datum(d: str) -> str:
    d = d.upper().replace(" ", "").replace("_", "")
    if d in {"SIRGAS", "SIRGAS2000", "WGS84"}:
        return "SIRGAS2000"
    if d in {"SAD69", "SAD69/96", "SAD6996"}:
        return "SAD69"
    raise ValueError(f"datum desconhecido: {d!r} (use SIRGAS2000 ou SAD69)")


def angulo(valor: float | str) -> float:
    """Aceita graus decimais ou texto em graus, minutos e segundos (ex.: 12°58'30\"S)."""
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip()
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return dms_para_graus(texto)


# ---------------------------------------------------------------- coordenadas

def geo_para_utm_pt(lat: float | str, lon: float | str, datum: str = "SIRGAS2000", fuso: int | None = None) -> dict:
    d = _datum(datum)
    la, lo = angulo(lat), angulo(lon)
    p = geo_para_utm(la, lo, elipsoide=d, fuso=fuso)
    return {
        "datum": d, "e": round(p.e, 3), "n": round(p.n, 3), "fuso": p.fuso, "hemisferio": p.hemisferio,
        "fator_escala": round(p.fator_escala, 8), "convergencia_meridiana": graus_para_dms(p.convergencia, "lon", 2).rstrip("WE ").strip(),
        "convergencia_graus": round(p.convergencia, 8), "epsg": p.epsg_sirgas if d == "SIRGAS2000" else None,
    }


def utm_para_geo_pt(e: float, n: float, fuso: int, hemisferio: str = "S", datum: str = "SIRGAS2000") -> dict:
    d = _datum(datum)
    la, lo = utm_para_geo(float(e), float(n), int(fuso), hemisferio, elipsoide=d)
    return {
        "datum": d, "lat": round(la, 9), "lon": round(lo, 9),
        "lat_dms": graus_para_dms(la, "lat", 4), "lon_dms": graus_para_dms(lo, "lon", 4),
    }


def transformar_datum(lat: float | str, lon: float | str, de: str, para: str, h: float = 0.0) -> dict:
    """SAD 69 ↔ SIRGAS 2000 com os parâmetros oficiais do IBGE (R.PR 1/2005)."""
    a, b = _datum(de), _datum(para)
    la, lo = angulo(lat), angulo(lon)
    if a == b:
        r = (la, lo, h)
    elif a == "SAD69":
        r = sad69_para_sirgas2000(la, lo, h)
    else:
        r = sirgas2000_para_sad69(la, lo, h)
    dlat_m = (r[0] - la) * RAD * 6_371_000
    dlon_m = (r[1] - lo) * RAD * 6_371_000 * math.cos(la * RAD)
    return {
        "de": a, "para": b, "lat": round(r[0], 9), "lon": round(r[1], 9), "h": round(r[2], 3),
        "lat_dms": graus_para_dms(r[0], "lat", 4), "lon_dms": graus_para_dms(r[1], "lon", 4),
        "deslocamento_m": round(math.hypot(dlat_m, dlon_m), 2),
    }


def converter_lote(pontos: Sequence[dict], de: str, para: str) -> dict:
    """Converte uma lista de pontos entre sistemas.

    Sistemas: 'GEO:SIRGAS2000', 'GEO:SAD69', 'UTM:SIRGAS2000', 'UTM:SAD69'.
    Pontos GEO têm lat/lon; pontos UTM têm e/n/fuso (hemisfério 'S' por padrão).
    Cada ponto pode ter 'nome'. Na saída UTM, o fuso é o do ponto de entrada (se UTM)
    ou calculado (se GEO), a não ser que 'fuso' seja informado no ponto.
    """
    def sistema(s: str) -> tuple[str, str]:
        tipo, _, dat = s.upper().partition(":")
        if tipo not in {"GEO", "UTM"}:
            raise ValueError(f"sistema inválido: {s!r} (ex.: 'UTM:SAD69', 'GEO:SIRGAS2000')")
        return tipo, _datum(dat or "SIRGAS2000")

    t1, d1 = sistema(de)
    t2, d2 = sistema(para)
    saida, erros = [], []
    for i, p in enumerate(pontos):
        nome = str(p.get("nome", i + 1))
        try:
            fuso_in = int(p["fuso"]) if "fuso" in p else None
            if t1 == "UTM":
                la, lo = utm_para_geo(float(p["e"]), float(p["n"]), int(p["fuso"]), p.get("hemisferio", "S"), elipsoide=d1)
            else:
                la, lo = angulo(p["lat"]), angulo(p["lon"])
            if d1 != d2:
                r = transformar_datum(la, lo, d1, d2)
                la, lo = r["lat"], r["lon"]
            if t2 == "UTM":
                u = geo_para_utm(la, lo, elipsoide=d2, fuso=fuso_in)
                saida.append({"nome": nome, "e": round(u.e, 3), "n": round(u.n, 3), "fuso": u.fuso, "hemisferio": u.hemisferio})
            else:
                saida.append({"nome": nome, "lat": round(la, 9), "lon": round(lo, 9)})
        except (KeyError, ValueError, TypeError) as exc:
            erros.append({"ponto": nome, "erro": str(exc)})
    return {"de": f"{t1}:{d1}", "para": f"{t2}:{d2}", "convertidos": len(saida), "pontos": saida, "erros": erros}


# ---------------------------------------------------------------- áreas

def area(pontos: Sequence[dict], tipo: str = "utm") -> dict:
    """Área e perímetro. tipo='utm' (pontos e/n, área no plano UTM) ou 'geo' (lat/lon, área geodésica)."""
    if len(pontos) < 3:
        raise ValueError("informe pelo menos 3 vértices")
    if tipo.lower() == "utm":
        a = area_plana([(float(p["e"]), float(p["n"])) for p in pontos])
        tipo_txt = "plana (no plano UTM)"
    else:
        a = area_geodesica([(angulo(p["lat"]), angulo(p["lon"])) for p in pontos])
        tipo_txt = "geodésica (sobre o elipsoide GRS80)"
    return {"tipo": tipo_txt, "area_m2": round(a.area_m2, 3), "area_ha": round(a.hectares, 6), "perimetro_m": round(a.perimetro_m, 3)}


# ---------------------------------------------------------------- RBMC

URL_RBMC = "https://maessa-oliveira.github.io/rbmc-mapa/data/rbmc.json"
_cache_rbmc: dict = {}


def _carregar_rbmc() -> dict:
    """Dados do dia (atualizados pelo mapa da RBMC); sem internet, usa a cópia embutida no pacote."""
    if "d" in _cache_rbmc:
        return _cache_rbmc["d"]
    d = None
    if os.environ.get("GEOBR_MCP_OFFLINE") != "1":
        try:
            with urllib.request.urlopen(URL_RBMC, timeout=4) as r:
                d = json.loads(r.read().decode("utf-8"))
            if len(d.get("estacoes", [])) < 50:
                d = None
        except Exception:  # noqa: BLE001 - qualquer falha de rede cai na cópia local
            d = None
    if d is None:
        with resources.files("geobr_mcp").joinpath("rbmc.json").open(encoding="utf-8") as f:
            d = json.load(f)
    _cache_rbmc["d"] = d
    return d


def _vincenty(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """Distância (m) e azimute (graus) no GRS80, fórmula inversa de Vincenty."""
    a, f = 6_378_137.0, 1 / 298.257222101
    b = a * (1 - f)
    L = (lon2 - lon1) * RAD
    U1 = math.atan((1 - f) * math.tan(lat1 * RAD))
    U2 = math.atan((1 - f) * math.tan(lat2 * RAD))
    sU1, cU1, sU2, cU2 = math.sin(U1), math.cos(U1), math.sin(U2), math.cos(U2)
    lam = L
    for _ in range(200):
        sl, cl = math.sin(lam), math.cos(lam)
        ss = math.hypot(cU2 * sl, cU1 * sU2 - sU1 * cU2 * cl)
        if ss == 0:
            return 0.0, 0.0
        cs = sU1 * sU2 + cU1 * cU2 * cl
        sig = math.atan2(ss, cs)
        sa = cU1 * cU2 * sl / ss
        c2a = 1 - sa * sa
        c2sm = cs - 2 * sU1 * sU2 / c2a if c2a else 0.0
        C = f / 16 * c2a * (4 + f * (4 - 3 * c2a))
        ant = lam
        lam = L + (1 - C) * f * sa * (sig + C * ss * (c2sm + C * cs * (-1 + 2 * c2sm * c2sm)))
        if abs(lam - ant) < 1e-12:
            break
    u2 = c2a * (a * a - b * b) / (b * b)
    A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    ds = B * ss * (c2sm + B / 4 * (cs * (-1 + 2 * c2sm * c2sm) - B / 6 * c2sm * (-3 + 4 * ss * ss) * (-3 + 4 * c2sm * c2sm)))
    dist = b * A * (sig - ds)
    az = math.atan2(cU2 * math.sin(lam), cU1 * sU2 - sU1 * cU2 * math.cos(lam)) / RAD
    return dist, (az + 360) % 360


def _situacao(dias: int, consultados: int) -> str:
    if dias == 0:
        return "sem dados recentes"
    if dias >= max(1, consultados - 1):
        return "ativa"
    return f"instável ({dias} de {consultados} dias)"


def _orientacao(km: float) -> str:
    if km <= 20:
        return "Até 20 km: RTK/NTRIP de rede e pós-processamento rápido funcionam bem."
    if km <= 50:
        return "De 20 a 50 km: prefira receptor multifrequência e rastreios mais longos no estático."
    if km <= 100:
        return "De 50 a 100 km: use estático longo (2 h ou mais) e confira com o IBGE-PPP."
    return "Acima de 100 km: estático longo com IBGE-PPP ou uma base própria mais próxima."


def rbmc_mais_proximas(lat: float | str, lon: float | str, quantidade: int = 3, so_ativas: bool = True) -> dict:
    """Estações RBMC/IBGE mais próximas, com distância, azimute e situação na última semana."""
    d = _carregar_rbmc()
    la, lo = angulo(lat), angulo(lon)
    consultados = len(d.get("dias_consultados", [])) or 7
    lista = []
    for e in d["estacoes"]:
        sit = _situacao(int(e.get("dias_com_dados", 0)), consultados)
        if so_ativas and sit == "sem dados recentes":
            continue
        dist, az = _vincenty(la, lo, e["lat"], e["lon"])
        lista.append({
            "id": e["id"], "cidade": e.get("cidade", ""), "uf": e.get("uf", ""), "lat": e["lat"], "lon": e["lon"],
            "altitude_elipsoidal": e.get("h"), "situacao": sit, "receptor": e.get("receptor", ""),
            "constelacoes": e.get("sistemas", ""), "distancia_km": round(dist / 1000, 2), "azimute_graus": round(az, 1),
            "descritivo": f"https://geoftp.ibge.gov.br/informacoes_sobre_posicionamento_geodesico/rbmc/relatorio/Descritivo_{e['id']}.pdf",
        })
    lista.sort(key=lambda x: x["distancia_km"])
    prox = lista[: max(1, int(quantidade))]
    return {
        "dados_de": d.get("atualizado_em"), "fonte": d.get("fonte"),
        "orientacao": _orientacao(prox[0]["distancia_km"]) if prox else "",
        "estacoes": prox,
    }


# ---------------------------------------------------------------- poligonal

def _norm360(g: float) -> float:
    return g % 360.0


def _norm180(g: float) -> float:
    r = _norm360(g)
    return r - 360 if r > 180 else r


def poligonal(
    estacoes: Sequence[dict],
    tipo: str = "fechada",
    azimute_inicial: float | str | None = None,
    inicio: dict | None = None,
    apoio: dict | None = None,
    tolerancia_angular_seg: float = 20.0,
    precisao_minima: float = 5000.0,
    compensacao: str = "bowditch",
    fator_escala: float = 1.0,
) -> dict:
    """Calcula uma poligonal fechada ou enquadrada.

    estacoes: [{'nome', 'angulo' (horário, ré→vante; graus ou GMS), 'distancia' (m, até a próxima)}].
    Fechada: azimute_inicial (lado da 1ª para a 2ª estação) e inicio {'e','n'} da 1ª estação.
    Enquadrada: apoio {'re','partida','chegada','vante'} com {'e','n'}; 1ª estação = partida, última = chegada.
    """
    est = [{"nome": str(s.get("nome", f"P{i + 1}")), "angulo": angulo(s["angulo"]),
            "dist": float(str(s.get("distancia", 0) or 0).replace(",", ".")) * fator_escala} for i, s in enumerate(estacoes)]
    n = len(est)
    if n < 3:
        raise ValueError("informe pelo menos 3 estações")
    soma = sum(e["angulo"] for e in est)
    def inv(p, q):
        de, dn = q["e"] - p["e"], q["n"] - p["n"]
        return _norm360(math.degrees(math.atan2(de, dn))), math.hypot(de, dn)

    if tipo == "fechada":
        if azimute_inicial is None or inicio is None:
            raise ValueError("poligonal fechada precisa de azimute_inicial e inicio")
        erro = _norm180(soma - n * 180)
        az0 = angulo(azimute_inicial)
        p0 = {"e": float(inicio["e"]), "n": float(inicio["n"])}
        nlados = n
    elif tipo == "enquadrada":
        if not apoio or not all(k in apoio for k in ("re", "partida", "chegada", "vante")):
            raise ValueError("poligonal enquadrada precisa de apoio com re, partida, chegada e vante")
        az_re = inv(apoio["re"], apoio["partida"])[0]
        az_ch = inv(apoio["chegada"], apoio["vante"])[0]
        erro = _norm180(_norm360(az_re + soma - n * 180) - az_ch)
        az0, p0, nlados = az_re, {"e": float(apoio["partida"]["e"]), "n": float(apoio["partida"]["n"])}, n - 1
    else:
        raise ValueError("tipo deve ser 'fechada' ou 'enquadrada'")
    for e in est[:nlados]:
        if e["dist"] <= 0:
            raise ValueError(f"distância inválida em {e['nome']}")

    corr = -erro / n
    for e in est:
        e["corrigido"] = e["angulo"] + corr
    lados = []
    az = _norm360(az0)
    for i in range(nlados):
        if tipo == "fechada":
            if i > 0:
                az = _norm360(az + est[i]["corrigido"] - 180)
        else:
            az = _norm360(az + est[i]["corrigido"] - 180)
        d = est[i]["dist"]
        lados.append({"de": est[i]["nome"], "para": est[(i + 1) % n]["nome"], "az": az, "dist": d,
                      "dE": d * math.sin(az * RAD), "dN": d * math.cos(az * RAD)})
    perim = sum(l["dist"] for l in lados)
    eE = sum(l["dE"] for l in lados)
    eN = sum(l["dN"] for l in lados)
    if tipo == "enquadrada":
        eE -= apoio["chegada"]["e"] - apoio["partida"]["e"]
        eN -= apoio["chegada"]["n"] - apoio["partida"]["n"]
    erro_lin = math.hypot(eE, eN)
    prec = perim / erro_lin if erro_lin > 0 else float("inf")
    sE = sum(abs(l["dE"]) for l in lados) or 1
    sN = sum(abs(l["dN"]) for l in lados) or 1
    coords = [dict(p0)]
    for l in lados[: n - 1]:
        if compensacao == "transito":
            cE, cN = -eE * abs(l["dE"]) / sE, -eN * abs(l["dN"]) / sN
        else:
            cE, cN = -eE * l["dist"] / perim, -eN * l["dist"] / perim
        coords.append({"e": coords[-1]["e"] + l["dE"] + cE, "n": coords[-1]["n"] + l["dN"] + cN})
    tol = tolerancia_angular_seg * math.sqrt(n) / 3600
    res = {
        "tipo": tipo, "estacoes": n, "perimetro_m": round(perim, 3),
        "fechamento_angular": {
            "erro_seg": round(erro * 3600, 1), "tolerancia_seg": round(tol * 3600, 1),
            "correcao_por_estacao_seg": round(corr * 3600, 2), "atende": abs(erro) <= tol + 1e-12,
        },
        "fechamento_linear": {
            "erro_e_m": round(eE, 4), "erro_n_m": round(eN, 4), "erro_m": round(erro_lin, 4),
            "precisao": f"1:{round(prec):,}".replace(",", ".") if math.isfinite(prec) else "exata",
            "precisao_minima": f"1:{round(precisao_minima):,}".replace(",", "."), "atende": prec >= precisao_minima,
        },
        "compensacao": "trânsito" if compensacao == "transito" else "Bowditch",
        "coordenadas": [{"nome": est[i]["nome"], "e": round(c["e"], 3), "n": round(c["n"], 3)} for i, c in enumerate(coords)],
    }
    if tipo == "fechada":
        res["area_m2"] = round(area_plana([(c["e"], c["n"]) for c in coords]).area_m2, 2)
    return res


# ---------------------------------------------------------------- drone

CAMERAS = {
    "mavic 3 enterprise": (17.3, 13.0, 12.29, 5280, 3956),
    "matrice 4e": (17.3, 13.0, 12.29, 5280, 3956),
    "phantom 4 rtk": (13.2, 8.8, 8.8, 5472, 3648),
    "zenmuse p1 35mm": (35.9, 24.0, 35.0, 8192, 5460),
    "mini 4 pro": (9.6, 7.2, 6.72, 4032, 3024),
}


def gsd_drone(
    altura_m: float | None = None,
    gsd_cm: float | None = None,
    camera: str = "mavic 3 enterprise",
    sobreposicao_frontal: float = 0.8,
    sobreposicao_lateral: float = 0.7,
    area_ha: float | None = None,
) -> dict:
    """GSD e geometria do voo. Informe altura_m (calcula o GSD) ou gsd_cm (calcula a altura)."""
    chave = camera.lower().strip()
    if chave not in CAMERAS:
        raise ValueError(f"câmera desconhecida: {camera!r}. Opções: {', '.join(CAMERAS)}")
    sl, _sa, f, pl, pa = CAMERAS[chave]
    if altura_m is None and gsd_cm is None:
        raise ValueError("informe altura_m ou gsd_cm")
    if altura_m is None:
        altura_m = gsd_cm / 100 * f * pl / sl
    g = sl * altura_m / (f * pl)  # m/px
    larg, alt = g * pl, g * pa
    linhas = larg * (1 - sobreposicao_lateral)
    base = alt * (1 - sobreposicao_frontal)
    r = {
        "camera": chave, "altura_m": round(altura_m, 1), "gsd_cm": round(g * 100, 2),
        "pegada_m": {"largura": round(larg, 1), "altura": round(alt, 1)},
        "espacamento_linhas_m": round(linhas, 1), "espacamento_fotos_m": round(base, 1),
        "precisao_esperada_cm": {"horizontal": [round(g * 100, 1), round(2 * g * 100, 1)],
                                  "vertical": [round(1.5 * g * 100, 1), round(3 * g * 100, 1)]},
        "observacao": "Precisão típica com RTK/PPK ou pontos de controle; confirme com pontos de checagem.",
    }
    if area_ha:
        r["fotos_estimadas"] = math.ceil(area_ha * 10_000 / (linhas * base) * 1.15)  # +15 % nas bordas
    if altura_m > 120:
        r["alerta"] = "Acima de 120 m exige autorização específica (ANAC/DECEA)."
    return r


def fuso_utm(lon: float | str) -> dict:
    lo = angulo(lon)
    f = fuso_de(lo)
    return {"fuso": f, "meridiano_central": -183 + 6 * f}


def _numeros(xs: Iterable) -> list[float]:
    return [float(x) for x in xs]
