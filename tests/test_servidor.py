"""Testa o servidor pelo protocolo MCP de verdade (cliente e servidor em memória)."""

import json

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from geobr_mcp.servidor import mcp

ESPERADAS = {"geo_para_utm", "utm_para_geo", "transformar_datum", "converter_lote", "area_poligono",
             "rbmc_mais_proximas", "calcular_poligonal", "gsd_drone", "fuso_utm"}


def _rodar(fn):
    return anyio.run(fn)


async def _com_sessao(acao):
    async with create_connected_server_and_client_session(mcp._mcp_server) as s:
        return await acao(s)


def _json(res):
    assert not res.isError, res.content
    return json.loads(res.content[0].text)


def test_lista_ferramentas_com_descricao():
    async def acao(s):
        return (await s.list_tools()).tools
    tools = _rodar(lambda: _com_sessao(acao))
    nomes = {t.name for t in tools}
    assert ESPERADAS <= nomes
    assert all(t.description and len(t.description) > 40 for t in tools)


def test_chamadas_pelo_protocolo():
    async def acao(s):
        a = await s.call_tool("geo_para_utm", {"lat": "-12.9714", "lon": "-38.5014"})
        b = await s.call_tool("rbmc_mais_proximas", {"lat": "-12.9714", "lon": "-38.5014", "quantidade": 1})
        c = await s.call_tool("gsd_drone", {"altura_m": 100, "camera": "phantom 4 rtk"})
        d = await s.call_tool("transformar_datum", {"lat": "x", "lon": "0", "de": "SAD69", "para": "SIRGAS2000"})
        return a, b, c, d
    a, b, c, d = _rodar(lambda: _com_sessao(acao))
    assert _json(a)["fuso"] == 24
    assert _json(b)["estacoes"][0]["id"] == "SSA1"
    assert _json(c)["gsd_cm"] == pytest.approx(2.74, abs=0.01)
    assert d.isError  # entrada inválida vira erro de ferramenta, sem derrubar o servidor
