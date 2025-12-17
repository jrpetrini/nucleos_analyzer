#!/usr/bin/env python3
"""
Chart/figure creation functions for Nucleos Analyzer dashboard.
"""

import pandas as pd
import plotly.graph_objects as go

from components import COLORS, BENCHMARK_COLORS


def create_position_figure(df_position: pd.DataFrame, log_scale: bool = False,
                           benchmark_sim: pd.DataFrame = None,
                           benchmark_label: str = None) -> go.Figure:
    """Create the position line chart with optional benchmark comparison.

    Args:
        df_position: Pre-filtered position data with adjusted values
        benchmark_sim: Pre-filtered benchmark simulation data
        benchmark_label: Label for the benchmark curve
        log_scale: Whether to use logarithmic Y-axis

    Returns:
        Plotly Figure object
    """
    fig = go.Figure()

    # Shift dates to mid-month (15th) to avoid UTC timezone rollover issues
    if not df_position.empty:
        df_position = df_position.copy()
        df_position['data'] = df_position['data'].apply(lambda d: d.replace(day=15))
    if benchmark_sim is not None and not benchmark_sim.empty:
        benchmark_sim = benchmark_sim.copy()
        benchmark_sim['data'] = benchmark_sim['data'].apply(lambda d: d.replace(day=15))

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
            line=dict(color=color, width=2),
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
            title=dict(text='Mês Fechamento', font=dict(color=COLORS['text'])),
            gridcolor=COLORS['grid'],
            tickfont=dict(color=COLORS['text_muted']),
            tickformat='%b %Y',
            ticklabelmode='period'
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
                                 show_split: bool = False,
                                 is_partial: bool = False) -> go.Figure:
    """Create the contributions bar chart with position and invested curves.

    Args:
        df_contributions: Pre-filtered monthly contribution data
        df_position: Pre-filtered and adjusted position data
        show_split: Whether to show participant/sponsor split

    Returns:
        Plotly Figure object
    """
    fig = go.Figure()

    # Shift dates to mid-month (15th) to avoid UTC timezone rollover issues
    # (e.g., Dec 31 local → Jan 1 UTC in hover)
    df_contributions = df_contributions.copy()
    df_contributions['data'] = df_contributions['data'].apply(lambda d: d.replace(day=15))
    if df_position is not None and not df_position.empty:
        df_position = df_position.copy()
        df_position['data'] = df_position['data'].apply(lambda d: d.replace(day=15))

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
    # When show_split is ON, "Total Investido" shows only participant contributions
    if show_split and 'contrib_participante' in df_contributions.columns:
        invested_cumsum = df_contributions['contrib_participante'].cumsum()
        invested_label = 'Total Investido (Participante)'
    else:
        invested_cumsum = df_contributions['contribuicao_total'].cumsum()
        invested_label = 'Total Investido'

    fig.add_trace(go.Scatter(
        x=df_contributions['data'],
        y=invested_cumsum,
        mode='lines+markers',
        name=invested_label,
        line=dict(color=COLORS['accent'], width=3),
        marker=dict(size=6),
        yaxis='y2',
        hovertemplate='<b>%{x|%b %Y}</b><br>' + invested_label + ': R$ %{y:,.2f}<extra></extra>'
    ))

    # When show_split is ON, add a separate curve for total contributions
    if show_split and 'contrib_participante' in df_contributions.columns:
        total_cumsum = df_contributions['contribuicao_total'].cumsum()
        fig.add_trace(go.Scatter(
            x=df_contributions['data'],
            y=total_cumsum,
            mode='lines+markers',
            name='Contribuição Total',
            line=dict(color=COLORS['sponsor'], width=2),
            marker=dict(size=5),
            yaxis='y2',
            hovertemplate='<b>%{x|%b %Y}</b><br>Contribuição Total: R$ %{y:,.2f}<extra></extra>'
        ))

    # Add position curve (already adjusted relative to start of range)
    if df_position is not None and not df_position.empty:
        # For partial PDFs, this shows only the visible portion (delta)
        position_label = 'ΔNucleos' if is_partial else 'Nucleos'
        fig.add_trace(go.Scatter(
            x=df_position['data'],
            y=df_position['posicao'],
            mode='lines+markers',
            name=position_label,
            line=dict(color=COLORS['primary'], width=3),
            marker=dict(size=6),
            yaxis='y2',
            hovertemplate=f'<b>%{{x|%b %Y}}</b><br>{position_label}: R$ %{{y:,.2f}}<extra></extra>'
        ))

    fig.update_layout(
        title=dict(
            text='Contribuições Mensais',
            font=dict(size=24, color=COLORS['text']),
            x=0.5
        ),
        xaxis=dict(
            title=dict(text='Mês Fechamento', font=dict(color=COLORS['text'])),
            gridcolor=COLORS['grid'],
            tickfont=dict(color=COLORS['text_muted']),
            tickformat='%b %Y',
            ticklabelmode='period'
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
    """Create an empty placeholder figure with a message.

    Args:
        message: Message to display in the empty figure

    Returns:
        Plotly Figure object
    """
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
