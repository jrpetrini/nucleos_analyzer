#!/usr/bin/env python3
"""
Nucleos Analyzer Dashboard - Interactive visualization of pension fund data.
"""

import re
import subprocess
import sys

import pandas as pd
import pypdf
import plotly.graph_objects as go
from dash import Dash, dcc, html, callback, Output, Input
from pyxirr import xirr
from bizdays import Calendar
from scipy.optimize import brentq

# Load Brazilian ANBIMA calendar for business day calculations
ANBIMA_CAL = Calendar.load('ANBIMA')


def xirr_bizdays(dates: list, amounts: list, cal: Calendar = ANBIMA_CAL) -> float | None:
    """
    Calculate XIRR using Brazilian business days (252 days/year).

    This provides a more accurate annualized return for Brazilian investments
    where returns are typically quoted in "dias úteis" (business days).

    Args:
        dates: List of dates for each cash flow
        amounts: List of amounts (negative = outflow, positive = inflow)
        cal: Business day calendar (default: ANBIMA)

    Returns:
        Annualized return rate based on 252 business days, or None if no solution
    """
    if len(dates) != len(amounts) or len(dates) < 2:
        return None

    # Convert dates to date objects if needed
    dates = [pd.Timestamp(d).date() for d in dates]
    first_date = min(dates)

    # Calculate business days from first date to each cash flow date
    biz_days = []
    for d in dates:
        if d == first_date:
            biz_days.append(0)
        else:
            biz_days.append(cal.bizdays(first_date, d))

    def npv(rate):
        """Calculate NPV using business days / 252."""
        if rate <= -1:
            return float('inf')
        total = 0
        for amt, days in zip(amounts, biz_days):
            total += amt / ((1 + rate) ** (days / 252))
        return total

    # Use brentq with bracket [-0.99, 10] (i.e., -99% to 1000% annual return)
    # Guaranteed convergence within bracket
    try:
        rate = brentq(npv, -0.99, 10, xtol=1e-10)
        return rate
    except ValueError:
        # No solution in bracket, try standard xirr as fallback
        try:
            return xirr(dates, amounts)
        except Exception:
            return None


# Try to import tkinter for file dialog
try:
    import tkinter as tk
    from tkinter import filedialog
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


def select_pdf_file_tkinter() -> str | None:
    """Opens a tkinter file dialog to select the PDF file."""
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Selecione o arquivo extratoIndividual.pdf",
        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
    )
    root.destroy()
    return file_path if file_path else None


def select_pdf_file_zenity() -> str | None:
    """Opens a zenity file dialog to select the PDF file."""
    try:
        result = subprocess.run(
            ["zenity", "--file-selection",
             "--title=Selecione o arquivo extratoIndividual.pdf",
             "--file-filter=PDF files | *.pdf"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def select_pdf_file() -> str | None:
    """Opens a file dialog to select the PDF file."""
    if HAS_TKINTER:
        try:
            return select_pdf_file_tkinter()
        except Exception:
            pass
    file_path = select_pdf_file_zenity()
    if file_path:
        return file_path
    print("GUI não disponível. Digite o caminho do arquivo:")
    return input("> ").strip() or None


def extract_data_from_pdf(file_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extracts data from Nucleos PDF statement.

    Returns:
        Tuple of (raw_df, contributions_df)
    """
    reader = pypdf.PdfReader(file_path)
    row_map = {}
    contributions_list = []
    pat_date_month = re.compile(r'\d{2}/\d{4}')
    pat_date_full = re.compile(r'(\d{2}/\d{2}/\d{4})$')  # DD/MM/YYYY at end of line

    for page_num, page in enumerate(reader.pages, start=1):
        page_text_raw = page.extract_text()
        rows = page_text_raw.split('\n')
        rows = [row for row in rows if ('CONTRIB' in row) or ('TAXA' in row)]

        for row_num, row in enumerate(rows):
            row_split = row.split(" ")

            # Extract exact date (DD/MM/YYYY) from end of row
            full_date_match = pat_date_full.search(row)
            if full_date_match:
                data_exata = pd.to_datetime(full_date_match.group(1), format='%d/%m/%Y')
            else:
                # Fallback to month/year
                date_match = pat_date_month.findall(row)
                if not date_match:
                    continue
                data_exata = pd.to_datetime(date_match[0].strip(), format='%m/%Y')

            # Extract month/year for grouping position data
            date_match = pat_date_month.findall(row)
            if not date_match:
                continue
            mes_ano = pd.to_datetime(date_match[0].strip(), format='%m/%Y')

            quotas = float(row_split[-1][:-8].replace('.', '').replace(',', '.'))
            val_quota = float(row_split[-2].replace('.', '').replace(',', '.'))

            # Determine transaction type
            is_contribution = 'CONTRIB' in row and quotas > 0
            is_participant = 'PARTICIPANTE' in row

            row_map[f'{page_num}-{row_num}'] = {
                'mes_ano': mes_ano,
                'valor_cota': val_quota,
                'cotas': quotas
            }

            # Track actual contributions with exact dates
            if is_contribution:
                valor_contribuido = quotas * val_quota
                contributions_list.append({
                    'data_exata': data_exata,
                    'mes_ano': mes_ano,
                    'tipo': 'participante' if is_participant else 'patrocinador',
                    'valor': valor_contribuido
                })

    df_raw = pd.DataFrame.from_dict(row_map, orient='index')

    # Build contributions dataframe with exact dates
    if contributions_list:
        df_contrib_raw = pd.DataFrame(contributions_list)
        # Group by exact date and aggregate
        df_contributions = df_contrib_raw.groupby('data_exata').agg({
            'mes_ano': 'first',
            'valor': 'sum'
        }).reset_index()
        df_contributions = df_contributions.rename(columns={'valor': 'contribuicao_total', 'data_exata': 'data'})
        df_contributions = df_contributions.sort_values('data').reset_index(drop=True)
        df_contributions['contribuicao_acumulada'] = df_contributions['contribuicao_total'].cumsum()
    else:
        df_contributions = pd.DataFrame()

    return df_raw, df_contributions


def process_position_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Process raw data to get monthly positions."""
    df = df_raw.copy(deep=True)
    df['cotas_cumsum'] = df['cotas'].cumsum()
    df['posicao'] = df['cotas_cumsum'] * df['valor_cota']

    df = (
        df.groupby('mes_ano')
        .last()[['cotas_cumsum', 'posicao', 'valor_cota']]
        .rename(columns={'cotas_cumsum': 'cotas'})
    )
    df.index = df.index.to_period('M').to_timestamp(how='end')
    df = df.reset_index().rename(columns={'mes_ano': 'data'})

    return df


def process_contributions_data(df_contributions: pd.DataFrame) -> pd.DataFrame:
    """Process contributions data for bar chart (aggregated by month)."""
    if df_contributions.empty:
        return df_contributions

    df = df_contributions.copy()
    # Aggregate by month for chart display
    df['mes'] = df['data'].dt.to_period('M').dt.to_timestamp(how='end')
    df_monthly = df.groupby('mes').agg({
        'contribuicao_total': 'sum'
    }).reset_index()
    df_monthly = df_monthly.rename(columns={'mes': 'data'})
    df_monthly['contribuicao_acumulada'] = df_monthly['contribuicao_total'].cumsum()

    return df_monthly


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


def create_position_figure(df_position: pd.DataFrame, log_scale: bool = True,
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


def create_app(df_position: pd.DataFrame, df_contributions_raw: pd.DataFrame, df_contributions_monthly: pd.DataFrame) -> Dash:
    """Create the Dash application."""
    app = Dash(__name__, suppress_callback_exceptions=True)

    min_date = df_position['data'].min()
    max_date = df_position['data'].max()

    # Create month options for dropdowns
    month_options = [
        {'label': d.strftime('%b %Y'), 'value': d.isoformat()}
        for d in df_position['data']
    ]

    # Summary stats
    last_position = df_position['posicao'].iloc[-1]
    last_date = df_position['data'].iloc[-1]
    total_contributed = df_contributions_monthly['contribuicao_acumulada'].iloc[-1] if not df_contributions_monthly.empty else 0
    total_return = last_position - total_contributed
    return_pct = (total_return / total_contributed * 100) if total_contributed > 0 else 0

    # Calculate XIRR (CAGR) using exact dates and Brazilian business days
    # Cash flows: contributions are negative (money out), final position is positive (money in)
    if not df_contributions_raw.empty:
        dates = df_contributions_raw['data'].tolist() + [last_date]
        amounts = [-amt for amt in df_contributions_raw['contribuicao_total'].tolist()] + [last_position]
        cagr = xirr_bizdays(dates, amounts)
        cagr_pct = cagr * 100 if cagr is not None else None
    else:
        cagr_pct = None

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
                html.H2(f'R$ {last_position:,.2f}', style={'color': COLORS['primary'], 'margin': '0.5rem 0'})
            ], style={
                'backgroundColor': COLORS['card'],
                'padding': '1.5rem',
                'borderRadius': '0.75rem',
                'flex': '1',
                'textAlign': 'center'
            }),
            html.Div([
                html.P('Total Investido', style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'}),
                html.H2(f'R$ {total_contributed:,.2f}', style={'color': COLORS['participant'], 'margin': '0.5rem 0'})
            ], style={
                'backgroundColor': COLORS['card'],
                'padding': '1.5rem',
                'borderRadius': '0.75rem',
                'flex': '1',
                'textAlign': 'center'
            }),
            html.Div([
                html.P('Rendimento (CAGR)', style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'}),
                html.H2(f'{cagr_pct:+.2f}% a.a.' if cagr_pct is not None else 'N/A', style={
                    'color': COLORS['accent'] if (cagr_pct or 0) >= 0 else '#ef4444',
                    'margin': '0.5rem 0'
                }),
                html.P(f'R$ {total_return:,.2f} total', style={
                    'color': COLORS['accent'] if total_return >= 0 else '#ef4444',
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


def main():
    """Main entry point."""
    print("Nucleos Analyzer Dashboard")
    print("=" * 40)

    # Get file path
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = select_pdf_file()

    if not file_path:
        print("Nenhum arquivo selecionado. Encerrando.")
        sys.exit(0)

    print(f"Carregando: {file_path}")

    # Extract and process data
    df_raw, df_contributions_raw = extract_data_from_pdf(file_path)
    df_position = process_position_data(df_raw)
    df_contributions_monthly = process_contributions_data(df_contributions_raw)

    print(f"Registros processados: {len(df_raw)}")
    print()
    print("Iniciando dashboard em http://127.0.0.1:8050")
    print("Pressione Ctrl+C para encerrar")
    print()

    # Create and run app
    app = create_app(df_position, df_contributions_raw, df_contributions_monthly)
    app.run(debug=False)


if __name__ == "__main__":
    main()
