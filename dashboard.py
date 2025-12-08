#!/usr/bin/env python3
"""
Dashboard UI components for Nucleos Analyzer.
"""

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, callback, Output, Input, State

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


def create_position_figure(df_position: pd.DataFrame, log_scale: bool = False,
                           date_range: tuple = None,
                           benchmark_sim: pd.DataFrame = None,
                           benchmark_label: str = None) -> go.Figure:
    """Create the position line chart with optional benchmark comparison."""
    df = df_position.copy()

    if date_range and date_range[0] and date_range[1]:
        df = df[(df['data'] >= date_range[0]) & (df['data'] <= date_range[1])]

    fig = go.Figure()

    # Main position line
    fig.add_trace(go.Scatter(
        x=df['data'],
        y=df['posicao'],
        mode='lines+markers',
        name='Nucleos',
        line=dict(color=COLORS['primary'], width=3),
        marker=dict(size=8, color=COLORS['primary']),
        hovertemplate='<b>%{x|%b %Y}</b><br>Nucleos: R$ %{y:,.2f}<extra></extra>'
    ))

    # Add benchmark curve if available
    if benchmark_sim is not None and not benchmark_sim.empty and benchmark_label:
        bench_df = benchmark_sim.copy()
        bench_df['data'] = pd.to_datetime(bench_df['data'])

        if date_range and date_range[0] and date_range[1]:
            bench_df = bench_df[
                (bench_df['data'] >= date_range[0]) &
                (bench_df['data'] <= date_range[1])
            ]

        # Get base benchmark name for color
        base_name = benchmark_label.split('+')[0].strip()
        color = BENCHMARK_COLORS.get(base_name, '#888888')

        fig.add_trace(go.Scatter(
            x=bench_df['data'],
            y=bench_df['posicao'],
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


def create_contributions_figure(df_contributions: pd.DataFrame) -> go.Figure:
    """Create the contributions bar chart."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_contributions['data'],
        y=df_contributions['contribuicao_total'],
        name='Contribuição Mensal',
        marker_color=COLORS['participant'],
        hovertemplate='<b>%{x|%b %Y}</b><br>Contribuição: R$ %{y:,.2f}<extra></extra>'
    ))

    # Add cumulative line
    fig.add_trace(go.Scatter(
        x=df_contributions['data'],
        y=df_contributions['contribuicao_acumulada'],
        mode='lines+markers',
        name='Total Acumulado',
        line=dict(color=COLORS['accent'], width=3),
        marker=dict(size=6),
        yaxis='y2',
        hovertemplate='<b>%{x|%b %Y}</b><br>Acumulado: R$ %{y:,.2f}<extra></extra>'
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
            title=dict(text='Total Acumulado (R$)', font=dict(color=COLORS['accent'])),
            overlaying='y',
            side='right',
            tickfont=dict(color=COLORS['accent']),
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


def create_app(df_position: pd.DataFrame,
               df_contributions_raw: pd.DataFrame,
               df_contributions_monthly: pd.DataFrame) -> Dash:
    """
    Create the Dash application.

    Args:
        df_position: Processed position data
        df_contributions_raw: Raw contributions with exact dates (for XIRR)
        df_contributions_monthly: Monthly aggregated contributions (for charts)

    Returns:
        Configured Dash application
    """
    app = Dash(__name__, suppress_callback_exceptions=True)

    min_date = df_position['data'].min()
    max_date = df_position['data'].max()

    # Create month options for dropdowns
    month_options = [
        {'label': d.strftime('%b %Y'), 'value': d.isoformat()}
        for d in df_position['data']
    ]

    # Benchmark options
    benchmark_options = [{'label': 'Nenhum', 'value': 'none'}] + [
        {'label': name, 'value': name} for name in AVAILABLE_BENCHMARKS
    ]

    # Calculate summary stats
    stats = calculate_summary_stats(df_position, df_contributions_raw, df_contributions_monthly)

    # Pre-create figures
    initial_position_fig = create_position_figure(df_position, log_scale=False)
    contributions_fig = create_contributions_figure(df_contributions_monthly)

    # Date range for benchmark fetching
    start_date_str = df_contributions_raw['data'].min().strftime('%Y-%m-%d')
    end_date_str = df_position['data'].max().strftime('%Y-%m-%d')

    app.layout = html.Div([
        # Header
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
        ], style={
            'textAlign': 'center',
            'padding': '2rem',
            'backgroundColor': COLORS['background']
        }),

        # Summary Cards
        html.Div([
            html.Div([
                html.P('Posição Atual', style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'}),
                html.H2(f'R$ {stats["last_position"]:,.2f}', style={'color': COLORS['primary'], 'margin': '0.5rem 0'})
            ], style={
                'backgroundColor': COLORS['card'],
                'padding': '1.5rem',
                'borderRadius': '0.75rem',
                'flex': '1',
                'textAlign': 'center'
            }),
            html.Div([
                html.P('Total Investido', style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'}),
                html.H2(f'R$ {stats["total_contributed"]:,.2f}', style={'color': COLORS['participant'], 'margin': '0.5rem 0'})
            ], style={
                'backgroundColor': COLORS['card'],
                'padding': '1.5rem',
                'borderRadius': '0.75rem',
                'flex': '1',
                'textAlign': 'center'
            }),
            html.Div([
                html.P('Rendimento Nucleos (CAGR)', style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'}),
                html.H2(f'{stats["cagr_pct"]:+.2f}% a.a.' if stats["cagr_pct"] is not None else 'N/A', style={
                    'color': COLORS['accent'] if (stats["cagr_pct"] or 0) >= 0 else '#ef4444',
                    'margin': '0.5rem 0'
                }),
                html.P(f'R$ {stats["total_return"]:,.2f} total', style={
                    'color': COLORS['accent'] if stats["total_return"] >= 0 else '#ef4444',
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
            # Benchmark CAGR card
            html.Div(id='benchmark-cagr-card', children=[
                html.P('Rendimento Benchmark', style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'}),
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
                html.Div([
                    html.Label('De:', style={'color': COLORS['text'], 'marginRight': '0.5rem'}),
                    dcc.Dropdown(
                        id='start-month',
                        options=month_options,
                        value=min_date.isoformat(),
                        clearable=False,
                        style={'width': '130px', 'color': '#000'}
                    ),
                    html.Label('Até:', style={'color': COLORS['text'], 'margin': '0 0.5rem 0 1rem'}),
                    dcc.Dropdown(
                        id='end-month',
                        options=month_options,
                        value=max_date.isoformat(),
                        clearable=False,
                        style={'width': '130px', 'color': '#000'}
                    )
                ], style={'display': 'flex', 'alignItems': 'center'})
            ], style={
                'display': 'flex',
                'justifyContent': 'space-between',
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
                html.Label('Overhead:', style={'color': COLORS['text'], 'margin': '0 0.5rem 0 1rem'}),
                dcc.Dropdown(
                    id='overhead-select',
                    options=OVERHEAD_OPTIONS,
                    value=4,  # Default to +4%
                    clearable=False,
                    style={'width': '100px', 'color': '#000'}
                ),
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
            )
        ], style={
            'padding': '2rem',
            'backgroundColor': COLORS['background'],
            'minHeight': '600px',
            'display': 'block'
        }),

        # Contributions Tab Content
        html.Div(id='contributions-tab', children=[
            dcc.Graph(id='contributions-graph', figure=contributions_fig, style={'height': '500px'})
        ], style={
            'padding': '2rem',
            'backgroundColor': COLORS['background'],
            'minHeight': '600px',
            'display': 'none'
        }),

        # Store data for callbacks
        dcc.Store(id='position-data', data=df_position.to_dict('records')),
        dcc.Store(id='contributions-data', data=df_contributions_raw.to_dict('records')),
        dcc.Store(id='date-range-data', data={'start': start_date_str, 'end': end_date_str}),
        dcc.Store(id='benchmark-cache', data={}),  # Cache fetched benchmark data

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
        State('position-data', 'data'),
        State('contributions-data', 'data'),
        State('date-range-data', 'data'),
        State('benchmark-cache', 'data')
    )
    def update_position_graph(scale, start_date, end_date, benchmark_name, overhead,
                              position_data, contributions_data, date_range, cache):
        df = pd.DataFrame(position_data)
        df['data'] = pd.to_datetime(df['data'])

        df_contrib = pd.DataFrame(contributions_data)
        df_contrib['data'] = pd.to_datetime(df_contrib['data'])

        benchmark_sim = None
        benchmark_label = None
        benchmark_cagr_text = '--'
        benchmark_cagr_style = {'color': COLORS['text_muted'], 'margin': '0.5rem 0'}
        benchmark_label_text = 'Selecione um benchmark'

        if benchmark_name and benchmark_name != 'none':
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

                # Simulate benchmark
                benchmark_sim = simulate_benchmark(
                    df_contrib,
                    benchmark_with_overhead,
                    df[['data']]
                )

                # Calculate benchmark CAGR (simple: final / initial - expressed as return)
                if not benchmark_sim.empty and len(benchmark_sim) > 1:
                    final_value = benchmark_sim['posicao'].iloc[-1]
                    total_contrib = df_contrib['contribuicao_total'].sum()
                    bench_return = final_value - total_contrib

                    # For CAGR we need XIRR-like calculation
                    from calculator import xirr_bizdays
                    last_date = df['data'].iloc[-1]
                    dates = df_contrib['data'].tolist() + [last_date]
                    amounts = [-amt for amt in df_contrib['contribuicao_total'].tolist()] + [final_value]
                    bench_cagr = xirr_bizdays(dates, amounts)

                    if bench_cagr is not None:
                        bench_cagr_pct = bench_cagr * 100
                        benchmark_cagr_text = f'{bench_cagr_pct:+.2f}% a.a.'
                        color = COLORS['accent'] if bench_cagr_pct >= 0 else '#ef4444'
                        benchmark_cagr_style = {'color': color, 'margin': '0.5rem 0'}
                    else:
                        benchmark_cagr_text = 'N/A'

                    benchmark_label_text = f'{benchmark_label}: R$ {final_value:,.2f}'

        fig = create_position_figure(
            df,
            log_scale=(scale == 'log'),
            date_range=(start_date, end_date),
            benchmark_sim=benchmark_sim,
            benchmark_label=benchmark_label
        )

        return fig, benchmark_cagr_text, benchmark_cagr_style, benchmark_label_text, cache

    return app
