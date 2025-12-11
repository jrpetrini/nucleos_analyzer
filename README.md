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

## Usar Online

Acesse diretamente pelo navegador, sem instalar nada:

**https://huggingface.co/spaces/petrinijr/nucleos-analyzer**

Basta fazer upload do seu PDF e pronto!

## Funcionalidades

- Upload de PDF via navegador
- Extração automática de dados do extrato Nucleos
- Cálculo de CAGR (XIRR) usando dias úteis brasileiros (calendário ANBIMA)
- Gráfico de evolução da posição
- Gráfico de contribuições mensais
- Comparação com benchmarks: CDI, IPCA, INPC, S&P 500, USD
- Overhead configurável (+0% a +10% a.a.)
- Filtro de período (data inicial/final)
- Toggle para considerar contribuição da empresa como "sem custo"

## Como Obter o PDF

1. Acesse [planocd.nucleos.com.br](https://planocd.nucleos.com.br/)
2. Faça login com suas credenciais
3. No menu, vá em **Arrecadação** → **Extrato de Saldo Individual**
4. Selecione o período desejado (sugestão: da data de início do plano até o fim do ano seguinte, para pegar tudo)
5. Clique em **Gerar PDF**
6. Salve o arquivo "extratoIndividual.pdf"

## Executar Localmente

Se preferir rodar no seu computador, siga as instruções abaixo.

### Pré-requisitos

- **Python 3.10 ou superior** - [Download Python](https://www.python.org/downloads/)
- **Git** - [Download Git](https://git-scm.com/downloads/)
- **PDF do extrato individual Nucleos**

Para verificar se já estão instalados, abra o terminal e execute:

```bash
python3 --version   # Deve mostrar 3.10 ou superior
git --version       # Qualquer versão funciona
```

### Passo a Passo

**1. Baixar o código:**

```bash
git clone https://github.com/jrpetrini/nucleos_analyzer.git
cd nucleos_analyzer
```

**2. Criar ambiente virtual:**

O ambiente virtual isola as dependências do projeto. Execute:

```bash
python3 -m venv .venv
```

**3. Ativar o ambiente virtual:**

```bash
# Linux/macOS:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

Você verá `(.venv)` no início da linha do terminal quando estiver ativo.

**4. Instalar dependências:**

```bash
pip install -r requirements.txt
```

**5. Iniciar o dashboard:**

```bash
python main.py
```

**6. Acessar no navegador:**

Abra http://127.0.0.1:8050 e clique em "Carregar PDF" para fazer upload do seu extrato.

### Uso Avançado

Para iniciar com um PDF já carregado:

```bash
python main.py --pdf caminho/para/extratoIndividual.pdf
```

## Problemas Comuns

**"python3: command not found"**
- No Windows, tente `python` em vez de `python3`

**"pip: command not found"**
- Certifique-se de que o ambiente virtual está ativo (passo 3)

**Erro ao instalar dependências**
- Atualize o pip: `pip install --upgrade pip`
- Tente novamente: `pip install -r requirements.txt`

## Contribuir

Código fonte: https://github.com/jrpetrini/nucleos_analyzer

Encontrou um bug ou tem sugestões? Abra uma [issue](https://github.com/jrpetrini/nucleos_analyzer/issues)!
