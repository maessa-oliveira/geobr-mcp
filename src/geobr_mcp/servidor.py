"""Servidor MCP: expõe os cálculos geodésicos e topográficos como ferramentas para o Claude
(ou qualquer cliente MCP). Rode com ``geobr-mcp`` (transporte stdio)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import calculos as c

mcp = FastMCP(
    "geobr",
    instructions=(
        "Ferramentas de geodésia e topografia para o Brasil (SIRGAS 2000, SAD 69, UTM, RBMC/IBGE). "
        "Use-as sempre que precisar converter coordenadas, transformar datum, calcular área, "
        "poligonal, GSD de drone ou achar a estação RBMC mais próxima, em vez de calcular de cabeça. "
        "Ângulos aceitam graus decimais (negativos a sul/oeste) ou GMS como 12°58'30\"S."
    ),
)


@mcp.tool()
def geo_para_utm(lat: str, lon: str, datum: str = "SIRGAS2000", fuso: int | None = None) -> dict:
    """Converte latitude/longitude em coordenadas UTM (E, N, fuso), com fator de escala e
    convergência meridiana. datum: SIRGAS2000 (padrão) ou SAD69. fuso: força um fuso específico."""
    return c.geo_para_utm_pt(lat, lon, datum, fuso)


@mcp.tool()
def utm_para_geo(e: float, n: float, fuso: int, hemisferio: str = "S", datum: str = "SIRGAS2000") -> dict:
    """Converte coordenadas UTM (E, N, fuso, hemisfério S/N) em latitude/longitude."""
    return c.utm_para_geo_pt(e, n, fuso, hemisferio, datum)


@mcp.tool()
def transformar_datum(lat: str, lon: str, de: str, para: str, h: float = 0.0) -> dict:
    """Transforma coordenadas geográficas entre SAD 69 e SIRGAS 2000 com os parâmetros oficiais
    do IBGE (R.PR 1/2005). Informa também o deslocamento horizontal em metros."""
    return c.transformar_datum(lat, lon, de, para, h)


@mcp.tool()
def converter_lote(pontos: list[dict], de: str, para: str) -> dict:
    """Converte vários pontos de uma vez. de/para: 'GEO:SIRGAS2000', 'GEO:SAD69', 'UTM:SIRGAS2000'
    ou 'UTM:SAD69'. Pontos GEO: {'nome','lat','lon'}; pontos UTM: {'nome','e','n','fuso','hemisferio'}.
    Pontos com erro são listados em 'erros' sem interromper o lote."""
    return c.converter_lote(pontos, de, para)


@mcp.tool()
def area_poligono(pontos: list[dict], tipo: str = "utm") -> dict:
    """Área (m² e ha) e perímetro de um polígono. tipo='utm' com pontos {'e','n'} (área no plano
    UTM) ou tipo='geo' com pontos {'lat','lon'} (área geodésica no elipsoide GRS80)."""
    return c.area(pontos, tipo)


@mcp.tool()
def rbmc_mais_proximas(lat: str, lon: str, quantidade: int = 3, so_ativas: bool = True) -> dict:
    """Estações GNSS da RBMC (IBGE) mais próximas de uma coordenada: distância, azimute, situação
    na última semana, receptor e link do descritivo, com orientação prática (RTK, estático, PPP)."""
    return c.rbmc_mais_proximas(lat, lon, quantidade, so_ativas)


@mcp.tool()
def calcular_poligonal(
    estacoes: list[dict],
    tipo: str = "fechada",
    azimute_inicial: str | None = None,
    inicio: dict | None = None,
    apoio: dict | None = None,
    tolerancia_angular_seg: float = 20.0,
    precisao_minima: float = 5000.0,
    compensacao: str = "bowditch",
    fator_escala: float = 1.0,
) -> dict:
    """Calcula uma poligonal topográfica: fechamento angular (com tolerância T"·√n), fechamento
    linear, precisão 1:N, compensação (bowditch ou transito) e coordenadas.
    estacoes: [{'nome','angulo','distancia'}], ângulo horário lido de ré para vante, distância
    horizontal até a próxima estação. Fechada: azimute_inicial (1ª→2ª estação) e inicio {'e','n'}.
    Enquadrada: apoio {'re','partida','chegada','vante'} com {'e','n'} cada."""
    return c.poligonal(estacoes, tipo, azimute_inicial, inicio, apoio, tolerancia_angular_seg,
                       precisao_minima, compensacao, fator_escala)


@mcp.tool()
def gsd_drone(
    altura_m: float | None = None,
    gsd_cm: float | None = None,
    camera: str = "mavic 3 enterprise",
    sobreposicao_frontal: float = 0.8,
    sobreposicao_lateral: float = 0.7,
    area_ha: float | None = None,
) -> dict:
    """Geometria de aerolevantamento com drone: GSD a partir da altura (ou altura a partir do GSD),
    pegada da foto, espaçamento entre linhas e fotos, precisão esperada e fotos estimadas para a área.
    Câmeras: mavic 3 enterprise, matrice 4e, phantom 4 rtk, zenmuse p1 35mm, mini 4 pro."""
    return c.gsd_drone(altura_m, gsd_cm, camera, sobreposicao_frontal, sobreposicao_lateral, area_ha)


@mcp.tool()
def fuso_utm(lon: str) -> dict:
    """Fuso UTM e meridiano central para uma longitude."""
    return c.fuso_utm(lon)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
