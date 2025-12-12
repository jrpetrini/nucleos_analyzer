#!/usr/bin/env python3
"""
Dashboard UI components for Nucleos Analyzer.
"""

import base64
import io
import pandas as pd
import plotly.graph_objects as go
import dash
from dash import Dash, dcc, html, callback, Output, Input, State, dash_table

from calculator import calculate_summary_stats
from benchmarks import (
    AVAILABLE_BENCHMARKS, fetch_single_benchmark, apply_overhead_to_benchmark,
    simulate_benchmark
)

# Color palette
COLORS = {
    'primary': '#6366f1',      # Indigo
    'secondary': '#8b5cf6',    # Purple
    'accent': '#06b6d4',       # Cyan
    'participant': '#10b981',  # Emerald
    'sponsor': '#f59e0b',      # Amber
    'background': '#0f172a',   # Slate 900
    'card': '#1e293b',         # Slate 800
    'text': '#f1f5f9',         # Slate 100
    'text_muted': '#94a3b8',   # Slate 400
    'grid': '#334155',         # Slate 700
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
    'company_as_mine': 'Quando ativado, considera as contribuições da empresa como "de graça" - você recebe o patrimônio total mas só contabiliza o que saiu do seu bolso. Isso mostra o retorno real sobre seu dinheiro. Afeta tanto o Nucleos quanto o benchmark.',
    'pdf_upload': 'Faça upload do arquivo "extratoIndividual.pdf" do site da Nucleos. ⚠️ PRIVACIDADE: O PDF contém dados pessoais. Veja como redacionar: github.com/jrpetrini/nucleos_analyzer#privacidade-e-segurança (ou execute localmente).',
    'position_table': 'Tabela com os dados do gráfico. "Simulado" mostra quanto suas contribuições valeriam se investidas no benchmark. "Índice" mostra o valor bruto do índice (normalizado para 1 no início).',
    'contributions_table': 'Tabela com contribuições mensais, total investido acumulado e posição. Quando o toggle "empresa como sem custo" está ativo, mostra a divisão participante/patrocinador.',
}


def filter_data_by_range(df_pos: pd.DataFrame, df_contrib: pd.DataFrame,
                          start_date: str, end_date: str) -> tuple:
    """
    Filter position and contribution data to the selected date range.
    Adjusts position values to be relative to the position before the start date.

    Returns:
        tuple: (df_pos_filtered, df_contrib_filtered, position_before_start, date_before_start)
               date_before_start is None if there's no previous month (first month selected)
    """
    df_pos = df_pos.copy()
    df_contrib = df_contrib.copy()

    # Convert dates
    start_dt = pd.to_datetime(start_date) if start_date else None
    end_dt = pd.to_datetime(end_date) if end_date else None

    # Filter by date range
    if start_dt and end_dt:
        df_pos_filtered = df_pos[(df_pos['data'] >= start_dt) & (df_pos['data'] <= end_dt)].copy()
        # Filter contributions by month to include all contributions in start month
        df_contrib_filtered = df_contrib[
            (df_contrib['data'].dt.to_period('M') >= start_dt.to_period('M')) &
            (df_contrib['data'].dt.to_period('M') <= end_dt.to_period('M'))
        ].copy()
    else:
        df_pos_filtered = df_pos.copy()
        df_contrib_filtered = df_contrib.copy()

    # Find position BEFORE the start date (and its actual date for XIRR)
    position_before_start = 0
    date_before_start = None
    if not df_pos_filtered.empty:
        selected_start = df_pos_filtered['data'].iloc[0]
        df_before = df_pos[df_pos['data'] < selected_start]
        if len(df_before) > 0:
            position_before_start = df_before['posicao'].iloc[-1]
            date_before_start = df_before['data'].iloc[-1]

    # Adjust position values to be relative to start
    if not df_pos_filtered.empty:
        df_pos_filtered['posicao'] = df_pos_filtered['posicao'] - position_before_start

    return df_pos_filtered, df_contrib_filtered, position_before_start, date_before_start


def calculate_time_weighted_position(df_contrib: pd.DataFrame,
                                      start_position: float,
                                      end_position: float,
                                      period_start: pd.Timestamp,
                                      period_end: pd.Timestamp,
                                      contribution_col: str = 'contribuicao_total') -> tuple:
    """
    Calculate time-weighted return rate and position for contributions in a period.

    Uses the formula:
    r = (End - Start - ΣContributions) / (Start + Σ(Contribution_i × fraction_i))

    Where fraction_i = days remaining in period / total days in period

    Args:
        df_contrib: DataFrame with contributions (must have 'data' and contribution_col columns)
        start_position: Position at start of period (0 if first period)
        end_position: Position at end of period
        period_start: Start date of period
        period_end: End date of period
        contribution_col: Column name for contribution amounts

    Returns:
        tuple: (return_rate, contributions_with_returns)
               contributions_with_returns = sum of (contribution × (1 + r × fraction))
    """
    if df_contrib.empty:
        # No contributions in period
        if start_position > 0:
            return_rate = (end_position / start_position) - 1
            return return_rate, 0.0
        else:
            return 0.0, 0.0

    total_days = (period_end - period_start).days
    if total_days <= 0:
        total_days = 1  # Avoid division by zero for same-day

    # Calculate fraction for each contribution (days remaining / total days)
    contributions = df_contrib[contribution_col].values
    dates = pd.to_datetime(df_contrib['data'])

    fractions = []
    for date in dates:
        days_remaining = (period_end - date).days
        fraction = max(0, min(1, days_remaining / total_days))
        fractions.append(fraction)

    fractions = pd.Series(fractions)

    # Calculate weighted sum for denominator
    weighted_contrib_sum = (contributions * fractions).sum()
    total_contributions = contributions.sum()

    # r = (End - Start - ΣContributions) / (Start + Σ(Contribution_i × fraction_i))
    denominator = start_position + weighted_contrib_sum
    if denominator <= 0:
        # Edge case: no starting position and no time-weighted contributions
        return 0.0, total_contributions

    numerator = end_position - start_position - total_contributions
    return_rate = numerator / denominator

    # Calculate what each contribution is worth at period end
    # contribution_value = contribution × (1 + r × fraction)
    contribution_values = contributions * (1 + return_rate * fractions)
    contributions_with_returns = contribution_values.sum()

    return return_rate, contributions_with_returns


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
                'fontSize': '11px',
                'fontWeight': 'bold',
                'cursor': 'help',
                'marginLeft': '6px',
            }
        ),
        html.Div(
            help_text,
            className='help-tooltip',
            style={
                'visibility': 'hidden',
                'opacity': '0',
                'position': 'absolute',
                'backgroundColor': COLORS['card'],
                'color': COLORS['text'],
                'padding': '8px 12px',
                'borderRadius': '6px',
                'fontSize': '12px',
                'minWidth': '280px',
                'maxWidth': '40vw',
                'boxShadow': '0 4px 6px rgba(0,0,0,0.3)',
                'zIndex': '1000',
                'top': '100%',
                'left': '0',
                'marginTop': '5px',
                'transition': 'opacity 0.2s, visibility 0.2s',
                'whiteSpace': 'normal',
                'lineHeight': '1.4',
            }
        )
    ], style={
        'display': 'inline-block',
        'position': 'relative',
    }, className='help-container')


def create_position_figure(df_position: pd.DataFrame, log_scale: bool = False,
                           benchmark_sim: pd.DataFrame = None,
                           benchmark_label: str = None) -> go.Figure:
    """Create the position line chart with optional benchmark comparison.

    Args:
        df_position: Pre-filtered position data with adjusted values
        benchmark_sim: Pre-filtered benchmark simulation data
    """
    fig = go.Figure()

    # Main position line
    if not df_position.empty:
        fig.add_trace(go.Scatter(
            x=df_position['data'],
            y=df_position['posicao'],
            mode='lines+markers',
            name='Nucleos',
            line=dict(color=COLORS['primary'], width=3),
            marker=dict(size=8, color=COLORS['primary']),
            hovertemplate='<b>%{x|%b %Y}</b><br>Nucleos: R$ %{y:,.2f}<extra></extra>'
        ))

    # Add benchmark curve if available
    if benchmark_sim is not None and not benchmark_sim.empty and benchmark_label:
        # Get base benchmark name for color
        base_name = benchmark_label.split('+')[0].strip()
        color = BENCHMARK_COLORS.get(base_name, '#888888')

        fig.add_trace(go.Scatter(
            x=benchmark_sim['data'],
            y=benchmark_sim['posicao'],
            mode='lines+markers',
            name=benchmark_label,
            line=dict(color=color, width=2, dash='dash'),
            marker=dict(size=5, color=color),
            hovertemplate=f'<b>%{{x|%b %Y}}</b><br>{benchmark_label}: R$ %{{y:,.2f}}<extra></extra>'
        ))

    fig.update_layout(
        title=dict(
            text='Evolução da Posição',
            font=dict(size=24, color=COLORS['text']),
            x=0.5
        ),
        xaxis=dict(
            title='',
            gridcolor=COLORS['grid'],
            tickfont=dict(color=COLORS['text_muted']),
            tickformat='%b %Y'
        ),
        yaxis=dict(
            title=dict(text='Posição (R$)', font=dict(color=COLORS['text'])),
            type='log' if log_scale else 'linear',
            gridcolor=COLORS['grid'],
            tickfont=dict(color=COLORS['text_muted']),
            tickformat=',.0f'
        ),
        plot_bgcolor=COLORS['card'],
        paper_bgcolor=COLORS['background'],
        hovermode='x unified',
        margin=dict(l=80, r=40, t=80, b=60),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
            font=dict(color=COLORS['text'])
        )
    )

    return fig


def create_contributions_figure(df_contributions: pd.DataFrame,
                                 df_position: pd.DataFrame = None,
                                 show_split: bool = False) -> go.Figure:
    """Create the contributions bar chart with position and invested curves.

    Args:
        df_contributions: Pre-filtered monthly contribution data
        df_position: Pre-filtered and adjusted position data
    """
    fig = go.Figure()

    if show_split and 'contrib_participante' in df_contributions.columns:
        # Stacked bar chart
        fig.add_trace(go.Bar(
            x=df_contributions['data'],
            y=df_contributions['contrib_participante'],
            name='Participante',
            marker_color=COLORS['participant'],
            hovertemplate='<b>%{x|%b %Y}</b><br>Participante: R$ %{y:,.2f}<extra></extra>'
        ))
        fig.add_trace(go.Bar(
            x=df_contributions['data'],
            y=df_contributions['contrib_patrocinador'],
            name='Patrocinador',
            marker_color=COLORS['sponsor'],
            hovertemplate='<b>%{x|%b %Y}</b><br>Patrocinador: R$ %{y:,.2f}<extra></extra>'
        ))
        fig.update_layout(barmode='stack')
    else:
        # Combined bar chart
        fig.add_trace(go.Bar(
            x=df_contributions['data'],
            y=df_contributions['contribuicao_total'],
            name='Contribuição Mensal',
            marker_color=COLORS['participant'],
            hovertemplate='<b>%{x|%b %Y}</b><br>Contribuição: R$ %{y:,.2f}<extra></extra>'
        ))

    # Add cumulative invested line
    invested_cumsum = df_contributions['contribuicao_total'].cumsum()
    fig.add_trace(go.Scatter(
        x=df_contributions['data'],
        y=invested_cumsum,
        mode='lines+markers',
        name='Total Investido',
        line=dict(color=COLORS['accent'], width=3),
        marker=dict(size=6),
        yaxis='y2',
        hovertemplate='<b>%{x|%b %Y}</b><br>Total Investido: R$ %{y:,.2f}<extra></extra>'
    ))

    # Add position curve (already adjusted relative to start of range)
    if df_position is not None and not df_position.empty:
        fig.add_trace(go.Scatter(
            x=df_position['data'],
            y=df_position['posicao'],
            mode='lines+markers',
            name='Variação Posição',
            line=dict(color=COLORS['primary'], width=3),
            marker=dict(size=6),
            yaxis='y2',
            hovertemplate='<b>%{x|%b %Y}</b><br>Variação: R$ %{y:,.2f}<extra></extra>'
        ))

    fig.update_layout(
        title=dict(
            text='Contribuições Mensais',
            font=dict(size=24, color=COLORS['text']),
            x=0.5
        ),
        xaxis=dict(
            title='',
            gridcolor=COLORS['grid'],
            tickfont=dict(color=COLORS['text_muted']),
            tickformat='%b %Y'
        ),
        yaxis=dict(
            title=dict(text='Contribuição Mensal (R$)', font=dict(color=COLORS['text'])),
            gridcolor=COLORS['grid'],
            tickfont=dict(color=COLORS['text_muted']),
            tickformat=',.0f'
        ),
        yaxis2=dict(
            title=dict(text='Valor (R$)', font=dict(color=COLORS['text'])),
            overlaying='y',
            side='right',
            tickfont=dict(color=COLORS['text_muted']),
            tickformat=',.0f',
            showgrid=False
        ),
        plot_bgcolor=COLORS['card'],
        paper_bgcolor=COLORS['background'],
        hovermode='x unified',
        margin=dict(l=80, r=80, t=80, b=60),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
            font=dict(color=COLORS['text'])
        )
    )

    return fig


def create_empty_figure(message: str = "Sem dados") -> go.Figure:
    """Create an empty placeholder figure with a message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=20, color=COLORS['text_muted'])
    )
    fig.update_layout(
        plot_bgcolor=COLORS['background'],
        paper_bgcolor=COLORS['background'],
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        margin=dict(l=40, r=40, t=40, b=40)
    )
    return fig


def create_app(df_position: pd.DataFrame = None,
               df_contributions_raw: pd.DataFrame = None,
               df_contributions_monthly: pd.DataFrame = None) -> Dash:
    """
    Create the Dash application.

    Args:
        df_position: Processed position data (optional - can start without data)
        df_contributions_raw: Raw contributions with exact dates (for XIRR)
        df_contributions_monthly: Monthly aggregated contributions (for charts)

    Returns:
        Configured Dash application
    """
    app = Dash(__name__, suppress_callback_exceptions=True)

    # Check if we have data
    has_data = df_position is not None and not df_position.empty

    if has_data:
        min_date = df_position['data'].min()
        max_date = df_position['data'].max()

        # Create month options for dropdowns
        month_options = [
            {'label': d.strftime('%b %Y'), 'value': d.isoformat()}
            for d in df_position['data']
        ]

        # Calculate summary stats
        stats = calculate_summary_stats(df_position, df_contributions_raw, df_contributions_monthly)

        # Pre-create figures
        initial_position_fig = create_position_figure(df_position, log_scale=False)
        contributions_fig = create_contributions_figure(df_contributions_monthly, show_split=False)

        # Date range for benchmark fetching
        start_date_str = df_contributions_raw['data'].min().strftime('%Y-%m-%d')
        end_date_str = df_position['data'].max().strftime('%Y-%m-%d')

        # Convert data to dict for stores
        position_data = df_position.to_dict('records')
        contributions_data = df_contributions_raw.to_dict('records')
        contributions_monthly_data = df_contributions_monthly.to_dict('records')
    else:
        # Empty state defaults
        min_date = None
        max_date = None
        month_options = []
        stats = {}
        initial_position_fig = create_empty_figure("Carregue um PDF para visualizar")
        contributions_fig = create_empty_figure("Carregue um PDF para visualizar")
        start_date_str = ''
        end_date_str = ''
        position_data = []
        contributions_data = []
        contributions_monthly_data = []

    # Benchmark options (always available)
    benchmark_options = [{'label': 'Nenhum', 'value': 'none'}] + [
        {'label': name, 'value': name} for name in AVAILABLE_BENCHMARKS
    ]

    app.layout = html.Div([
        # Header
        html.Div([
            html.Div([
                html.H1('Nucleos Analyzer', style={
                    'color': COLORS['text'],
                    'marginBottom': '0',
                    'fontSize': '2.5rem'
                }),
                html.P('Análise de Previdência Privada', style={
                    'color': COLORS['text_muted'],
                    'marginTop': '0.5rem'
                })
            ]),
            html.A(
                html.Img(
                    src='https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png',
                    style={'height': '32px', 'opacity': '0.7'}
                ),
                href='https://github.com/jrpetrini/nucleos_analyzer',
                target='_blank',
                title='Ver código no GitHub',
                style={
                    'position': 'absolute',
                    'top': '1rem',
                    'right': '1rem'
                }
            )
        ], style={
            'textAlign': 'center',
            'padding': '2rem',
            'backgroundColor': COLORS['background'],
            'position': 'relative'
        }),

        # Global toggle - Company contributions as mine
        html.Div([
            html.Div([
                dcc.Checklist(
                    id='company-as-mine-toggle',
                    options=[{'label': ' Considerar contribuições da empresa como sem custo', 'value': 'as_mine'}],
                    value=[],  # Default: OFF (count company contributions as invested)
                    style={'color': COLORS['text']},
                    labelStyle={'display': 'flex', 'alignItems': 'center'}
                ),
                create_help_icon(HELP_TEXTS['company_as_mine'], 'help-company-toggle'),
            ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'})
        ], style={
            'padding': '0 2rem 1rem 2rem',
            'backgroundColor': COLORS['background']
        }),

        # Summary Cards (wrapped in loading indicator)
        dcc.Loading(
            id='loading-summary-cards',
            type='circle',
            color=COLORS['primary'],
            children=[
                html.Div([
                    # TODO: Fix "Posição Atual" - should match end of selected date range
                    html.Div([
                html.P('Posição Atual', style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'}),
                html.H2(id='current-position-value', style={'color': COLORS['primary'], 'margin': '0.5rem 0'})
            ], style={
                'backgroundColor': COLORS['card'],
                'padding': '1.5rem',
                'borderRadius': '0.75rem',
                'flex': '1',
                'textAlign': 'center'
            }),
            html.Div([
                html.Div([
                    html.P('Total Investido', style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'}),
                ]),
                html.H2(id='total-invested-value', style={'color': COLORS['participant'], 'margin': '0.5rem 0'})
            ], style={
                'backgroundColor': COLORS['card'],
                'padding': '1.5rem',
                'borderRadius': '0.75rem',
                'flex': '1',
                'textAlign': 'center'
            }),
            html.Div([
                html.Div([
                    html.P([
                        'Rendimento Nucleos (CAGR)',
                        create_help_icon(HELP_TEXTS['cagr_nucleos'], 'help-cagr-nucleos')
                    ], style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem', 'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'}),
                ]),
                html.H2(id='nucleos-cagr-value', style={'margin': '0.5rem 0'}),
                html.P(id='nucleos-return-value', style={'margin': '0', 'fontSize': '0.875rem'})
            ], style={
                'backgroundColor': COLORS['card'],
                'padding': '1.5rem',
                'borderRadius': '0.75rem',
                'flex': '1',
                'textAlign': 'center'
            }),
            # Benchmark CAGR card
            html.Div(id='benchmark-cagr-card', children=[
                html.Div([
                    html.P([
                        'Rendimento Benchmark',
                        create_help_icon(HELP_TEXTS['cagr_benchmark'], 'help-cagr-benchmark')
                    ], style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem', 'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'}),
                ]),
                html.H2(id='benchmark-cagr-value', children='--', style={
                    'color': COLORS['text_muted'],
                    'margin': '0.5rem 0'
                }),
                html.P(id='benchmark-cagr-label', children='Selecione um benchmark', style={
                    'color': COLORS['text_muted'],
                    'margin': '0',
                    'fontSize': '0.875rem'
                })
            ], style={
                'backgroundColor': COLORS['card'],
                'padding': '1.5rem',
                'borderRadius': '0.75rem',
                'flex': '1',
                'textAlign': 'center'
            }),
                ], style={
                    'display': 'flex',
                    'gap': '1rem',
                    'padding': '0 2rem',
                    'marginBottom': '2rem',
                    'backgroundColor': COLORS['background']
                }),
            ]
        ),

        # Shared controls (persist between tabs)
        html.Div(id='date-controls', children=[
            html.Div([
                html.Label('De:', style={'color': COLORS['text'], 'marginRight': '0.5rem'}),
                dcc.Dropdown(
                    id='start-month',
                    options=month_options,
                    value=min_date.isoformat() if min_date else None,
                    clearable=False,
                    style={'width': '130px', 'color': '#000'}
                ),
                html.Label('Até:', style={'color': COLORS['text'], 'margin': '0 0.5rem 0 1rem'}),
                dcc.Dropdown(
                    id='end-month',
                    options=month_options,
                    value=max_date.isoformat() if max_date else None,
                    clearable=False,
                    style={'width': '130px', 'color': '#000'}
                ),
                # PDF Upload - amber when no data, primary when loaded
                dcc.Loading(
                    id='loading-pdf-upload',
                    type='circle',
                    color=COLORS['sponsor'],
                    children=[
                        dcc.Upload(
                            id='pdf-upload',
                            children=html.Div([
                                html.Span('📄 ', style={'marginRight': '0.5rem'}),
                                'Carregar PDF'
                            ]),
                            style={
                                'marginLeft': '2rem',
                                'padding': '0.5rem 1rem',
                                'backgroundColor': COLORS['primary'] if has_data else COLORS['sponsor'],
                                'color': COLORS['text'],
                                'border': 'none',
                                'borderRadius': '0.5rem',
                                'cursor': 'pointer',
                                'display': 'inline-block'
                            },
                            accept='.pdf'
                        ),
                    ]
                ),
                create_help_icon(HELP_TEXTS['pdf_upload'], 'help-pdf-upload'),
            ], style={'display': 'flex', 'alignItems': 'center'})
        ], style={
            'display': 'flex',
            'justifyContent': 'center',
            'padding': '0 2rem 1rem 2rem',
            'backgroundColor': COLORS['background']
        }),

        # Tabs
        dcc.Tabs(id='tabs', value='position', children=[
            dcc.Tab(label='Posição', value='position', style={
                'backgroundColor': COLORS['card'],
                'color': COLORS['text_muted'],
                'border': 'none',
                'padding': '1rem 2rem'
            }, selected_style={
                'backgroundColor': COLORS['primary'],
                'color': COLORS['text'],
                'border': 'none',
                'padding': '1rem 2rem'
            }),
            dcc.Tab(label='Contribuições', value='contributions', style={
                'backgroundColor': COLORS['card'],
                'color': COLORS['text_muted'],
                'border': 'none',
                'padding': '1rem 2rem'
            }, selected_style={
                'backgroundColor': COLORS['primary'],
                'color': COLORS['text'],
                'border': 'none',
                'padding': '1rem 2rem'
            }),
        ], style={'padding': '0 2rem'}),

        # Position Tab Content
        html.Div(id='position-tab', children=[
            # Controls Row 1
            html.Div([
                html.Div([
                    html.Label('Escala Y:', style={'color': COLORS['text'], 'marginRight': '1rem'}),
                    dcc.RadioItems(
                        id='scale-toggle',
                        options=[
                            {'label': ' Linear', 'value': 'linear'},
                            {'label': ' Logarítmica', 'value': 'log'}
                        ],
                        value='linear',
                        inline=True,
                        style={'color': COLORS['text']},
                        labelStyle={'marginRight': '1rem'}
                    )
                ], style={'display': 'flex', 'alignItems': 'center'}),
            ], style={
                'display': 'flex',
                'justifyContent': 'flex-start',
                'marginBottom': '1rem',
                'flexWrap': 'wrap',
                'gap': '1rem'
            }),
            # Controls Row 2 - Benchmark selection
            html.Div([
                html.Label('Comparar com:', style={'color': COLORS['text'], 'marginRight': '0.5rem'}),
                dcc.Dropdown(
                    id='benchmark-select',
                    options=benchmark_options,
                    value='INPC',  # Default to INPC
                    clearable=False,
                    style={'width': '150px', 'color': '#000'}
                ),
                create_help_icon(HELP_TEXTS['benchmark'], 'help-benchmark'),
                html.Label('Overhead:', style={'color': COLORS['text'], 'margin': '0 0.5rem 0 1rem'}),
                dcc.Dropdown(
                    id='overhead-select',
                    options=OVERHEAD_OPTIONS,
                    value=4,  # Default to +4%
                    clearable=False,
                    style={'width': '100px', 'color': '#000'}
                ),
                create_help_icon(HELP_TEXTS['overhead'], 'help-overhead'),
            ], style={
                'display': 'flex',
                'alignItems': 'center',
                'marginBottom': '1rem',
                'flexWrap': 'wrap',
                'gap': '0.5rem'
            }),
            # Graph with loading indicator
            dcc.Loading(
                id='loading-graph',
                type='circle',
                color=COLORS['primary'],
                children=[
                    dcc.Graph(id='position-graph', figure=initial_position_fig, style={'height': '500px'})
                ]
            ),
            # Data Table Section
            html.Div([
                html.Div([
                    html.Div([
                        html.H3('Dados', style={'color': COLORS['text'], 'margin': '0'}),
                        create_help_icon(HELP_TEXTS['position_table'], 'help-position-table'),
                    ], style={'display': 'flex', 'alignItems': 'center'}),
                    html.Div([
                        dcc.Dropdown(
                            id='position-export-format',
                            options=[
                                {'label': 'CSV', 'value': 'csv'},
                                {'label': 'Excel', 'value': 'xlsx'}
                            ],
                            value='csv',
                            clearable=False,
                            style={'width': '100px', 'color': '#000'}
                        ),
                        html.Button('Exportar', id='position-export-btn', style={
                            'backgroundColor': COLORS['primary'],
                            'color': COLORS['text'],
                            'border': 'none',
                            'borderRadius': '0.5rem',
                            'padding': '0.5rem 1rem',
                            'cursor': 'pointer',
                            'marginLeft': '0.5rem'
                        }),
                    ], style={'display': 'flex', 'alignItems': 'center'}),
                ], style={
                    'display': 'flex',
                    'justifyContent': 'space-between',
                    'alignItems': 'center',
                    'marginBottom': '1rem'
                }),
                dcc.Loading(
                    id='loading-position-table',
                    type='circle',
                    color=COLORS['primary'],
                    children=[
                        dash_table.DataTable(
                            id='position-data-table',
                            columns=[],
                            data=[],
                            style_header={
                                'backgroundColor': COLORS['card'],
                                'color': COLORS['text'],
                                'fontWeight': 'bold',
                                'border': f"1px solid {COLORS['grid']}",
                            },
                            style_cell={
                                'backgroundColor': COLORS['background'],
                                'color': COLORS['text'],
                                'border': f"1px solid {COLORS['grid']}",
                                'textAlign': 'right',
                                'padding': '8px 12px',
                            },
                            style_data_conditional=[
                                {
                                    'if': {'row_index': 'odd'},
                                    'backgroundColor': COLORS['card'],
                                }
                            ],
                            style_table={
                                'overflowY': 'auto',
                                'maxHeight': '400px',
                            },
                            page_action='none',
                            sort_action='native',
                        ),
                    ]
                ),
                dcc.Download(id='position-download'),
            ], style={'marginTop': '2rem'}),
        ], style={
            'padding': '2rem',
            'backgroundColor': COLORS['background'],
            'minHeight': '600px',
            'display': 'block'
        }),

        # Contributions Tab Content
        html.Div(id='contributions-tab', children=[
            dcc.Loading(
                id='loading-contributions-graph',
                type='circle',
                color=COLORS['primary'],
                children=[dcc.Graph(id='contributions-graph', figure=contributions_fig, style={'height': '500px'})]
            ),
            # Data Table Section
            html.Div([
                html.Div([
                    html.Div([
                        html.H3('Dados', style={'color': COLORS['text'], 'margin': '0'}),
                        create_help_icon(HELP_TEXTS['contributions_table'], 'help-contributions-table'),
                    ], style={'display': 'flex', 'alignItems': 'center'}),
                    html.Div([
                        dcc.Dropdown(
                            id='contributions-export-format',
                            options=[
                                {'label': 'CSV', 'value': 'csv'},
                                {'label': 'Excel', 'value': 'xlsx'}
                            ],
                            value='csv',
                            clearable=False,
                            style={'width': '100px', 'color': '#000'}
                        ),
                        html.Button('Exportar', id='contributions-export-btn', style={
                            'backgroundColor': COLORS['primary'],
                            'color': COLORS['text'],
                            'border': 'none',
                            'borderRadius': '0.5rem',
                            'padding': '0.5rem 1rem',
                            'cursor': 'pointer',
                            'marginLeft': '0.5rem'
                        }),
                    ], style={'display': 'flex', 'alignItems': 'center'}),
                ], style={
                    'display': 'flex',
                    'justifyContent': 'space-between',
                    'alignItems': 'center',
                    'marginBottom': '1rem'
                }),
                dcc.Loading(
                    id='loading-contributions-table',
                    type='circle',
                    color=COLORS['primary'],
                    children=[
                        dash_table.DataTable(
                            id='contributions-data-table',
                            columns=[],
                            data=[],
                            style_header={
                                'backgroundColor': COLORS['card'],
                                'color': COLORS['text'],
                                'fontWeight': 'bold',
                                'border': f"1px solid {COLORS['grid']}",
                            },
                            style_cell={
                                'backgroundColor': COLORS['background'],
                                'color': COLORS['text'],
                                'border': f"1px solid {COLORS['grid']}",
                                'textAlign': 'right',
                                'padding': '8px 12px',
                            },
                            style_data_conditional=[
                                {
                                    'if': {'row_index': 'odd'},
                                    'backgroundColor': COLORS['card'],
                                }
                            ],
                            style_table={
                                'overflowY': 'auto',
                                'maxHeight': '400px',
                            },
                            page_action='none',
                            sort_action='native',
                        ),
                    ]
                ),
                dcc.Download(id='contributions-download'),
            ], style={'marginTop': '2rem'}),
        ], style={
            'padding': '2rem',
            'backgroundColor': COLORS['background'],
            'minHeight': '600px',
            'display': 'none'
        }),

        # Store data for callbacks
        dcc.Store(id='position-data', data=position_data),
        dcc.Store(id='contributions-data', data=contributions_data),
        dcc.Store(id='contributions-monthly-data', data=contributions_monthly_data),
        dcc.Store(id='data-loaded', data=has_data),
        dcc.Store(id='date-range-data', data={'start': start_date_str, 'end': end_date_str}),
        dcc.Store(id='benchmark-cache', data={}),
        dcc.Store(id='stats-data', data=stats),
        dcc.Store(id='month-options', data=month_options),

    ], style={
        'backgroundColor': COLORS['background'],
        'minHeight': '100vh',
        'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    })

    @callback(
        Output('position-tab', 'style'),
        Output('contributions-tab', 'style'),
        Input('tabs', 'value')
    )
    def toggle_tabs(tab):
        position_style = {
            'padding': '2rem',
            'backgroundColor': COLORS['background'],
            'minHeight': '600px',
            'display': 'block' if tab == 'position' else 'none'
        }
        contributions_style = {
            'padding': '2rem',
            'backgroundColor': COLORS['background'],
            'minHeight': '600px',
            'display': 'block' if tab == 'contributions' else 'none'
        }
        return position_style, contributions_style

    @callback(
        Output('end-month', 'options'),
        Output('end-month', 'value'),
        Input('start-month', 'value'),
        Input('month-options', 'data'),
        State('end-month', 'value')
    )
    def update_end_month_options(start_month, all_options, current_end):
        """Filter end month options to only show months >= start month."""
        if not start_month or not all_options:
            return all_options or [], current_end

        start_dt = pd.to_datetime(start_month)
        filtered_options = [
            opt for opt in all_options
            if pd.to_datetime(opt['value']) >= start_dt
        ]

        # If no current end (fresh upload), set to max date
        if not current_end and filtered_options:
            new_end = filtered_options[-1]['value']
        # If current end is before start, update to start
        elif current_end and pd.to_datetime(current_end) < start_dt:
            new_end = start_month
        else:
            new_end = current_end

        return filtered_options, new_end

    @callback(
        Output('current-position-value', 'children'),
        Output('total-invested-value', 'children'),
        Output('nucleos-cagr-value', 'children'),
        Output('nucleos-cagr-value', 'style'),
        Output('nucleos-return-value', 'children'),
        Output('nucleos-return-value', 'style'),
        Input('company-as-mine-toggle', 'value'),
        Input('start-month', 'value'),
        Input('end-month', 'value'),
        State('contributions-data', 'data'),
        State('position-data', 'data'),
    )
    def update_nucleos_stats(company_as_mine, start_date, end_date, contributions_data, position_data):
        # Guard for empty data
        if not contributions_data or not position_data:
            return ('R$ 0,00', 'R$ 0,00', 'N/A', {'color': COLORS['text_muted'], 'margin': '0.5rem 0'},
                    'R$ 0,00 total', {'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'})

        df_contrib = pd.DataFrame(contributions_data)
        df_contrib['data'] = pd.to_datetime(df_contrib['data'])
        df_pos = pd.DataFrame(position_data)
        df_pos['data'] = pd.to_datetime(df_pos['data'])

        # Filter data using helper function
        df_pos_filtered, df_contrib_filtered, position_before_start, date_before_start = filter_data_by_range(
            df_pos, df_contrib, start_date, end_date
        )

        if df_pos_filtered.empty:
            return ('R$ 0,00', 'R$ 0,00', 'N/A', {'color': COLORS['text_muted'], 'margin': '0.5rem 0'},
                    'R$ 0,00 total', {'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'})

        # Toggle ON = company as mine = only participant contributions count as invested
        treat_company_as_mine = 'as_mine' in (company_as_mine or [])

        # Determine which contribution column to use
        if treat_company_as_mine and 'contrib_participante' in df_contrib_filtered.columns:
            contrib_col = 'contrib_participante'
        else:
            contrib_col = 'contribuicao_total'

        # Calculate total invested within date range
        total_invested_in_range = df_contrib_filtered[contrib_col].sum() if not df_contrib_filtered.empty else 0

        # Get period boundaries for time-weighted calculation
        period_start = date_before_start if date_before_start is not None else df_pos_filtered['data'].iloc[0]
        period_end = df_pos_filtered['data'].iloc[-1]
        end_position_original = df_pos_filtered['posicao'].iloc[-1] + position_before_start

        # Calculate time-weighted position for this period's contributions
        _, position_from_contributions = calculate_time_weighted_position(
            df_contrib_filtered,
            start_position=position_before_start,
            end_position=end_position_original,
            period_start=period_start,
            period_end=period_end,
            contribution_col=contrib_col
        )

        # Position shows only what this period's contributions became (with their returns)
        position_display = position_from_contributions

        # Total return = position from contributions minus what was invested
        total_return = position_from_contributions - total_invested_in_range

        # Calculate XIRR for the selected period
        # XIRR is calculated on this period's contributions only (matching the position display)
        from calculator import xirr_bizdays

        amounts_for_xirr = df_contrib_filtered[contrib_col].tolist() if not df_contrib_filtered.empty else []

        # Build cash flows: contributions (outflows) + what they became (inflow)
        contrib_dates = df_contrib_filtered['data'].tolist() if not df_contrib_filtered.empty else []
        contrib_amounts = [-amt for amt in amounts_for_xirr]

        # Use position_from_contributions as the final value (what contributions became)
        dates = contrib_dates + [period_end]
        amounts = contrib_amounts + [position_from_contributions]

        cagr = xirr_bizdays(dates, amounts)
        cagr_pct = cagr * 100 if cagr is not None else None

        position_text = f'R$ {position_display:,.2f}'
        invested_text = f'R$ {total_invested_in_range:,.2f}'
        cagr_text = f'{cagr_pct:+.2f}% a.a.' if cagr_pct is not None else 'N/A'
        return_text = f'R$ {total_return:,.2f} total'

        cagr_color = COLORS['accent'] if (cagr_pct or 0) >= 0 else '#ef4444'
        return_color = COLORS['accent'] if total_return >= 0 else '#ef4444'

        return (
            position_text,
            invested_text,
            cagr_text,
            {'color': cagr_color, 'margin': '0.5rem 0'},
            return_text,
            {'color': return_color, 'margin': '0', 'fontSize': '0.875rem'}
        )

    @callback(
        Output('position-graph', 'figure'),
        Output('benchmark-cagr-value', 'children'),
        Output('benchmark-cagr-value', 'style'),
        Output('benchmark-cagr-label', 'children'),
        Output('benchmark-cache', 'data'),
        Input('scale-toggle', 'value'),
        Input('start-month', 'value'),
        Input('end-month', 'value'),
        Input('benchmark-select', 'value'),
        Input('overhead-select', 'value'),
        Input('company-as-mine-toggle', 'value'),
        State('position-data', 'data'),
        State('contributions-data', 'data'),
        State('date-range-data', 'data'),
        State('benchmark-cache', 'data')
    )
    def update_position_graph(scale, start_date, end_date, benchmark_name, overhead,
                              company_as_mine, position_data, contributions_data, date_range, cache):
        # Guard for empty data
        if not position_data or not contributions_data:
            empty_fig = create_empty_figure("Carregue um PDF para visualizar")
            return (empty_fig, '--', {'color': COLORS['text_muted'], 'margin': '0.5rem 0'},
                    'Selecione um benchmark', cache or {})

        df = pd.DataFrame(position_data)
        df['data'] = pd.to_datetime(df['data'])

        df_contrib = pd.DataFrame(contributions_data)
        df_contrib['data'] = pd.to_datetime(df_contrib['data'])

        # Filter data using helper function
        df_pos_filtered, df_contrib_filtered, position_before_start, date_before_start = filter_data_by_range(
            df, df_contrib, start_date, end_date
        )

        benchmark_sim = None
        benchmark_label = None
        benchmark_cagr_text = '--'
        benchmark_cagr_style = {'color': COLORS['text_muted'], 'margin': '0.5rem 0'}
        benchmark_label_text = 'Selecione um benchmark'

        if benchmark_name and benchmark_name != 'none' and not df_contrib_filtered.empty and not df_pos_filtered.empty:
            # Check cache first
            cache_key = benchmark_name
            if cache_key in cache:
                benchmark_raw = pd.DataFrame(cache[cache_key])
            else:
                # Fetch benchmark data
                benchmark_raw = fetch_single_benchmark(
                    benchmark_name,
                    date_range['start'],
                    date_range['end']
                )
                if benchmark_raw is not None:
                    cache[cache_key] = benchmark_raw.to_dict('records')

            if benchmark_raw is not None:
                # Apply overhead
                benchmark_with_overhead = apply_overhead_to_benchmark(benchmark_raw, overhead)

                # Create label
                if overhead > 0:
                    benchmark_label = f'{benchmark_name} +{overhead}%'
                else:
                    benchmark_label = benchmark_name

                # Simulate benchmark using filtered contributions and position dates
                # Use same contribution type as Nucleos based on toggle
                treat_company_as_mine = 'as_mine' in (company_as_mine or [])
                if treat_company_as_mine and 'contrib_participante' in df_contrib_filtered.columns:
                    contrib_amounts = df_contrib_filtered['contrib_participante']
                else:
                    contrib_amounts = df_contrib_filtered['contribuicao_total']

                df_contrib_sim = df_contrib_filtered[['data']].copy()
                df_contrib_sim['contribuicao_total'] = contrib_amounts

                # Filter position dates to start from first contribution month
                # This ensures benchmark curve aligns with Nucleos (both start when contributions begin)
                if not df_contrib_sim.empty:
                    first_contrib_month = df_contrib_sim['data'].min().to_period('M')
                    position_dates_for_bench = df_pos_filtered[
                        df_pos_filtered['data'].dt.to_period('M') >= first_contrib_month
                    ][['data']].copy()
                else:
                    position_dates_for_bench = df_pos_filtered[['data']].copy()

                # Simulate benchmark - extrapolation uses historical rate from benchmark_with_overhead
                # which already includes both base index + overhead
                benchmark_sim = simulate_benchmark(
                    df_contrib_sim,
                    benchmark_with_overhead,
                    position_dates_for_bench
                )

                # Calculate benchmark value and CAGR
                if not benchmark_sim.empty:
                    # What this period's contributions became under the benchmark
                    benchmark_final_value = benchmark_sim['posicao'].iloc[-1]

                    # Keep benchmark as absolute values (consistent with Nucleos)
                    # Both show "what contributions became" at each point

                    from calculator import xirr_bizdays
                    last_date = df_pos_filtered['data'].iloc[-1]

                    # XIRR: contributions → what they became under benchmark
                    dates = df_contrib_filtered['data'].tolist() + [last_date]
                    amounts = [-amt for amt in contrib_amounts.tolist()] + [benchmark_final_value]
                    bench_cagr = xirr_bizdays(dates, amounts)

                    if bench_cagr is not None:
                        bench_cagr_pct = bench_cagr * 100
                        benchmark_cagr_text = f'{bench_cagr_pct:+.2f}% a.a.'
                        color = COLORS['accent'] if bench_cagr_pct >= 0 else '#ef4444'
                        benchmark_cagr_style = {'color': color, 'margin': '0.5rem 0'}
                    else:
                        benchmark_cagr_text = 'N/A'

                    # Display shows position value (what contributions would be worth)
                    benchmark_label_text = f'Posição {benchmark_label}: R$ {benchmark_final_value:,.2f}'

        fig = create_position_figure(
            df_pos_filtered,
            log_scale=(scale == 'log'),
            benchmark_sim=benchmark_sim,
            benchmark_label=benchmark_label
        )

        return fig, benchmark_cagr_text, benchmark_cagr_style, benchmark_label_text, cache

    @callback(
        Output('contributions-graph', 'figure'),
        Input('company-as-mine-toggle', 'value'),
        Input('start-month', 'value'),
        Input('end-month', 'value'),
        State('contributions-monthly-data', 'data'),
        State('position-data', 'data')
    )
    def update_contributions_graph(company_as_mine, start_date, end_date, monthly_data, position_data):
        # Guard for empty data
        if not monthly_data or not position_data:
            return create_empty_figure("Carregue um PDF para visualizar")

        df_monthly = pd.DataFrame(monthly_data)
        df_monthly['data'] = pd.to_datetime(df_monthly['data'])

        df_pos = pd.DataFrame(position_data)
        df_pos['data'] = pd.to_datetime(df_pos['data'])

        # Filter data using helper function
        df_pos_filtered, df_monthly_filtered, _, _ = filter_data_by_range(
            df_pos, df_monthly, start_date, end_date
        )

        # Show split when toggle is ON (company as mine = show what's yours vs theirs)
        treat_company_as_mine = 'as_mine' in (company_as_mine or [])
        show_split = treat_company_as_mine

        return create_contributions_figure(
            df_monthly_filtered, df_position=df_pos_filtered, show_split=show_split
        )

    @callback(
        Output('position-data', 'data'),
        Output('contributions-data', 'data'),
        Output('contributions-monthly-data', 'data'),
        Output('date-range-data', 'data'),
        Output('stats-data', 'data'),
        Output('month-options', 'data'),
        Output('start-month', 'options'),
        Output('start-month', 'value'),
        Output('data-loaded', 'data'),
        Input('pdf-upload', 'contents'),
        State('pdf-upload', 'filename'),
        prevent_initial_call=True
    )
    def upload_pdf(contents, filename):
        """Process uploaded PDF file."""
        if contents is None:
            raise dash.exceptions.PreventUpdate

        from extractor import extract_data_from_pdf
        from calculator import process_position_data, process_contributions_data

        # Decode the uploaded file content
        # Format: "data:application/pdf;base64,<base64-encoded-content>"
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)

        # Create a BytesIO object for pypdf to read
        pdf_file = io.BytesIO(decoded)

        # Extract data from the PDF
        df_raw, df_contributions_raw = extract_data_from_pdf(pdf_file)
        df_position = process_position_data(df_raw)
        df_contributions_monthly = process_contributions_data(df_contributions_raw)

        # Create month options
        month_options = [
            {'label': d.strftime('%b %Y'), 'value': d.isoformat()}
            for d in df_position['data']
        ]

        min_date = df_position['data'].min()

        # Calculate stats
        stats = calculate_summary_stats(df_position, df_contributions_raw, df_contributions_monthly)

        # Date range for benchmark
        start_date_str = df_contributions_raw['data'].min().strftime('%Y-%m-%d')
        end_date_str = df_position['data'].max().strftime('%Y-%m-%d')

        # Note: end-month options/value will be set by update_end_month_options callback
        # which is triggered when start-month.value changes

        return (
            df_position.to_dict('records'),
            df_contributions_raw.to_dict('records'),
            df_contributions_monthly.to_dict('records'),
            {'start': start_date_str, 'end': end_date_str},
            stats,
            month_options,
            month_options,
            min_date.isoformat(),
            True,
        )

    @callback(
        Output('pdf-upload', 'style'),
        Input('data-loaded', 'data')
    )
    def update_upload_button_style(data_loaded):
        """Update upload button color: amber when empty, primary when loaded."""
        base_style = {
            'marginLeft': '2rem',
            'padding': '0.5rem 1rem',
            'color': COLORS['text'],
            'border': 'none',
            'borderRadius': '0.5rem',
            'cursor': 'pointer',
            'display': 'inline-block'
        }
        if data_loaded:
            base_style['backgroundColor'] = COLORS['primary']
        else:
            base_style['backgroundColor'] = COLORS['sponsor']  # Amber
        return base_style

    @callback(
        Output('position-data-table', 'data'),
        Output('position-data-table', 'columns'),
        Input('start-month', 'value'),
        Input('end-month', 'value'),
        Input('benchmark-select', 'value'),
        Input('overhead-select', 'value'),
        Input('company-as-mine-toggle', 'value'),
        State('position-data', 'data'),
        State('contributions-data', 'data'),
        State('date-range-data', 'data'),
        State('benchmark-cache', 'data')
    )
    def update_position_table(start_date, end_date, benchmark_name, overhead,
                              company_as_mine, position_data, contributions_data, date_range, cache):
        """Populate position data table with Nucleos and benchmark values."""
        if not position_data or not contributions_data:
            return [], []

        df = pd.DataFrame(position_data)
        df['data'] = pd.to_datetime(df['data'])

        df_contrib = pd.DataFrame(contributions_data)
        df_contrib['data'] = pd.to_datetime(df_contrib['data'])

        # Filter data
        df_pos_filtered, df_contrib_filtered, _, _ = filter_data_by_range(
            df, df_contrib, start_date, end_date
        )

        if df_pos_filtered.empty:
            return [], []

        # Build table data
        table_data = []
        for _, row in df_pos_filtered.iterrows():
            table_data.append({
                'data': row['data'].strftime('%b %Y'),
                'posicao': f"R$ {row['posicao']:,.2f}"
            })

        # Base columns
        columns = [
            {'name': 'Data', 'id': 'data'},
            {'name': 'Posição (Nucleos)', 'id': 'posicao'},
        ]

        # Add benchmark columns if benchmark selected
        if benchmark_name and benchmark_name != 'none' and not df_contrib_filtered.empty and date_range:
            cache = cache or {}
            cache_key = benchmark_name
            if cache_key in cache:
                benchmark_raw = pd.DataFrame(cache[cache_key])
            else:
                benchmark_raw = fetch_single_benchmark(
                    benchmark_name,
                    date_range['start'],
                    date_range['end']
                )

            if benchmark_raw is not None:
                # Prepare contributions for simulation
                treat_company_as_mine = 'as_mine' in (company_as_mine or [])
                if treat_company_as_mine and 'contrib_participante' in df_contrib_filtered.columns:
                    contrib_amounts = df_contrib_filtered['contrib_participante']
                else:
                    contrib_amounts = df_contrib_filtered['contribuicao_total']

                df_contrib_sim = df_contrib_filtered[['data']].copy()
                df_contrib_sim['contribuicao_total'] = contrib_amounts

                # Position dates for benchmark
                if not df_contrib_sim.empty:
                    first_contrib_month = df_contrib_sim['data'].min().to_period('M')
                    position_dates_for_bench = df_pos_filtered[
                        df_pos_filtered['data'].dt.to_period('M') >= first_contrib_month
                    ][['data']].copy()
                else:
                    position_dates_for_bench = df_pos_filtered[['data']].copy()

                # Simulate benchmark WITHOUT overhead
                benchmark_sim_raw = simulate_benchmark(
                    df_contrib_sim,
                    benchmark_raw,
                    position_dates_for_bench
                )

                # Simulate benchmark WITH overhead
                benchmark_with_overhead = apply_overhead_to_benchmark(benchmark_raw, overhead)
                benchmark_sim_overhead = simulate_benchmark(
                    df_contrib_sim,
                    benchmark_with_overhead,
                    position_dates_for_bench
                )

                # Add benchmark data to table
                bench_raw_dict = {row['data'].strftime('%b %Y'): row['posicao']
                                 for _, row in benchmark_sim_raw.iterrows()} if not benchmark_sim_raw.empty else {}
                bench_overhead_dict = {row['data'].strftime('%b %Y'): row['posicao']
                                       for _, row in benchmark_sim_overhead.iterrows()} if not benchmark_sim_overhead.empty else {}

                # Raw index values (normalized)
                benchmark_raw['date'] = pd.to_datetime(benchmark_raw['date'])
                index_raw_dict = {row['date'].strftime('%b %Y'): row['value']
                                  for _, row in benchmark_raw.iterrows()}
                benchmark_with_overhead['date'] = pd.to_datetime(benchmark_with_overhead['date'])
                index_overhead_dict = {row['date'].strftime('%b %Y'): row['value']
                                       for _, row in benchmark_with_overhead.iterrows()}

                for row in table_data:
                    date_key = row['data']
                    if date_key in bench_overhead_dict:
                        row['bench_overhead'] = f"R$ {bench_overhead_dict[date_key]:,.2f}"
                    else:
                        row['bench_overhead'] = '-'
                    if date_key in bench_raw_dict:
                        row['bench_raw'] = f"R$ {bench_raw_dict[date_key]:,.2f}"
                    else:
                        row['bench_raw'] = '-'
                    if date_key in index_overhead_dict:
                        row['index_overhead'] = f"{index_overhead_dict[date_key]:.4f}"
                    else:
                        row['index_overhead'] = '-'
                    if date_key in index_raw_dict:
                        row['index_raw'] = f"{index_raw_dict[date_key]:.4f}"
                    else:
                        row['index_raw'] = '-'

                # Add benchmark columns
                overhead_label = f'{benchmark_name} +{overhead}%' if overhead > 0 else benchmark_name
                columns.append({'name': f'{overhead_label} (simulado)', 'id': 'bench_overhead'})
                columns.append({'name': f'{benchmark_name} (simulado)', 'id': 'bench_raw'})
                columns.append({'name': f'{overhead_label} (índice)', 'id': 'index_overhead'})
                columns.append({'name': f'{benchmark_name} (índice)', 'id': 'index_raw'})

        return table_data, columns

    @callback(
        Output('position-download', 'data'),
        Input('position-export-btn', 'n_clicks'),
        State('position-data-table', 'data'),
        State('position-export-format', 'value'),
        prevent_initial_call=True
    )
    def export_position_data(n_clicks, table_data, export_format):
        """Export position table data to CSV or Excel."""
        if not table_data:
            raise dash.exceptions.PreventUpdate

        df = pd.DataFrame(table_data)

        if export_format == 'csv':
            return dcc.send_data_frame(df.to_csv, 'nucleos_posicao.csv', index=False)
        else:
            return dcc.send_data_frame(df.to_excel, 'nucleos_posicao.xlsx', index=False, engine='openpyxl')

    @callback(
        Output('contributions-data-table', 'data'),
        Output('contributions-data-table', 'columns'),
        Input('start-month', 'value'),
        Input('end-month', 'value'),
        Input('company-as-mine-toggle', 'value'),
        State('contributions-monthly-data', 'data'),
        State('position-data', 'data')
    )
    def update_contributions_table(start_date, end_date, company_as_mine,
                                   monthly_data, position_data):
        """Populate contributions data table."""
        if not monthly_data:
            return [], []

        df_monthly = pd.DataFrame(monthly_data)
        df_monthly['data'] = pd.to_datetime(df_monthly['data'])

        if position_data:
            df_pos = pd.DataFrame(position_data)
            df_pos['data'] = pd.to_datetime(df_pos['data'])
        else:
            df_pos = pd.DataFrame()

        # Filter by date range
        start_dt = pd.to_datetime(start_date) if start_date else None
        end_dt = pd.to_datetime(end_date) if end_date else None

        if start_dt:
            df_monthly = df_monthly[df_monthly['data'] >= start_dt]
        if end_dt:
            df_monthly = df_monthly[df_monthly['data'] <= end_dt]

        if df_monthly.empty:
            return [], []

        # Calculate cumulative invested
        show_split = 'as_mine' in (company_as_mine or [])
        if show_split:
            df_monthly['total_investido'] = df_monthly['contrib_participante'].cumsum()
        else:
            df_monthly['total_investido'] = df_monthly['contribuicao_total'].cumsum()

        # Build table data
        table_data = []
        for _, row in df_monthly.iterrows():
            row_data = {
                'data': row['data'].strftime('%b %Y'),
                'contrib_total': f"R$ {row['contribuicao_total']:,.2f}",
                'total_investido': f"R$ {row['total_investido']:,.2f}",
            }
            if show_split:
                row_data['contrib_participante'] = f"R$ {row['contrib_participante']:,.2f}"
                row_data['contrib_patrocinador'] = f"R$ {row['contrib_patrocinador']:,.2f}"

            # Add position if available
            if not df_pos.empty:
                pos_row = df_pos[df_pos['data'] == row['data']]
                if not pos_row.empty:
                    row_data['posicao'] = f"R$ {pos_row['posicao'].iloc[0]:,.2f}"
                else:
                    row_data['posicao'] = '-'
            table_data.append(row_data)

        # Build columns dynamically
        columns = [{'name': 'Data', 'id': 'data'}]
        if show_split:
            columns.append({'name': 'Contrib. Participante', 'id': 'contrib_participante'})
            columns.append({'name': 'Contrib. Patrocinador', 'id': 'contrib_patrocinador'})
        columns.append({'name': 'Contrib. Total', 'id': 'contrib_total'})
        columns.append({'name': 'Total Investido', 'id': 'total_investido'})
        if not df_pos.empty:
            columns.append({'name': 'Posição', 'id': 'posicao'})

        return table_data, columns

    @callback(
        Output('contributions-download', 'data'),
        Input('contributions-export-btn', 'n_clicks'),
        State('contributions-data-table', 'data'),
        State('contributions-export-format', 'value'),
        prevent_initial_call=True
    )
    def export_contributions_data(n_clicks, table_data, export_format):
        """Export contributions table data to CSV or Excel."""
        if not table_data:
            raise dash.exceptions.PreventUpdate

        df = pd.DataFrame(table_data)

        if export_format == 'csv':
            return dcc.send_data_frame(df.to_csv, 'nucleos_contribuicoes.csv', index=False)
        else:
            return dcc.send_data_frame(df.to_excel, 'nucleos_contribuicoes.xlsx', index=False, engine='openpyxl')

    return app
