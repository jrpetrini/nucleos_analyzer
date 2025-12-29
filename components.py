#!/usr/bin/env python3
"""
Reusable UI components for Nucleos Analyzer dashboard.
"""

from dash import html, dcc


def Dropdown(id, options, value, className='', disabled=False, **kwargs):
    """Create a dropdown with sensible defaults (no search, not clearable)."""
    style = {'color': '#000'}
    if disabled:
        style['opacity'] = '0.5'
    if 'style' in kwargs:
        style.update(kwargs.pop('style'))
    return dcc.Dropdown(
        id=id,
        options=options,
        value=value,
        clearable=False,
        searchable=False,
        disabled=disabled,
        className=className,
        style=style,
        **kwargs
    )


# Color palette - Nucleos-inspired light theme
COLORS = {
    'primary': '#1e40af',      # Blue 800 (Nucleos blue)
    'secondary': '#3b82f6',    # Blue 500
    'accent': '#0891b2',       # Cyan 600
    'participant': '#059669',  # Emerald 600
    'sponsor': '#d97706',      # Amber 600
    'danger': '#dc2626',       # Red 600
    'background': '#f1f5f9',   # Slate 100 (light gray)
    'card': '#ffffff',         # White
    'text': '#1e293b',         # Slate 800 (dark)
    'text_muted': '#64748b',   # Slate 500
    'grid': '#e2e8f0',         # Slate 200
}

# Common button styles
BUTTON_STYLE = {
    'backgroundColor': COLORS['primary'],
    'color': '#ffffff',
    'border': 'none',
    'borderRadius': '0.5rem',
    'padding': '0.5rem 1rem',
    'cursor': 'pointer',
}

BUTTON_DANGER_STYLE = {
    **BUTTON_STYLE,
    'backgroundColor': COLORS['danger'],
}

# Benchmark colors
BENCHMARK_COLORS = {
    'CDI': '#22c55e',          # Green
    'IPCA': '#ef4444',         # Red
    'INPC': '#f97316',         # Orange
    'S&P 500': '#3b82f6',      # Blue
    'USD': '#a855f7',          # Purple
}

# Overhead options
OVERHEAD_OPTIONS = [
    {'label': '+0%', 'value': 0},
    {'label': '+1%', 'value': 1},
    {'label': '+2%', 'value': 2},
    {'label': '+3%', 'value': 3},
    {'label': '+4%', 'value': 4},
    {'label': '+5%', 'value': 5},
    {'label': '+6%', 'value': 6},
    {'label': '+7%', 'value': 7},
    {'label': '+8%', 'value': 8},
    {'label': '+9%', 'value': 9},
    {'label': '+10%', 'value': 10},
]

# Help texts
HELP_TEXTS = {
    'benchmark': 'Compare sua carteira com índices de mercado. O benchmark simula quanto você teria se tivesse investido as mesmas contribuições no índice selecionado.',
    'overhead': 'Adiciona um retorno extra anual ao benchmark. Ex: INPC +4% simula um investimento que rende INPC mais 4% ao ano.',
    'cagr_nucleos': 'CAGR (Taxa de Crescimento Anual Composta) calculada usando XIRR com dias úteis brasileiros (252 dias/ano). Representa o retorno anualizado considerando todas as contribuições e suas datas exatas. O valor em R$ abaixo mostra o lucro total (posição menos investido).',
    'cagr_benchmark': 'Simula suas contribuições investidas no índice selecionado. O CAGR é calculado da mesma forma que o Nucleos. O valor em R$ abaixo mostra a posição total que você teria (não o lucro).',
    'company_as_mine': 'Quando ativado, só considera o que saiu do seu bolso - você recebe o patrimônio total mas a contribuição da empresa não conta como custo. Mostra o retorno real sobre seu dinheiro. Afeta tanto o Nucleos quanto o benchmark.',
    'pdf_upload': 'Faça upload do arquivo "extratoIndividual.pdf" do site da Nucleos. ⚠️ PRIVACIDADE: O PDF contém dados pessoais. Veja como redacionar: github.com/jrpetrini/nucleos_analyzer#privacidade-e-segurança (ou execute localmente).',
    'position_table': 'Tabela com os dados do gráfico. "Simulado" mostra quanto suas contribuições valeriam se investidas no benchmark. "Índice" mostra o valor bruto do índice (normalizado para 1 no início).',
    'contributions_table': 'Tabela com contribuições mensais, total investido acumulado e posição. Quando "Só meu aporte" está ativo, mostra a divisão participante/patrocinador.',
    'inflation_adjustment': 'Ajusta valores para mostrar retornos reais. IPCA: inflação oficial. INPC: inflação para salários. Valores são ajustados para o mês de referência.',
    'forecast': 'Projeta a posição no futuro usando o CAGR histórico e o padrão de contribuições. Quando o ajuste por inflação está ativo, a projeção também é deflacionada pela inflação projetada. Linha tracejada indica projeção (não garantida).',
    'salary_growth': 'Taxa de crescimento REAL do salário (acima da inflação), baseada no PCR (Plano de Carreira e Remuneração). Rápido: 3 passos a cada 2 anos (promoções frequentes). Médio: média geométrica. Lento: 0.5 passo por ano (progressão conservadora). A contribuição futura segue S(t) = S₀ × e^(taxa × t).',
}

# Forecast year options
FORECAST_OPTIONS = [
    {'label': '1 ano', 'value': 1},
    {'label': '2 anos', 'value': 2},
    {'label': '5 anos', 'value': 5},
    {'label': '10 anos', 'value': 10},
    {'label': '15 anos', 'value': 15},
    {'label': '20 anos', 'value': 20},
]

# Contribution growth rate options (salary progression, REAL rates above inflation)
# Fast: 4.43% real (PCR 3 steps every 2 years = 1.5 steps/year)
# Slow: 1.48% real (0.5 steps/year)
# Mid: geometric mean = sqrt(fast × slow) ≈ 2.56% real
import math
GROWTH_RATE_FAST = 0.0443
GROWTH_RATE_SLOW = GROWTH_RATE_FAST / 3  # 0.01477
GROWTH_RATE_MID = math.sqrt(GROWTH_RATE_FAST * GROWTH_RATE_SLOW)  # 0.02558

GROWTH_RATE_OPTIONS = [
    {'label': 'Lento (+1.5% real)', 'value': GROWTH_RATE_SLOW},
    {'label': 'Médio (+2.6% real)', 'value': GROWTH_RATE_MID},
    {'label': 'Rápido (+4.4% real)', 'value': GROWTH_RATE_FAST},
]

DEFAULT_GROWTH_RATE = GROWTH_RATE_MID


def create_help_icon(help_text: str, icon_id: str = None) -> html.Div:
    """Create a help icon with hover tooltip using CSS."""
    return html.Div([
        html.Span(
            '?',
            className='help-icon',
            style={
                'display': 'inline-flex',
                'alignItems': 'center',
                'justifyContent': 'center',
                'width': '16px',
                'height': '16px',
                'borderRadius': '50%',
                'backgroundColor': COLORS['grid'],
                'color': COLORS['text_muted'],
                'fontSize': '10px',
                'fontWeight': 'bold',
                'cursor': 'help',
                'marginLeft': '4px',
            }
        ),
        html.Div(
            help_text,
            className='help-tooltip',
            style={
                'display': 'none',
                'position': 'absolute',
                'backgroundColor': COLORS['card'],
                'color': COLORS['text'],
                'padding': '10px 14px',
                'borderRadius': '6px',
                'fontSize': '13px',
                'minWidth': '280px',
                'maxWidth': '400px',
                'width': 'max-content',
                'zIndex': '1000',
                'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.3)',
                'top': '100%',
                'left': '0',
                'marginTop': '4px',
                'whiteSpace': 'normal',
                'lineHeight': '1.5',
            }
        )
    ], style={
        'display': 'inline-block',
        'position': 'relative',
        'verticalAlign': 'middle',
    }, className='help-icon-container')


def create_summary_card(card_id: str, label: str, value_id: str,
                        color: str, help_text: str = None,
                        sub_value_id: str = None) -> html.Div:
    """Create a summary statistics card."""
    label_content = [label]
    if help_text:
        label_content.append(create_help_icon(help_text, f'help-{card_id}'))

    children = [
        html.P(
            label_content,
            style={
                'color': COLORS['text_muted'],
                'margin': '0',
                'fontSize': '0.875rem',
                'display': 'flex',
                'alignItems': 'center',
                'justifyContent': 'center'
            }
        ),
        html.H2(id=value_id, style={'color': color, 'margin': '0.5rem 0'})
    ]

    if sub_value_id:
        children.append(
            html.P(id=sub_value_id, style={'margin': '0', 'fontSize': '0.875rem'})
        )

    return html.Div(
        children,
        style={
            'backgroundColor': COLORS['card'],
            'padding': '1.5rem',
            'borderRadius': '0.75rem',
            'flex': '1',
            'textAlign': 'center'
        }
    )


def create_dropdown_with_label(label: str, dropdown_id: str, options: list,
                               value, size: str = 'md',
                               help_text: str = None) -> list:
    """Create a labeled dropdown with optional help icon.

    Args:
        size: 'sm', 'md', or 'lg' for dropdown width class
    """
    size_class = f'dropdown-{size}'
    components = [
        html.Label(label, style={'color': COLORS['text'], 'marginRight': '0.5rem'}),
        Dropdown(id=dropdown_id, options=options, value=value, className=size_class)
    ]
    if help_text:
        components.append(create_help_icon(help_text, f'help-{dropdown_id}'))
    return components


def create_export_controls(export_format_id: str, export_btn_id: str) -> html.Div:
    """Create export format dropdown and button."""
    return html.Div([
        Dropdown(
            id=export_format_id,
            options=[
                {'label': 'CSV', 'value': 'csv'},
                {'label': 'Excel', 'value': 'xlsx'}
            ],
            value='csv',
            className='dropdown-sm'
        ),
        html.Button('Exportar', id=export_btn_id, className='btn-primary', style={
            **BUTTON_STYLE,
            'marginLeft': '0.5rem'
        }),
    ], className='export-controls')


def create_data_table_styles() -> dict:
    """Return common DataTable style configurations."""
    return {
        'style_header': {
            'backgroundColor': COLORS['card'],
            'color': COLORS['text'],
            'fontWeight': 'bold',
            'border': f"1px solid {COLORS['grid']}",
        },
        'style_cell': {
            'backgroundColor': COLORS['background'],
            'color': COLORS['text'],
            'border': f"1px solid {COLORS['grid']}",
            'textAlign': 'right',
            'padding': '8px 12px',
        },
        'style_data_conditional': [
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': COLORS['card'],
            }
        ],
        'style_table': {
            'overflowY': 'auto',
            'maxHeight': '400px',
        },
    }


def create_tab_style() -> tuple:
    """Return tab and selected tab styles."""
    tab_style = {
        'backgroundColor': COLORS['card'],
        'color': COLORS['text_muted'],
        'border': 'none',
        'padding': '1rem 2rem'
    }
    selected_style = {
        'backgroundColor': COLORS['primary'],
        'color': '#ffffff',  # White text on blue background
        'border': 'none',
        'padding': '1rem 2rem'
    }
    return tab_style, selected_style
