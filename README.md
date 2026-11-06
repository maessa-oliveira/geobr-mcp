# geobr-mcp

[![CI](https://github.com/maessa-oliveira/geobr-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/maessa-oliveira/geobr-mcp/actions/workflows/ci.yml)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-green)](LICENSE)

**Servidor MCP de geodésia e topografia para o Brasil.** Conecta assistentes de IA compatíveis
com o *Model Context Protocol* a cálculos geodésicos testados. Em vez de "fazer de
cabeça", a IA usa ferramentas conferidas contra o PROJ e os parâmetros oficiais do IBGE.

> 🇬🇧 *MCP server with Brazilian geodesy and land-surveying tools (UTM, SAD 69 ↔ SIRGAS 2000, RBMC
> GNSS stations, traverse adjustment, drone GSD), so AI assistants compute with tested code instead of guessing.*

## Exemplos de pedidos

> "Converta estes 40 pontos de UTM SAD 69 fuso 24 para SIRGAS 2000."
>
> "Qual a estação RBMC mais próxima de -12.97, -38.50 e ela está funcionando?"
>
> "Calcule esta poligonal fechada e me diga se atende 1:10.000."
>
> "A que altura voo com o Phantom 4 RTK para ter GSD de 2 cm? Quantas fotos para 30 ha?"

## Ferramentas

| Ferramenta | O que faz |
|---|---|
| `geo_para_utm` / `utm_para_geo` | Conversão com fator de escala, convergência meridiana e EPSG |
| `transformar_datum` | SAD 69 ↔ SIRGAS 2000 (IBGE R.PR 1/2005), com o deslocamento em metros |
| `converter_lote` | Muitos pontos de uma vez entre GEO/UTM e SAD 69/SIRGAS 2000, com erros por ponto |
| `area_poligono` | Área e perímetro no plano UTM ou geodésica (GRS80) |
| `rbmc_mais_proximas` | Estações RBMC/IBGE mais próximas: distância, azimute, situação na semana e orientação de uso |
| `calcular_poligonal` | Poligonal fechada ou enquadrada: tolerância angular, precisão 1:N, Bowditch/trânsito e coordenadas |
| `gsd_drone` | GSD, altura, pegada, espaçamentos, precisão esperada e fotos estimadas |
| `fuso_utm` | Fuso e meridiano central de uma longitude |

Ângulos aceitam graus decimais ou GMS (`12°58'30"S`). Os dados da RBMC vêm do
[Mapa da RBMC](https://maessa-oliveira.github.io/rbmc-mapa/), atualizado todo dia; sem internet,
o servidor usa uma cópia embutida.

## Instalação

Precisa do [uv](https://docs.astral.sh/uv/) (ou de Python 3.10+ com pip).

**Cliente MCP (arquivo de configuração)**: adicione ao bloco `mcpServers` do seu aplicativo:

```json
{
  "mcpServers": {
    "geobr": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/maessa-oliveira/geobr-mcp", "geobr-mcp"]
    }
  }
}
```

**Linha de comando**: `uvx --from git+https://github.com/maessa-oliveira/geobr-mcp geobr-mcp` inicia o servidor (stdio).

**Com pip**: `pip install git+https://github.com/maessa-oliveira/geobr-mcp` e use o comando `geobr-mcp`.

## Qualidade

```bash
pip install -e ".[dev]"
pytest
```

- Conversões UTM conferidas contra o **PROJ** (diferença < 2 mm) e distâncias/azimutes RBMC contra
  o `pyproj.Geod`.
- A poligonal dá o **mesmo resultado** da [calculadora web](https://maessa-oliveira.github.io/poligonal/).
- O servidor é testado **pelo próprio protocolo MCP** (cliente e servidor em memória): lista de
  ferramentas, chamadas e erros de entrada que não derrubam o servidor.

Usa a biblioteca [geobr-tools](https://github.com/maessa-oliveira/geobr-tools) para os cálculos geodésicos.

## Limites

- Transformação SAD 69 → SIRGAS 2000 pelos parâmetros de Helmert do IBGE (precisão de ~1 m);
  para trabalhos que exigem mais, use as grades oficiais (ProGriD).
- A orientação da RBMC é uma regra prática, não substitui o planejamento do levantamento.
- Resultados são de apoio: confira sempre antes de usar em documento técnico.

## Licença

MIT.
