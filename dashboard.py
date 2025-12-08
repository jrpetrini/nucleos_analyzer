#!/usr/bin/env python3
"""
Dashboard UI components for Nucleos Analyzer.
"""

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, callback, Output, Input

from calculator import calculate_summary_stats

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


def create_position_figure(df_position: pd.DataFrame, log_scale: bool = False,
                           date_range: tuple = None) -> go.Figure:
    """Create the position line chart."""
    df = df_position.copy()

    if date_range and date_range[0] and date_range[1]:
        df = df[(df['data'] >= date_range[0]) & (df['data'] <= date_range[1])]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['data'],
        y=df['posicao'],
        mode='lines+markers',
        name='Posição',
        line=dict(color=COLORS['primary'], width=3),
        marker=dict(size=8, color=COLORS['primary']),
        hovertemplate='<b>%{x|%b %Y}</b><br>Posição: R$ %{y:,.2f}<extra></extra>'
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

    # Calculate summary stats
    stats = calculate_summary_stats(df_position, df_contributions_raw, df_contributions_monthly)

    # Pre-create figures
    initial_position_fig = create_position_figure(df_position, log_scale=False)
    contributions_fig = create_contributions_figure(df_contributions_monthly)

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
                html.P('Rendimento (CAGR)', style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'}),
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
            # Controls
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
            # Graph
            dcc.Graph(id='position-graph', figure=initial_position_fig, style={'height': '500px'})
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
        Input('scale-toggle', 'value'),
        Input('start-month', 'value'),
        Input('end-month', 'value'),
        Input('position-data', 'data')
    )
    def update_position_graph(scale, start_date, end_date, data):
        df = pd.DataFrame(data)
        df['data'] = pd.to_datetime(df['data'])
        return create_position_figure(
            df,
            log_scale=(scale == 'log'),
            date_range=(start_date, end_date)
        )

    return app
