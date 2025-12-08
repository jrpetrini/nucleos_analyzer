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

# Executar com arquivo PDF
python3 main.py caminho/para/extratoIndividual.pdf

# Ou executar sem argumento para abrir seletor de arquivo
python3 main.py
```

Acesse http://127.0.0.1:8050 no navegador.

## Funcionalidades

- Extração automática de dados do PDF Nucleos
- Cálculo de CAGR (XIRR) usando dias úteis brasileiros (calendário ANBIMA)
- Gráfico de evolução da posição
- Gráfico de contribuições mensais
- Comparação com benchmarks: CDI, IPCA, INPC, S&P 500, USD
- Overhead configurável (+0% a +10% a.a.)
