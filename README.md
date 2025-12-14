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

## Privacidade e Segurança

⚠️ **IMPORTANTE:** O extrato PDF da Nucleos contém informações pessoais (nome, CPF, endereço) no cabeçalho e rodapé.

### Para Máxima Privacidade

**Recomendamos executar localmente** (veja seção "Executar Localmente" abaixo) para manter seus dados completamente privados.

### Se Usar a Versão Online

O aplicativo **não armazena** seus dados pessoais - apenas extrai valores e datas das transações. No entanto, se você prefere não enviar o PDF original:

#### Método 1: Redação Manual (Mais Simples)

1. Abra o PDF em um leitor de PDF (Adobe Acrobat, Preview no Mac, etc.)
2. Use a ferramenta de redação/marcação para cobrir informações pessoais:
   - Nome completo
   - CPF
   - Endereço
   - Qualquer outro dado identificável no cabeçalho/rodapé
3. Salve como novo PDF
4. Faça upload do PDF redacionado

#### Método 2: Edição com Software PDF Gratuito

Use ferramentas **offline** instaladas no seu computador:

**Windows:**
- [PDF-XChange Editor](https://www.pdf-xchange.com/product/pdf-xchange-editor) (gratuito)
- Adobe Acrobat Reader (versão gratuita tem ferramentas básicas)

**Mac:**
- Preview (nativo) - use ferramentas de marcação/anotação
- [PDFtk](https://www.pdflabs.com/tools/pdftk-the-pdf-toolkit/)

**Linux:**
- [Okular](https://okular.kde.org/)
- [PDF Arranger](https://github.com/pdfarranger/pdfarranger)

Passos:
1. Abra o PDF no software escolhido
2. Use a ferramenta de retângulo/marcação preta para cobrir dados pessoais
3. Salve como novo PDF
4. **Teste:** Abra o PDF redacionado e verifique se consegue copiar o texto das transações (Ctrl+C). Se conseguir, o extrator funcionará.

**⚠️ Importante:** Não use "Imprimir para PDF" - isso pode converter o texto em imagem e quebrar a extração de dados.

### O Que o Aplicativo Extrai

Para transparência, o aplicativo extrai **apenas**:
- Valores das contribuições e saldos
- Datas das transações
- Classificação (participante vs. patrocinador)

**NÃO extrai:**
- Nomes, CPF, endereços
- Metadados do PDF
- Qualquer informação além de números e datas

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

## Notas Técnicas

### Convenção de Dias Úteis

O aplicativo usa a convenção de **252 dias úteis por ano**, padrão no mercado financeiro brasileiro. Em vez de consultar o calendário ANBIMA para cada data, utilizamos uma aproximação:

```
dias_úteis ≈ dias_corridos × (252 / 365.25)
```

**Por que esta aproximação?**

1. **Consistência matemática**: Todos os cálculos (XIRR, overhead, interpolação) usam a mesma fórmula
2. **Performance**: Não requer consultas a calendário externo
3. **Testabilidade**: Resultados são determinísticos e previsíveis

**Precisão**: A aproximação introduz diferença de ~0.04% no retorno anualizado comparado ao calendário ANBIMA. Para análise de investimentos pessoais, esta diferença é negligível.

### Ajuste por Inflação

Quando o ajuste por inflação está ativado, todos os valores são deflacionados usando a fórmula:

```
valor_real = valor_nominal × (índice_referência / índice_data)
```

Isso permite visualizar o poder de compra real dos seus investimentos ao longo do tempo.

<details>
<summary><strong>🧪 Suite de Testes (183 testes)</strong></summary>

### Executar Testes

```bash
# Todos os testes
pytest tests/ -v

# Sem testes de API externa (mais rápido)
pytest tests/ -m "not external_api"

# Apenas testes de API externa
pytest tests/ -m external_api

# Com cobertura
pytest tests/ --cov=. --cov-report=term-missing
```

### Estrutura dos Testes

| Arquivo | Testes | Descrição |
|---------|--------|-----------|
| `test_calculator.py` | 27 | XIRR, deflação, processamento de dados |
| `test_business_logic.py` | 30 | Lógica de cálculo de estatísticas e benchmarks |
| `test_benchmarks.py` | 49 | Simulação de benchmarks (CDI, IPCA, INPC, S&P500, USD) |
| `test_extractor.py` | 12 | Extração de dados do PDF |
| `test_dashboard_helpers.py` | 12 | Funções auxiliares da UI |
| `test_data_sources.py` | 13 | Cross-validação BCB vs IPEA APIs |
| `test_integration.py` | 34 | Testes end-to-end com PDFs reais |
| `conftest.py` | — | Fixtures compartilhadas |

### Cobertura de Código

| Módulo | Cobertura |
|--------|-----------|
| `calculator.py` | 97% |
| `business_logic.py` | 96% |
| `extractor.py` | 98% |
| `benchmarks.py` | 85% |
| `dashboard_helpers.py` | 100% |

### Testes de APIs Externas

Os testes em `test_data_sources.py` verificam:
- **BCB vs IPEA**: Dados idênticos entre fontes (IPCA, INPC, CDI)
- **Fallback automático**: Se BCB falhar, usa IPEA como backup
- **Disponibilidade**: Testes são SKIP (não FAIL) se API estiver offline

```python
# Exemplo: Cross-validação BCB vs IPEA
def test_ipca_bcb_matches_ipea():
    bcb_data = fetch_bcb_direct(433, '01/01/2024', '31/12/2024')
    ipea_data = fetch_ipea_direct('PRECOS12_IPCAG12')
    # Diferença máxima tolerada: 0.001%
    assert (bcb_data - ipea_data).abs().max() < 0.001
```

### Princípios dos Testes

1. **Valores exatos**: Testes usam valores calculados precisamente, não aproximações
2. **Investigar primeiro**: Se um teste falha, investigamos a causa antes de alterar o teste
3. **PDFs reais**: Testes de integração usam extratos reais (redacionados)
4. **Fallback resiliente**: Sistema continua funcionando mesmo com APIs instáveis

</details>

## Contribuir

Código fonte: https://github.com/jrpetrini/nucleos_analyzer

Encontrou um bug ou tem sugestões? Abra uma [issue](https://github.com/jrpetrini/nucleos_analyzer/issues)!
