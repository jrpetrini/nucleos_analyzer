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
    """Create the page header with title, GitHub link, and settings button."""
    return html.Div([
        html.Div([
            # Title row with gear icon
            html.Div([
                # Spacer to balance the gear icon on the right
                html.Div(style={'width': '2.5rem'}),
                html.H1('Nucleos Analyzer', className='header-title', style={
                    'color': COLORS['text'],
                    'marginBottom': '0',
                }),
                html.Button(
                    '⚙️',
                    id='settings-btn',
                    className='settings-btn',
                    title='Configurações',
                    style={
                        'background': 'none',
                        'border': 'none',
                        'fontSize': '1.75rem',
                        'cursor': 'pointer',
                        'padding': '0.25rem',
                        'opacity': '0.7',
                        'marginLeft': '0.5rem',
                    }
                ),
            ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'}),
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
            className='github-link',
            style={
                'position': 'absolute',
                'top': '1rem',
                'right': '1rem',
            }
        ),
    ], className='header', style={
        'backgroundColor': COLORS['background'],
    })


def create_settings_panel(month_options: list, max_date, min_date, has_data: bool,
                          benchmark_options: list) -> html.Div:
    """Create the slide-out settings panel with all configuration controls."""
    return html.Div([
        # Overlay (click to close)
        html.Div(id='settings-overlay', className='settings-overlay'),

        # Settings panel
        html.Div([
            # Header
            html.Div([
                html.H3(['Configurações ', html.Span('⚙️', style={'fontSize': '1rem'})], style={
                    'color': COLORS['text'],
                    'margin': '0',
                    'fontSize': '1.25rem',
                }),
                html.Button('✕', id='settings-close-btn', style={
                    'background': 'none',
                    'border': 'none',
                    'color': COLORS['text'],
                    'fontSize': '1.5rem',
                    'cursor': 'pointer',
                    'padding': '0',
                    'lineHeight': '1',
                }),
            ], className='settings-header', style={
                'display': 'flex',
                'justifyContent': 'space-between',
                'alignItems': 'center',
                'padding': '1rem 1.25rem',
                'borderBottom': f'1px solid {COLORS["card"]}',
            }),

            # Scrollable content
            html.Div([
                # DADOS section
                html.Div([
                    html.H4('DADOS', className='settings-section-title', style={
                        'color': COLORS['text_muted'],
                        'fontSize': '0.75rem',
                        'fontWeight': '600',
                        'letterSpacing': '0.05em',
                        'margin': '0 0 0.75rem 0',
                    }),
                    # PDF Upload
                    dcc.Loading(
                        id='loading-pdf-upload',
                        type='circle',
                        color=COLORS['sponsor'],
                        children=[
                            dcc.Upload(
                                id='pdf-upload',
                                children=html.Div('📄 Carregar PDF'),
                                className='upload-btn-settings',
                                style={
                                    'backgroundColor': COLORS['primary'] if has_data else COLORS['sponsor'],
                                    'color': COLORS['text'],
                                    'width': '100%',
                                    'textAlign': 'center',
                                    'padding': '0.75rem 1rem',
                                    'borderRadius': '0.5rem',
                                    'cursor': 'pointer',
                                    'marginBottom': '1rem',
                                    'boxSizing': 'border-box',
                                },
                                accept='.pdf'
                            ),
                        ]
                    ),
                    # Date range controls (read-only display)
                    html.Div([
                        html.Div([
                            html.Label('De:', style={'color': COLORS['text'], 'marginBottom': '0.25rem', 'display': 'block', 'fontSize': '0.875rem'}),
                            dcc.Dropdown(
                                id='start-month',
                                options=month_options,
                                value=min_date.isoformat() if min_date else None,
                                clearable=False,
                                disabled=True,
                                className='dropdown-settings',
                                style={'color': '#000'}
                            ),
                        ], style={'flex': '1'}),
                        html.Div([
                            html.Label('Até:', style={'color': COLORS['text'], 'marginBottom': '0.25rem', 'display': 'block', 'fontSize': '0.875rem'}),
                            dcc.Dropdown(
                                id='end-month',
                                options=month_options,
                                value=max_date.isoformat() if max_date else None,
                                clearable=False,
                                disabled=True,
                                className='dropdown-settings',
                                style={'color': '#000'}
                            ),
                        ], style={'flex': '1'}),
                    ], style={'display': 'flex', 'gap': '0.75rem', 'marginBottom': '0.5rem'}),
                    # Partial PDF warning
                    html.Div([
                        html.Span('⚠️', className='help-icon', style={
                            'fontSize': '14px', 'cursor': 'help', 'marginRight': '6px'
                        }),
                        html.Span('PDF com histórico parcial', style={
                            'color': COLORS['text_muted'], 'fontSize': '0.8rem'
                        }),
                    ], id='partial-pdf-warning', style={'display': 'none', 'marginTop': '0.5rem'}),
                ], className='settings-section', style={'marginBottom': '1.5rem'}),

                # AJUSTES section
                html.Div([
                    html.H4('AJUSTES', className='settings-section-title', style={
                        'color': COLORS['text_muted'],
                        'fontSize': '0.75rem',
                        'fontWeight': '600',
                        'letterSpacing': '0.05em',
                        'margin': '0 0 0.75rem 0',
                    }),
                    # Company as mine toggle
                    html.Div([
                        dcc.Checklist(
                            id='company-as-mine-toggle',
                            options=[{'label': ' Só meu aporte', 'value': 'as_mine'}],
                            value=[],
                            style={'color': COLORS['text']},
                            labelStyle={'display': 'flex', 'alignItems': 'center'}
                        ),
                        create_help_icon(HELP_TEXTS['company_as_mine'], 'help-company-toggle'),
                    ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between', 'marginBottom': '0.75rem'}),
                    # Inflation toggle
                    dcc.Loading(
                        id='loading-inflation',
                        type='circle',
                        color=COLORS['primary'],
                        children=[
                            html.Div([
                                html.Div([
                                    dcc.Checklist(
                                        id='inflation-toggle',
                                        options=[{'label': ' Ajustar inflação', 'value': 'adjust'}],
                                        value=[],
                                        style={'color': COLORS['text']},
                                        labelStyle={'display': 'flex', 'alignItems': 'center'}
                                    ),
                                    create_help_icon(HELP_TEXTS['inflation_adjustment'], 'help-inflation'),
                                ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between', 'marginBottom': '0.5rem'}),
                                html.Div(id='inflation-controls-wrapper', children=[
                                    html.Div([
                                        html.Label('Índice:', id='inflation-index-label',
                                                   style={'color': COLORS['text_muted'], 'fontSize': '0.8rem', 'marginBottom': '0.25rem', 'display': 'block'}),
                                        dcc.Dropdown(
                                            id='inflation-index-select',
                                            options=[
                                                {'label': 'IPCA', 'value': 'IPCA'},
                                                {'label': 'INPC', 'value': 'INPC'},
                                            ],
                                            value='IPCA',
                                            clearable=False,
                                            className='dropdown-settings',
                                            style={'color': '#000', 'opacity': '0.5'},
                                            disabled=True
                                        ),
                                    ], style={'flex': '1'}),
                                    html.Div([
                                        html.Label('Mês Ref.:', id='inflation-ref-label',
                                                   style={'color': COLORS['text_muted'], 'fontSize': '0.8rem', 'marginBottom': '0.25rem', 'display': 'block'}),
                                        dcc.Dropdown(
                                            id='inflation-reference-month',
                                            options=month_options,
                                            value=max_date.isoformat() if max_date else None,
                                            clearable=False,
                                            className='dropdown-settings',
                                            style={'color': '#000', 'opacity': '0.5'},
                                            disabled=True
                                        ),
                                    ], style={'flex': '1'}),
                                ], style={'display': 'flex', 'gap': '0.75rem', 'marginLeft': '1.5rem'}),
                                html.Div(id='inflation-loading-trigger', style={'display': 'none'}),
                            ])
                        ]
                    ),
                ], className='settings-section', style={'marginBottom': '1.5rem'}),

                # BENCHMARK section
                html.Div([
                    html.H4('BENCHMARK', className='settings-section-title', style={
                        'color': COLORS['text_muted'],
                        'fontSize': '0.75rem',
                        'fontWeight': '600',
                        'letterSpacing': '0.05em',
                        'margin': '0 0 0.75rem 0',
                    }),
                    html.Div([
                        html.Label([
                            'Comparar:',
                            create_help_icon(HELP_TEXTS['benchmark'], 'help-benchmark'),
                        ], style={'color': COLORS['text'], 'fontSize': '0.875rem', 'marginBottom': '0.25rem', 'display': 'flex', 'alignItems': 'center', 'gap': '0.25rem'}),
                        dcc.Dropdown(
                            id='benchmark-select',
                            options=benchmark_options,
                            value='INPC',
                            clearable=False,
                            className='dropdown-settings',
                            style={'color': '#000'}
                        ),
                    ], style={'marginBottom': '0.75rem'}),
                    html.Div([
                        html.Label([
                            'Overhead:',
                            create_help_icon(HELP_TEXTS['overhead'], 'help-overhead'),
                        ], style={'color': COLORS['text'], 'fontSize': '0.875rem', 'marginBottom': '0.25rem', 'display': 'flex', 'alignItems': 'center', 'gap': '0.25rem'}),
                        dcc.Dropdown(
                            id='overhead-select',
                            options=OVERHEAD_OPTIONS,
                            value=4,
                            clearable=False,
                            className='dropdown-settings',
                            style={'color': '#000'}
                        ),
                    ]),
                ], className='settings-section', style={'marginBottom': '1.5rem'}),

                # PROJEÇÃO section
                html.Div([
                    html.H4('PROJEÇÃO', className='settings-section-title', style={
                        'color': COLORS['text_muted'],
                        'fontSize': '0.75rem',
                        'fontWeight': '600',
                        'letterSpacing': '0.05em',
                        'margin': '0 0 0.75rem 0',
                    }),
                    html.Div([
                        dcc.Checklist(
                            id='forecast-toggle',
                            options=[{'label': ' Projetar futuro', 'value': 'enabled'}],
                            value=[],
                            style={'color': COLORS['text']},
                            labelStyle={'display': 'flex', 'alignItems': 'center'}
                        ),
                        create_help_icon(HELP_TEXTS['forecast'], 'help-forecast'),
                    ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between', 'marginBottom': '0.75rem'}),
                    html.Div([
                        html.Div([
                            html.Label('Anos:', id='forecast-years-label',
                                       style={'color': COLORS['text_muted'], 'fontSize': '0.8rem', 'marginBottom': '0.25rem', 'display': 'block'}),
                            dcc.Dropdown(
                                id='forecast-years',
                                options=FORECAST_OPTIONS,
                                value=1,
                                clearable=False,
                                className='dropdown-settings',
                                style={'color': '#000', 'opacity': '0.5'},
                                disabled=True
                            ),
                        ], style={'flex': '1', 'minWidth': '70px'}),
                        html.Div([
                            html.Label([
                                'Cresc. salarial:',
                                create_help_icon(HELP_TEXTS['salary_growth'], 'help-salary-growth'),
                            ], id='growth-rate-label',
                               style={'color': COLORS['text_muted'], 'fontSize': '0.8rem', 'marginBottom': '0.25rem', 'display': 'flex', 'alignItems': 'center', 'gap': '0.25rem'}),
                            dcc.Dropdown(
                                id='growth-rate',
                                options=GROWTH_RATE_OPTIONS,
                                value=DEFAULT_GROWTH_RATE,
                                clearable=False,
                                className='dropdown-settings',
                                style={'color': '#000', 'opacity': '0.5'},
                                disabled=True
                            ),
                        ], style={'flex': '2', 'minWidth': '100px'}),
                    ], className='forecast-controls', style={'display': 'flex', 'gap': '0.5rem', 'alignItems': 'flex-end', 'marginLeft': '1.5rem', 'flexWrap': 'wrap'}),
                ], className='settings-section', style={'marginBottom': '1.5rem'}),

                # Hidden scale toggle (kept for callback compatibility)
                dcc.RadioItems(
                    id='scale-toggle',
                    options=[{'label': 'linear', 'value': 'linear'}],
                    value='linear',
                    style={'display': 'none'}
                ),

                # OK button
                html.Button('OK', id='settings-ok-btn', style={
                    'width': '100%',
                    'padding': '0.75rem',
                    'backgroundColor': COLORS['primary'],
                    'color': COLORS['text'],
                    'border': 'none',
                    'borderRadius': '0.5rem',
                    'fontSize': '1rem',
                    'fontWeight': '500',
                    'cursor': 'pointer',
                    'marginTop': '0.5rem',
                }),

            ], id='settings-content', className='settings-content', style={
                'padding': '1.25rem',
                'overflowY': 'auto',
                'flex': '1',
            }),

        ], id='settings-panel', className='settings-panel', style={
            'position': 'fixed',
            'top': '0',
            'right': '0',
            'width': '320px',
            'height': '100vh',
            'backgroundColor': COLORS['background'],
            'boxShadow': '-4px 0 20px rgba(0, 0, 0, 0.3)',
            'transform': 'translateX(100%)',
            'transition': 'transform 0.3s ease',
            'zIndex': '1000',
            'display': 'flex',
            'flexDirection': 'column',
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
                ], className='summary-card', style={
                    'backgroundColor': COLORS['card'],
                }),
                # Total invested card
                html.Div([
                    html.Div([
                        html.P(id='invested-label', children='Total Investido',
                               style={'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'}),
                    ]),
                    html.H2(id='total-invested-value', style={'color': COLORS['participant'], 'margin': '0.5rem 0'})
                ], className='summary-card', style={
                    'backgroundColor': COLORS['card'],
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
                            'justifyContent': 'center',
                            'flexWrap': 'wrap'
                        }),
                    ]),
                    html.H2(id='nucleos-cagr-value', style={'margin': '0.5rem 0'}),
                    html.P(id='nucleos-return-value', style={'margin': '0', 'fontSize': '0.875rem'})
                ], className='summary-card', style={
                    'backgroundColor': COLORS['card'],
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
                            'justifyContent': 'center',
                            'flexWrap': 'wrap'
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
                ], className='summary-card', style={
                    'backgroundColor': COLORS['card'],
                }),
            ], className='summary-cards-container', style={
                'backgroundColor': COLORS['background']
            }),
        ]
    )


def create_tabs() -> dcc.Tabs:
    """Create the navigation tabs."""
    tab_style, selected_style = create_tab_style()
    return dcc.Tabs(id='tabs', value='position', children=[
        dcc.Tab(label='Posição', value='position',
                style=tab_style, selected_style=selected_style),
        dcc.Tab(label='Contribuições', value='contributions',
                style=tab_style, selected_style=selected_style),
    ], style={'padding': '0 2rem'})


def create_position_tab(initial_fig) -> html.Div:
    """Create the position tab content (controls moved to settings panel)."""
    table_styles = create_data_table_styles()

    return html.Div(id='position-tab', className='tab-content', children=[
        # Graph (controls are now in settings panel)
        dcc.Loading(
            id='loading-graph',
            type='circle',
            color=COLORS['primary'],
            children=[
                dcc.Graph(
                    id='position-graph',
                    figure=initial_fig,
                    className='graph-container',
                    config={'scrollZoom': False, 'displayModeBar': False}
                )
            ]
        ),
        # Data table section
        html.Div([
            html.Div([
                html.Div([
                    html.H3('Dados', style={'color': COLORS['text'], 'margin': '0'}),
                    create_help_icon(HELP_TEXTS['position_table'], 'help-position-table'),
                ], className='table-title-group'),
                html.Div([
                    dcc.Dropdown(
                        id='position-export-format',
                        options=[
                            {'label': 'CSV', 'value': 'csv'},
                            {'label': 'Excel', 'value': 'xlsx'}
                        ],
                        value='csv',
                        clearable=False,
                        className='dropdown-sm',
                        style={'color': '#000'}
                    ),
                    html.Button('Exportar', id='position-export-btn', className='btn-primary', style={
                        'backgroundColor': COLORS['primary'],
                        'color': COLORS['text'],
                        'marginLeft': '0.5rem'
                    }),
                ], className='export-controls'),
            ], className='table-header-row'),
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
                        className='dropdown-sm',
                        style={'color': '#000'}
                    ),
                    html.Button('Exportar', id='forecast-export-btn', className='btn-primary', style={
                        'backgroundColor': COLORS['primary'],
                        'color': COLORS['text'],
                        'marginLeft': '0.5rem'
                    }),
                ], className='export-controls'),
            ], className='table-header-row'),
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
        'backgroundColor': COLORS['background'],
        'display': 'block'
    })


def create_contributions_tab(contributions_fig) -> html.Div:
    """Create the contributions tab content."""
    table_styles = create_data_table_styles()

    return html.Div(id='contributions-tab', className='tab-content', children=[
        dcc.Loading(
            id='loading-contributions-graph',
            type='circle',
            color=COLORS['primary'],
            children=[
                dcc.Graph(
                    id='contributions-graph',
                    figure=contributions_fig,
                    className='graph-container',
                    config={'scrollZoom': False, 'displayModeBar': False}
                )
            ]
        ),
        # Data table section
        html.Div([
            html.Div([
                html.Div([
                    html.H3('Dados', style={'color': COLORS['text'], 'margin': '0'}),
                    create_help_icon(HELP_TEXTS['contributions_table'], 'help-contributions-table'),
                ], className='table-title-group'),
                html.Div([
                    dcc.Dropdown(
                        id='contributions-export-format',
                        options=[
                            {'label': 'CSV', 'value': 'csv'},
                            {'label': 'Excel', 'value': 'xlsx'}
                        ],
                        value='csv',
                        clearable=False,
                        className='dropdown-sm',
                        style={'color': '#000'}
                    ),
                    html.Button('Exportar', id='contributions-export-btn', className='btn-primary', style={
                        'backgroundColor': COLORS['primary'],
                        'color': COLORS['text'],
                        'marginLeft': '0.5rem'
                    }),
                ], className='export-controls'),
            ], className='table-header-row'),
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
        'backgroundColor': COLORS['background'],
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
        create_summary_cards(),
        create_tabs(),
        create_position_tab(initial_position_fig),
        create_contributions_tab(contributions_fig),
        create_settings_panel(month_options, max_date, min_date, has_data, benchmark_options),
        *create_data_stores(
            position_data, contributions_data, contributions_monthly_data,
            has_data, start_date_str, end_date_str, stats, month_options
        ),
        # Settings panel state store
        dcc.Store(id='settings-panel-open', data=not has_data),  # Open by default when no data
    ], id='page-container', className='page-container', style={
        'backgroundColor': COLORS['background'],
    })
