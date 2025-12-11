---
title: Nucleos Analyzer
emoji: 📊
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# Nucleos Analyzer

Análise de extratos de previdência privada Nucleos com comparação de benchmarks.

## Requisitos

- Python 3.10+
- PDF do extrato individual Nucleos

## Instalação

```bash
# Clonar o repositório
git clone https://github.com/jrpetrini/nucleos_analyzer.git
cd nucleos_analyzer

# Criar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

## Como Executar

```bash
# Ativar ambiente virtual
source .venv/bin/activate

# Iniciar o dashboard
python main.py

# Ou iniciar com um PDF pré-carregado
python main.py --pdf caminho/para/extratoIndividual.pdf
```

Acesse http://127.0.0.1:8050 no navegador e clique em "Carregar PDF" para fazer upload do seu extrato.

## Funcionalidades

- Upload de PDF via navegador (botão "Carregar PDF")
- Extração automática de dados do PDF Nucleos
- Cálculo de CAGR (XIRR) usando dias úteis brasileiros (calendário ANBIMA)
- Gráfico de evolução da posição
- Gráfico de contribuições mensais
- Comparação com benchmarks: CDI, IPCA, INPC, S&P 500, USD
- Overhead configurável (+0% a +10% a.a.)
- Filtro de período (data inicial/final)
- Toggle para considerar contribuição da empresa como "sem custo"
