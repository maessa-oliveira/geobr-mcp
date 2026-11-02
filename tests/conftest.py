import os

# os testes usam a cópia embutida dos dados da RBMC (resultado reproduzível, sem internet)
os.environ["GEOBR_MCP_OFFLINE"] = "1"
