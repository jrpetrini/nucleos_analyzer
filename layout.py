#!/usr/bin/env python3
"""
Page layout assembly for Nucleos Analyzer dashboard.
"""

import pandas as pd
from dash import dcc, html, dash_table

from components import (
    COLORS, OVERHEAD_OPTIONS, FORECAST_OPTIONS, GROWTH_RATE_OPTIONS, DEFAULT_GROWTH_RATE,
    HELP_TEXTS, create_help_icon, create_data_table_styles, create_tab_style
)
from figures import create_position_figure, create_contributions_figure, create_empty_figure
from calculator import calculate_summary_stats
from benchmarks import AVAILABLE_BENCHMARKS


def create_header() -> html.Div:
    """Create the page header with title and GitHub link."""
    return html.Div([
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
    })


def create_global_toggles(month_options: list, max_date) -> html.Div:
    """Create the global toggle controls (company as mine, inflation)."""
    return html.Div([
        # Company contributions toggle
        html.Div([
            html.Div([
                dcc.Checklist(
                    id='company-as-mine-toggle',
                    options=[{'label': ' Considerar contribuições da empresa como sem custo', 'value': 'as_mine'}],
                    value=[],
                    style={'color': COLORS['text']},
                    labelStyle={'display': 'flex', 'alignItems': 'center'}
                ),
                create_help_icon(HELP_TEXTS['company_as_mine'], 'help-company-toggle'),
            ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'})
        ], style={
            'padding': '0 2rem 1rem 2rem',
            'backgroundColor': COLORS['background']
        }),

        # Inflation adjustment controls
        html.Div([
            dcc.Loading(
                id='loading-inflation',
                type='circle',
                color=COLORS['primary'],
                children=[
                    html.Div([
                        dcc.Checklist(
                            id='inflation-toggle',
                            options=[{'label': ' Ajustar pela inflação', 'value': 'adjust'}],
                            value=[],
                            style={'color': COLORS['text']},
                            labelStyle={'display': 'flex', 'alignItems': 'center'}
                        ),
                        create_help_icon(HELP_TEXTS['inflation_adjustment'], 'help-inflation'),
                        html.Div(id='inflation-controls-wrapper', children=[
                            html.Label('Índice:', id='inflation-index-label',
                                       style={'color': COLORS['text_muted'], 'marginLeft': '1rem'}),
                            dcc.Dropdown(
                                id='inflation-index-select',
                                options=[
                                    {'label': 'IPCA', 'value': 'IPCA'},
                                    {'label': 'INPC', 'value': 'INPC'},
                                ],
                                value='IPCA',
                                clearable=False,
                                style={'width': '100px', 'color': '#000', 'opacity': '0.5'},
                                disabled=True
                            ),
                            html.Label('Mês Ref.:', id='inflation-ref-label',
                                       style={'color': COLORS['text_muted'], 'marginLeft': '1rem'}),
                            dcc.Dropdown(
                                id='inflation-reference-month',
                                options=month_options,
                                value=max_date.isoformat() if max_date else None,
                                clearable=False,
                                style={'width': '130px', 'color': '#000', 'opacity': '0.5'},
                                disabled=True
                            ),
                        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '0.5rem'}),
                        html.Div(id='inflation-loading-trigger', style={'display': 'none'}),
                    ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'gap': '0.5rem'})
                ]
            )
        ], style={
            'padding': '0 2rem 1rem 2rem',
            'backgroundColor': COLORS['background']
        }),
    ])


def create_summary_cards() -> dcc.Loading:
    """Create the summary statistics cards section."""
    return dcc.Loading(
        id='loading-summary-cards',
        type='circle',
        color=COLORS['primary'],
        children=[
            html.Div([
                # Position card
                html.Div([
                    html.P(id='position-label', children='Posição',
                           style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'}),
                    html.H2(id='current-position-value', style={'color': COLORS['primary'], 'margin': '0.5rem 0'}),
                    # Starting position info (hidden by default, shown for partial PDFs)
                    html.P(id='starting-position-info',
                           style={'display': 'none', 'color': COLORS['text_muted'],
                                  'margin': '0', 'fontSize': '0.75rem'})
                ], style={
                    'backgroundColor': COLORS['card'],
                    'padding': '1.5rem',
                    'borderRadius': '0.75rem',
                    'flex': '1',
                    'textAlign': 'center'
                }),
                # Total invested card
                html.Div([
                    html.Div([
                        html.P(id='invested-label', children='Total Investido',
                               style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'}),
                    ]),
                    html.H2(id='total-invested-value', style={'color': COLORS['participant'], 'margin': '0.5rem 0'})
                ], style={
                    'backgroundColor': COLORS['card'],
                    'padding': '1.5rem',
                    'borderRadius': '0.75rem',
                    'flex': '1',
                    'textAlign': 'center'
                }),
                # Nucleos CAGR card
                html.Div([
                    html.Div([
                        html.P([
                            'Rendimento Nucleos (CAGR)',
                            create_help_icon(HELP_TEXTS['cagr_nucleos'], 'help-cagr-nucleos')
                        ], style={
                            'color': COLORS['text_muted'],
                            'margin': '0',
                            'fontSize': '0.875rem',
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center'
                        }),
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
                        ], style={
                            'color': COLORS['text_muted'],
                            'margin': '0',
                            'fontSize': '0.875rem',
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center'
                        }),
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
    )


def create_date_controls(month_options: list, min_date, max_date, has_data: bool) -> html.Div:
    """Create the date range and PDF upload controls."""
    return html.Div(id='date-controls', children=[
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
            # Partial PDF warning icon (hidden by default, uses same CSS as help icons)
            html.Div([
                html.Span('⚠️', className='help-icon', style={
                    'fontSize': '16px', 'cursor': 'help', 'marginLeft': '8px'
                }),
                html.Div(
                    'PDF com histórico parcial: este extrato não inclui todo o histórico de contribuições. '
                    'A "Posição antes de" mostra o saldo estimado antes do primeiro mês do PDF (baseado no SALDO TOTAL). '
                    'O gráfico mostra a posição ao final de cada mês. '
                    'Os cálculos de CAGR e XIRR consideram a posição inicial + contribuições visíveis no PDF.',
                    className='help-tooltip',
                    style={
                        'display': 'none', 'position': 'absolute',
                        'backgroundColor': COLORS['card'], 'color': COLORS['text'],
                        'padding': '10px 14px', 'borderRadius': '6px', 'fontSize': '13px',
                        'minWidth': '280px', 'maxWidth': '400px', 'width': 'max-content',
                        'zIndex': '1000', 'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.3)',
                        'top': '100%', 'left': '50%', 'transform': 'translateX(-50%)',
                        'marginTop': '4px', 'whiteSpace': 'normal', 'lineHeight': '1.5',
                    }
                )
            ], id='partial-pdf-warning', className='help-icon-container', style={
                'display': 'none', 'position': 'relative', 'verticalAlign': 'middle'
            }),
            # PDF Upload
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
    })


def create_tabs() -> dcc.Tabs:
    """Create the navigation tabs."""
    tab_style, selected_style = create_tab_style()
    return dcc.Tabs(id='tabs', value='position', children=[
        dcc.Tab(label='Posição', value='position',
                style=tab_style, selected_style=selected_style),
        dcc.Tab(label='Contribuições', value='contributions',
                style=tab_style, selected_style=selected_style),
    ], style={'padding': '0 2rem'})


def create_position_tab(benchmark_options: list, initial_fig) -> html.Div:
    """Create the position tab content."""
    table_styles = create_data_table_styles()

    return html.Div(id='position-tab', children=[
        # Scale toggle
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
        # Benchmark controls
        html.Div([
            html.Label('Comparar com:', style={'color': COLORS['text'], 'marginRight': '0.5rem'}),
            dcc.Dropdown(
                id='benchmark-select',
                options=benchmark_options,
                value='INPC',
                clearable=False,
                style={'width': '150px', 'color': '#000'}
            ),
            create_help_icon(HELP_TEXTS['benchmark'], 'help-benchmark'),
            html.Label('Overhead:', style={'color': COLORS['text'], 'margin': '0 0.5rem 0 1rem'}),
            dcc.Dropdown(
                id='overhead-select',
                options=OVERHEAD_OPTIONS,
                value=4,
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
        # Forecast controls
        html.Div([
            dcc.Checklist(
                id='forecast-toggle',
                options=[{'label': ' Projetar no futuro', 'value': 'enabled'}],
                value=[],  # Default OFF
                style={'color': COLORS['text']},
                labelStyle={'display': 'flex', 'alignItems': 'center'}
            ),
            create_help_icon(HELP_TEXTS['forecast'], 'help-forecast'),
            html.Label('Anos:', id='forecast-years-label',
                       style={'color': COLORS['text_muted'], 'marginLeft': '1rem'}),
            dcc.Dropdown(
                id='forecast-years',
                options=FORECAST_OPTIONS,
                value=1,  # Default 1 year
                clearable=False,
                style={'width': '100px', 'color': '#000', 'opacity': '0.5'},
                disabled=True  # Enabled only when forecast toggle ON
            ),
            html.Label('Cresc. salarial:', id='growth-rate-label',
                       style={'color': COLORS['text_muted'], 'marginLeft': '1rem'}),
            dcc.Dropdown(
                id='growth-rate',
                options=GROWTH_RATE_OPTIONS,
                value=DEFAULT_GROWTH_RATE,
                clearable=False,
                style={'width': '150px', 'color': '#000', 'opacity': '0.5'},
                disabled=True  # Enabled only when forecast toggle ON
            ),
            create_help_icon(HELP_TEXTS['salary_growth'], 'help-salary-growth'),
        ], style={
            'display': 'flex',
            'alignItems': 'center',
            'marginBottom': '1rem',
            'flexWrap': 'wrap',
            'gap': '0.5rem'
        }),
        # Graph
        dcc.Loading(
            id='loading-graph',
            type='circle',
            color=COLORS['primary'],
            children=[
                dcc.Graph(id='position-graph', figure=initial_fig, style={'height': '500px'})
            ]
        ),
        # Data table section
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
                        page_action='none',
                        sort_action='native',
                        **table_styles
                    ),
                ]
            ),
            dcc.Download(id='position-download'),
        ], style={'marginTop': '2rem'}),
        # Forecast data table section (only visible when forecast is ON)
        html.Div(id='forecast-table-section', children=[
            html.Div([
                html.H3('Dados Projeção', style={'color': COLORS['text'], 'margin': '0'}),
                html.Div([
                    dcc.Dropdown(
                        id='forecast-export-format',
                        options=[
                            {'label': 'CSV', 'value': 'csv'},
                            {'label': 'Excel', 'value': 'xlsx'}
                        ],
                        value='csv',
                        clearable=False,
                        style={'width': '100px', 'color': '#000'}
                    ),
                    html.Button('Exportar', id='forecast-export-btn', style={
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
                id='loading-forecast-table',
                type='circle',
                color=COLORS['primary'],
                children=[
                    dash_table.DataTable(
                        id='forecast-data-table',
                        columns=[],
                        data=[],
                        page_action='none',
                        sort_action='native',
                        **table_styles
                    ),
                ]
            ),
            dcc.Download(id='forecast-download'),
        ], style={'display': 'none', 'marginTop': '2rem'}),  # Hidden by default
    ], style={
        'padding': '2rem',
        'backgroundColor': COLORS['background'],
        'minHeight': '600px',
        'display': 'block'
    })


def create_contributions_tab(contributions_fig) -> html.Div:
    """Create the contributions tab content."""
    table_styles = create_data_table_styles()

    return html.Div(id='contributions-tab', children=[
        dcc.Loading(
            id='loading-contributions-graph',
            type='circle',
            color=COLORS['primary'],
            children=[dcc.Graph(id='contributions-graph', figure=contributions_fig, style={'height': '500px'})]
        ),
        # Data table section
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
                        page_action='none',
                        sort_action='native',
                        **table_styles
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
    })


def create_data_stores(position_data: list, contributions_data: list,
                       contributions_monthly_data: list, has_data: bool,
                       start_date_str: str, end_date_str: str,
                       stats: dict, month_options: list,
                       pdf_metadata: dict = None) -> list:
    """Create all the dcc.Store components for data storage."""
    return [
        # Display versions (may be deflated)
        dcc.Store(id='position-data', data=position_data),
        dcc.Store(id='contributions-data', data=contributions_data),
        dcc.Store(id='contributions-monthly-data', data=contributions_monthly_data),
        # Original data (never deflated - source of truth)
        dcc.Store(id='position-data-original', data=position_data),
        dcc.Store(id='contributions-data-original', data=contributions_data),
        dcc.Store(id='contributions-monthly-data-original', data=contributions_monthly_data),
        dcc.Store(id='data-loaded', data=has_data),
        dcc.Store(id='date-range-data', data={'start': start_date_str, 'end': end_date_str}),
        dcc.Store(id='benchmark-cache', data={}),
        dcc.Store(id='stats-data', data=stats),
        dcc.Store(id='month-options', data=month_options),
        # PDF metadata (partial history detection)
        dcc.Store(id='pdf-metadata', data=pdf_metadata or {}),
        # Forecast data (generated when toggle is ON)
        dcc.Store(id='forecast-data', data=None),
    ]


def create_layout(df_position: pd.DataFrame = None,
                  df_contributions_raw: pd.DataFrame = None,
                  df_contributions_monthly: pd.DataFrame = None) -> html.Div:
    """Create the complete page layout.

    Args:
        df_position: Processed position data (optional)
        df_contributions_raw: Raw contributions with exact dates
        df_contributions_monthly: Monthly aggregated contributions

    Returns:
        Complete Dash layout
    """
    # Check if we have data
    has_data = df_position is not None and not df_position.empty

    if has_data:
        min_date = df_position['data'].min()
        max_date = df_position['data'].max()

        month_options = [
            {'label': d.strftime('%b %Y'), 'value': d.isoformat()}
            for d in df_position['data']
        ]

        stats = calculate_summary_stats(df_position, df_contributions_raw, df_contributions_monthly)
        initial_position_fig = create_position_figure(df_position, log_scale=False)
        contributions_fig = create_contributions_figure(df_contributions_monthly, show_split=False)

        start_date_str = df_contributions_raw['data'].min().strftime('%Y-%m-%d')
        end_date_str = df_position['data'].max().strftime('%Y-%m-%d')

        position_data = df_position.to_dict('records')
        contributions_data = df_contributions_raw.to_dict('records')
        contributions_monthly_data = df_contributions_monthly.to_dict('records')
    else:
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

    benchmark_options = [{'label': 'Nenhum', 'value': 'none'}] + [
        {'label': name, 'value': name} for name in AVAILABLE_BENCHMARKS
    ]

    return html.Div([
        create_header(),
        create_global_toggles(month_options, max_date),
        create_summary_cards(),
        create_date_controls(month_options, min_date, max_date, has_data),
        create_tabs(),
        create_position_tab(benchmark_options, initial_position_fig),
        create_contributions_tab(contributions_fig),
        *create_data_stores(
            position_data, contributions_data, contributions_monthly_data,
            has_data, start_date_str, end_date_str, stats, month_options
        ),
    ], style={
        'backgroundColor': COLORS['background'],
        'minHeight': '100vh',
        'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    })
