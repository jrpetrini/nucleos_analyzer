#!/usr/bin/env python3
"""
Callback functions for Nucleos Analyzer dashboard.
"""

import base64
import io
import pandas as pd
import dash
from dash import callback, Output, Input, State, dcc

from components import COLORS
from figures import create_position_figure, create_contributions_figure, create_empty_figure
from calculator import calculate_summary_stats
from benchmarks import fetch_single_benchmark, apply_overhead_to_benchmark, simulate_benchmark
from dashboard_helpers import prepare_dataframe, is_company_as_mine
from business_logic import filter_data_by_range, calculate_nucleos_stats


def register_callbacks(app):
    """Register all callbacks for the Dash application.

    Args:
        app: The Dash application instance
    """

    @callback(
        Output('position-tab', 'style'),
        Output('contributions-tab', 'style'),
        Input('tabs', 'value')
    )
    def toggle_tabs(tab):
        """Toggle visibility between position and contributions tabs."""
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
        Output('inflation-index-select', 'disabled'),
        Output('inflation-reference-month', 'disabled'),
        Output('inflation-index-select', 'style'),
        Output('inflation-reference-month', 'style'),
        Output('inflation-index-label', 'style'),
        Output('inflation-ref-label', 'style'),
        Input('inflation-toggle', 'value')
    )
    def toggle_inflation_controls(inflation_toggle):
        """Enable/disable inflation controls based on toggle."""
        is_enabled = 'adjust' in (inflation_toggle or [])

        if is_enabled:
            dropdown_style = {'width': '100px', 'color': '#000'}
            ref_dropdown_style = {'width': '130px', 'color': '#000'}
            label_style = {'color': COLORS['text'], 'marginLeft': '1rem'}
        else:
            dropdown_style = {'width': '100px', 'color': '#000', 'opacity': '0.5'}
            ref_dropdown_style = {'width': '130px', 'color': '#000', 'opacity': '0.5'}
            label_style = {'color': COLORS['text_muted'], 'marginLeft': '1rem'}

        return (not is_enabled, not is_enabled,
                dropdown_style, ref_dropdown_style,
                label_style, label_style)

    @callback(
        Output('inflation-reference-month', 'options'),
        Output('inflation-reference-month', 'value'),
        Input('month-options', 'data'),
        State('inflation-reference-month', 'value'),
    )
    def update_inflation_reference_options(month_options, current_value):
        """Update reference month options when data is loaded."""
        if not month_options:
            return [], None
        if current_value is None or current_value not in [opt['value'] for opt in month_options]:
            return month_options, month_options[0]['value']
        return month_options, current_value

    @callback(
        Output('position-data', 'data', allow_duplicate=True),
        Output('contributions-data', 'data', allow_duplicate=True),
        Output('contributions-monthly-data', 'data', allow_duplicate=True),
        Output('inflation-loading-trigger', 'children'),
        Input('inflation-toggle', 'value'),
        Input('inflation-index-select', 'value'),
        Input('inflation-reference-month', 'value'),
        State('position-data-original', 'data'),
        State('contributions-data-original', 'data'),
        State('contributions-monthly-data-original', 'data'),
        State('date-range-data', 'data'),
        prevent_initial_call=True
    )
    def apply_inflation_adjustment(inflation_toggle, inflation_index, reference_month,
                                   position_original, contributions_original,
                                   contributions_monthly_original, date_range):
        """Apply or remove inflation adjustment to display data."""
        from calculator import apply_deflation, process_contributions_data

        if not position_original:
            raise dash.exceptions.PreventUpdate

        is_inflation_on = 'adjust' in (inflation_toggle or [])

        if not is_inflation_on:
            return position_original, contributions_original, contributions_monthly_original, ''

        if not reference_month or not date_range:
            raise dash.exceptions.PreventUpdate

        extended_start = (pd.Timestamp(date_range['start']) - pd.DateOffset(months=1)).replace(day=1)
        inflation_data = fetch_single_benchmark(
            inflation_index,
            extended_start.isoformat(),
            date_range['end']
        )

        if inflation_data is None:
            return position_original, contributions_original, contributions_monthly_original, ''

        df_pos = pd.DataFrame(position_original)
        df_pos['data'] = pd.to_datetime(df_pos['data'])

        df_contrib = pd.DataFrame(contributions_original)
        df_contrib['data'] = pd.to_datetime(df_contrib['data'])

        df_pos_deflated, df_contrib_deflated = apply_deflation(
            df_pos, df_contrib, inflation_data, reference_month
        )

        df_contrib_monthly_deflated = process_contributions_data(df_contrib_deflated)

        return (
            df_pos_deflated.to_dict('records'),
            df_contrib_deflated.to_dict('records'),
            df_contrib_monthly_deflated.to_dict('records'),
            '',
        )

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

        if not current_end and filtered_options:
            new_end = filtered_options[-1]['value']
        elif current_end and pd.to_datetime(current_end) < start_dt:
            new_end = start_month
        else:
            new_end = current_end

        return filtered_options, new_end

    @callback(
        Output('position-label', 'children'),
        Output('current-position-value', 'children'),
        Output('invested-label', 'children'),
        Output('total-invested-value', 'children'),
        Output('nucleos-cagr-value', 'children'),
        Output('nucleos-cagr-value', 'style'),
        Output('nucleos-return-value', 'children'),
        Output('nucleos-return-value', 'style'),
        Input('company-as-mine-toggle', 'value'),
        Input('start-month', 'value'),
        Input('end-month', 'value'),
        Input('contributions-data', 'data'),
        Input('position-data', 'data'),
        State('pdf-metadata', 'data'),
    )
    def update_nucleos_stats(company_as_mine, start_date, end_date, contributions_data, position_data, pdf_metadata):
        """Update Nucleos statistics cards."""
        if not contributions_data or not position_data:
            return ('Posição', 'R$ 0,00', 'Total Investido', 'R$ 0,00', 'N/A',
                    {'color': COLORS['text_muted'], 'margin': '0.5rem 0'},
                    'R$ 0,00 total', {'color': COLORS['text_muted'], 'margin': '0', 'fontSize': '0.875rem'})

        df_contrib = prepare_dataframe(contributions_data)
        df_pos = prepare_dataframe(position_data)

        # Get missing_cotas for partial PDFs (to calculate growth correctly)
        missing_cotas = 0.0
        if pdf_metadata and pdf_metadata.get('is_partial'):
            missing_cotas = pdf_metadata.get('missing_cotas', 0.0)

        stats = calculate_nucleos_stats(
            df_contrib, df_pos, start_date, end_date,
            is_company_as_mine(company_as_mine), COLORS,
            missing_cotas=missing_cotas
        )

        return (
            stats['position_label'],
            stats['position_value'],
            stats['invested_label'],
            stats['invested_value'],
            stats['cagr_text'],
            stats['cagr_style'],
            stats['return_text'],
            stats['return_style']
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
        Input('position-data', 'data'),
        Input('contributions-data', 'data'),
        State('inflation-toggle', 'value'),
        State('inflation-index-select', 'value'),
        State('inflation-reference-month', 'value'),
        State('contributions-data-original', 'data'),
        State('date-range-data', 'data'),
        State('benchmark-cache', 'data'),
        State('pdf-metadata', 'data'),
    )
    def update_position_graph(scale, start_date, end_date, benchmark_name, overhead,
                              company_as_mine, position_data, contributions_data,
                              inflation_toggle, inflation_index, inflation_ref_month,
                              contributions_original, date_range, cache, pdf_metadata):
        """Update the position graph and benchmark calculations."""
        if not position_data or not contributions_data:
            empty_fig = create_empty_figure("Carregue um PDF para visualizar")
            return (empty_fig, '--', {'color': COLORS['text_muted'], 'margin': '0.5rem 0'},
                    'Selecione um benchmark', cache or {})

        df = pd.DataFrame(position_data)
        df['data'] = pd.to_datetime(df['data'])

        df_contrib = pd.DataFrame(contributions_data)
        df_contrib['data'] = pd.to_datetime(df_contrib['data'])

        df_contrib_orig = pd.DataFrame(contributions_original) if contributions_original else df_contrib.copy()
        df_contrib_orig['data'] = pd.to_datetime(df_contrib_orig['data'])

        df_pos_filtered, df_contrib_filtered, position_before_start, date_before_start = filter_data_by_range(
            df, df_contrib, start_date, end_date
        )
        _, df_contrib_orig_filtered, _, _ = filter_data_by_range(
            df, df_contrib_orig, start_date, end_date
        )

        is_inflation_on = 'adjust' in (inflation_toggle or [])
        inflation_data = None
        if is_inflation_on and date_range and inflation_index and inflation_ref_month:
            extended_start = (pd.Timestamp(date_range['start']) - pd.DateOffset(months=1)).replace(day=1)
            inflation_data = fetch_single_benchmark(
                inflation_index, extended_start.strftime('%Y-%m-%d'), date_range['end']
            )

        benchmark_sim = None
        benchmark_label = None
        benchmark_cagr_text = '--'
        benchmark_cagr_style = {'color': COLORS['text_muted'], 'margin': '0.5rem 0'}
        benchmark_label_text = 'Selecione um benchmark'

        if benchmark_name and benchmark_name != 'none' and not df_contrib_orig_filtered.empty and not df_pos_filtered.empty:
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
                    cache[cache_key] = benchmark_raw.to_dict('records')

            if benchmark_raw is not None:
                benchmark_with_overhead = apply_overhead_to_benchmark(benchmark_raw, overhead)

                if overhead > 0:
                    benchmark_label = f'{benchmark_name} +{overhead}%'
                else:
                    benchmark_label = benchmark_name

                treat_company_as_mine = 'as_mine' in (company_as_mine or [])
                if treat_company_as_mine and 'contrib_participante' in df_contrib_orig_filtered.columns:
                    contrib_amounts = df_contrib_orig_filtered['contrib_participante']
                else:
                    contrib_amounts = df_contrib_orig_filtered['contribuicao_total']

                df_contrib_sim = df_contrib_orig_filtered[['data']].copy()
                df_contrib_sim['contribuicao_total'] = contrib_amounts

                # For partial PDFs, prepend starting position as initial "contribution"
                # This makes benchmark start from same position as Nucleos
                if pdf_metadata and pdf_metadata.get('is_partial'):
                    starting_pos = pdf_metadata.get('starting_position', 0)
                    first_pos_date = df_pos_filtered['data'].min()
                    starting_contrib = pd.DataFrame({
                        'data': [first_pos_date],
                        'contribuicao_total': [starting_pos]
                    })
                    df_contrib_sim = pd.concat([starting_contrib, df_contrib_sim], ignore_index=True)

                if not df_contrib_sim.empty:
                    first_contrib_month = df_contrib_sim['data'].min().to_period('M')
                    position_dates_for_bench = df_pos_filtered[
                        df_pos_filtered['data'].dt.to_period('M') >= first_contrib_month
                    ][['data']].copy()
                else:
                    position_dates_for_bench = df_pos_filtered[['data']].copy()

                benchmark_sim = simulate_benchmark(
                    df_contrib_sim,
                    benchmark_with_overhead,
                    position_dates_for_bench
                )

                if is_inflation_on and inflation_data is not None and not benchmark_sim.empty:
                    from calculator import deflate_series
                    benchmark_sim = deflate_series(benchmark_sim, inflation_data, inflation_ref_month, 'posicao')
                    benchmark_sim['posicao'] = benchmark_sim['posicao_real']
                    benchmark_sim = benchmark_sim.drop(columns=['posicao_real'])

                if not benchmark_sim.empty:
                    benchmark_final_value = benchmark_sim['posicao'].iloc[-1]

                    from calculator import xirr_bizdays
                    last_date = df_pos_filtered['data'].iloc[-1]

                    if treat_company_as_mine and 'contrib_participante' in df_contrib_filtered.columns:
                        contrib_for_cagr = df_contrib_filtered['contrib_participante']
                    else:
                        contrib_for_cagr = df_contrib_filtered['contribuicao_total']

                    # For partial PDFs, CAGR should only measure visible contributions' growth
                    # (matching Nucleos which excludes invisible cotas from CAGR).
                    # We need a separate simulation without starting_position for this.
                    if pdf_metadata and pdf_metadata.get('is_partial'):
                        # Simulate benchmark with only visible contributions (no starting_position)
                        df_contrib_visible_only = df_contrib_orig_filtered[['data']].copy()
                        df_contrib_visible_only['contribuicao_total'] = contrib_amounts
                        bench_sim_for_cagr = simulate_benchmark(
                            df_contrib_visible_only,
                            benchmark_with_overhead,
                            position_dates_for_bench
                        )
                        if is_inflation_on and inflation_data is not None and not bench_sim_for_cagr.empty:
                            from calculator import deflate_series
                            bench_sim_for_cagr = deflate_series(bench_sim_for_cagr, inflation_data, inflation_ref_month, 'posicao')
                            bench_sim_for_cagr['posicao'] = bench_sim_for_cagr['posicao_real']
                        cagr_final_value = bench_sim_for_cagr['posicao'].iloc[-1] if not bench_sim_for_cagr.empty else 0
                    else:
                        cagr_final_value = benchmark_final_value

                    dates = df_contrib_filtered['data'].tolist() + [last_date]
                    amounts = [-amt for amt in contrib_for_cagr.tolist()] + [cagr_final_value]

                    bench_cagr = xirr_bizdays(dates, amounts)

                    if bench_cagr is not None:
                        bench_cagr_pct = bench_cagr * 100
                        benchmark_cagr_text = f'{bench_cagr_pct:+.2f}% a.a.'
                        color = COLORS['accent'] if bench_cagr_pct >= 0 else '#ef4444'
                        benchmark_cagr_style = {'color': color, 'margin': '0.5rem 0'}
                    else:
                        benchmark_cagr_text = 'N/A'

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
        Input('contributions-monthly-data', 'data'),
        Input('position-data', 'data'),
        State('pdf-metadata', 'data')
    )
    def update_contributions_graph(company_as_mine, start_date, end_date, monthly_data, position_data, pdf_metadata):
        """Update the contributions graph."""
        if not monthly_data or not position_data:
            return create_empty_figure("Carregue um PDF para visualizar")

        df_monthly = prepare_dataframe(monthly_data)
        df_pos = prepare_dataframe(position_data)

        df_pos_filtered, df_monthly_filtered, _, _ = filter_data_by_range(
            df_pos, df_monthly, start_date, end_date
        )

        is_partial = pdf_metadata.get('is_partial', False) if pdf_metadata else False

        # For partial PDFs, subtract invisible cotas' value to show only visible growth
        if is_partial and 'valor_cota' in df_pos_filtered.columns:
            missing_cotas = pdf_metadata.get('missing_cotas', 0.0)
            df_pos_for_contrib = df_pos_filtered.copy()
            df_pos_for_contrib['posicao'] = df_pos_for_contrib['posicao'] - (missing_cotas * df_pos_for_contrib['valor_cota'])
        else:
            df_pos_for_contrib = df_pos_filtered

        return create_contributions_figure(
            df_monthly_filtered, df_position=df_pos_for_contrib,
            show_split=is_company_as_mine(company_as_mine),
            is_partial=is_partial
        )

    @callback(
        Output('position-data', 'data'),
        Output('contributions-data', 'data'),
        Output('contributions-monthly-data', 'data'),
        Output('position-data-original', 'data'),
        Output('contributions-data-original', 'data'),
        Output('contributions-monthly-data-original', 'data'),
        Output('date-range-data', 'data'),
        Output('stats-data', 'data'),
        Output('month-options', 'data'),
        Output('start-month', 'options'),
        Output('start-month', 'value'),
        Output('data-loaded', 'data'),
        Output('pdf-metadata', 'data'),
        Input('pdf-upload', 'contents'),
        State('pdf-upload', 'filename'),
        prevent_initial_call=True
    )
    def upload_pdf(contents, filename):
        """Process uploaded PDF file."""
        import tempfile
        import os

        if contents is None:
            raise dash.exceptions.PreventUpdate

        from extractor import extract_data_from_pdf, detect_partial_history
        from calculator import process_position_data, process_contributions_data

        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        pdf_file = io.BytesIO(decoded)

        df_raw, df_contributions_raw = extract_data_from_pdf(pdf_file)

        # Detect partial history (need temp file for SALDO extraction)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(decoded)
            tmp_path = tmp.name

        try:
            pdf_metadata = detect_partial_history(tmp_path, df_raw)
        finally:
            os.unlink(tmp_path)

        # For partial PDFs, add starting_cotas to position data so totals are correct
        starting_cotas = 0.0
        if pdf_metadata and pdf_metadata.get('is_partial'):
            starting_cotas = pdf_metadata.get('missing_cotas', 0.0)

        df_position = process_position_data(df_raw, starting_cotas=starting_cotas)
        df_contributions_monthly = process_contributions_data(df_contributions_raw)

        month_options = [
            {'label': d.strftime('%b %Y'), 'value': d.isoformat()}
            for d in df_position['data']
        ]

        min_date = df_position['data'].min()
        stats = calculate_summary_stats(df_position, df_contributions_raw, df_contributions_monthly)

        start_date_str = df_contributions_raw['data'].min().strftime('%Y-%m-%d')
        end_date_str = df_position['data'].max().strftime('%Y-%m-%d')

        position_data = df_position.to_dict('records')
        contributions_data = df_contributions_raw.to_dict('records')
        contributions_monthly_data = df_contributions_monthly.to_dict('records')

        return (
            position_data,
            contributions_data,
            contributions_monthly_data,
            position_data,
            contributions_data,
            contributions_monthly_data,
            {'start': start_date_str, 'end': end_date_str},
            stats,
            month_options,
            month_options,
            min_date.isoformat(),
            True,
            pdf_metadata or {},
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
            base_style['backgroundColor'] = COLORS['sponsor']
        return base_style

    @callback(
        Output('partial-pdf-warning', 'style'),
        Input('pdf-metadata', 'data')
    )
    def update_partial_warning(pdf_metadata):
        """Show/hide partial PDF warning icon based on metadata."""
        base_style = {
            'position': 'relative',
            'verticalAlign': 'middle'
        }
        if pdf_metadata and pdf_metadata.get('is_partial'):
            base_style['display'] = 'inline-block'
        else:
            base_style['display'] = 'none'
        return base_style

    @callback(
        Output('starting-position-info', 'children'),
        Output('starting-position-info', 'style'),
        Input('pdf-metadata', 'data')
    )
    def update_starting_position_info(pdf_metadata):
        """Show starting position info for partial PDFs."""
        hidden_style = {'display': 'none'}

        if not pdf_metadata or not pdf_metadata.get('is_partial'):
            return '', hidden_style

        starting_pos = pdf_metadata.get('starting_position', 0)
        first_month = pdf_metadata.get('first_month', '')

        text = f'Posição antes de {first_month}: R$ {starting_pos:,.2f}'
        visible_style = {
            'display': 'block',
            'color': COLORS['text_muted'],
            'margin': '0.25rem 0 0 0',
            'fontSize': '0.75rem'
        }
        return text, visible_style

    @callback(
        Output('position-data-table', 'data'),
        Output('position-data-table', 'columns'),
        Input('start-month', 'value'),
        Input('end-month', 'value'),
        Input('benchmark-select', 'value'),
        Input('overhead-select', 'value'),
        Input('company-as-mine-toggle', 'value'),
        Input('position-data', 'data'),
        Input('contributions-data', 'data'),
        State('inflation-toggle', 'value'),
        State('inflation-index-select', 'value'),
        State('inflation-reference-month', 'value'),
        State('date-range-data', 'data'),
        State('benchmark-cache', 'data'),
        State('pdf-metadata', 'data'),
    )
    def update_position_table(start_date, end_date, benchmark_name, overhead,
                              company_as_mine, position_data, contributions_data,
                              inflation_toggle, inflation_index, inflation_ref_month,
                              date_range, cache, pdf_metadata):
        """Populate position data table with Nucleos and benchmark values."""
        if not position_data or not contributions_data:
            return [], []

        df = pd.DataFrame(position_data)
        df['data'] = pd.to_datetime(df['data'])

        df_contrib = pd.DataFrame(contributions_data)
        df_contrib['data'] = pd.to_datetime(df_contrib['data'])

        df_pos_filtered, df_contrib_filtered, position_before_start, _ = filter_data_by_range(
            df, df_contrib, start_date, end_date
        )

        if df_pos_filtered.empty:
            return [], []

        is_inflation_on = 'adjust' in (inflation_toggle or [])

        deflator_dict = {}
        if is_inflation_on and date_range and inflation_index:
            deflator_data = fetch_single_benchmark(
                inflation_index, date_range['start'], date_range['end']
            )
            if deflator_data is not None:
                deflator_data['date'] = pd.to_datetime(deflator_data['date'])
                deflator_dict = {row['date'].strftime('%b %Y'): row['value']
                                for _, row in deflator_data.iterrows()}

        treat_company_as_mine = 'as_mine' in (company_as_mine or [])
        df_contrib_sorted = df_contrib_filtered.sort_values('data')

        table_data = []
        for _, row in df_pos_filtered.iterrows():
            pos_date = row['data']
            date_key = pos_date.strftime('%b %Y')

            contrib_up_to_date = df_contrib_sorted[df_contrib_sorted['data'] <= pos_date]
            total_contrib = contrib_up_to_date['contribuicao_total'].sum() if not contrib_up_to_date.empty else 0

            row_data = {
                'data': date_key,
                'posicao': f"R$ {row['posicao']:,.2f}",
                'total_contrib': f"R$ {total_contrib:,.2f}"
            }

            if treat_company_as_mine and 'contrib_participante' in df_contrib_sorted.columns:
                participant_contrib = contrib_up_to_date['contrib_participante'].sum() if not contrib_up_to_date.empty else 0
                row_data['participant_contrib'] = f"R$ {participant_contrib:,.2f}"

            if is_inflation_on and deflator_dict:
                if date_key in deflator_dict:
                    row_data['deflator'] = f"{deflator_dict[date_key]:.6f}"
                else:
                    row_data['deflator'] = '-'
            table_data.append(row_data)

        columns = [
            {'name': 'Data', 'id': 'data'},
            {'name': 'Posição (Nucleos)', 'id': 'posicao'},
            {'name': 'Contrib. Total', 'id': 'total_contrib'},
        ]
        if treat_company_as_mine and 'contrib_participante' in df_contrib_sorted.columns:
            columns.append({'name': 'Contrib. Participante', 'id': 'participant_contrib'})
        if is_inflation_on and deflator_dict:
            columns.append({'name': f'Deflator ({inflation_index})', 'id': 'deflator'})

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
                treat_company_as_mine = 'as_mine' in (company_as_mine or [])
                if treat_company_as_mine and 'contrib_participante' in df_contrib_filtered.columns:
                    contrib_amounts = df_contrib_filtered['contrib_participante']
                else:
                    contrib_amounts = df_contrib_filtered['contribuicao_total']

                df_contrib_sim = df_contrib_filtered[['data']].copy()
                df_contrib_sim['contribuicao_total'] = contrib_amounts

                # For partial PDFs, prepend starting position as initial "contribution"
                if pdf_metadata and pdf_metadata.get('is_partial'):
                    starting_pos = pdf_metadata.get('starting_position', 0)
                    first_pos_date = df_pos_filtered['data'].min()
                    starting_contrib = pd.DataFrame({
                        'data': [first_pos_date],
                        'contribuicao_total': [starting_pos]
                    })
                    df_contrib_sim = pd.concat([starting_contrib, df_contrib_sim], ignore_index=True)

                if not df_contrib_sim.empty:
                    first_contrib_month = df_contrib_sim['data'].min().to_period('M')
                    position_dates_for_bench = df_pos_filtered[
                        df_pos_filtered['data'].dt.to_period('M') >= first_contrib_month
                    ][['data']].copy()
                else:
                    position_dates_for_bench = df_pos_filtered[['data']].copy()

                benchmark_sim_raw = simulate_benchmark(
                    df_contrib_sim,
                    benchmark_raw,
                    position_dates_for_bench
                )

                benchmark_with_overhead = apply_overhead_to_benchmark(benchmark_raw, overhead)
                benchmark_sim_overhead = simulate_benchmark(
                    df_contrib_sim,
                    benchmark_with_overhead,
                    position_dates_for_bench
                )

                bench_raw_dict = {row['data'].strftime('%b %Y'): row['posicao']
                                 for _, row in benchmark_sim_raw.iterrows()} if not benchmark_sim_raw.empty else {}
                bench_overhead_dict = {row['data'].strftime('%b %Y'): row['posicao']
                                       for _, row in benchmark_sim_overhead.iterrows()} if not benchmark_sim_overhead.empty else {}

                benchmark_raw['date'] = pd.to_datetime(benchmark_raw['date'])
                index_raw_dict = {row['date'].strftime('%b %Y'): row['value']
                                  for _, row in benchmark_raw.iterrows()}
                benchmark_with_overhead['date'] = pd.to_datetime(benchmark_with_overhead['date'])
                index_overhead_dict = {row['date'].strftime('%b %Y'): row['value']
                                       for _, row in benchmark_with_overhead.iterrows()}

                for row in table_data:
                    date_key = row['data']
                    if overhead > 0:
                        if date_key in bench_overhead_dict:
                            row['bench_overhead'] = f"R$ {bench_overhead_dict[date_key]:,.2f}"
                        else:
                            row['bench_overhead'] = '-'
                        if date_key in index_overhead_dict:
                            row['index_overhead'] = f"{index_overhead_dict[date_key]:.4f}"
                        else:
                            row['index_overhead'] = '-'
                    if date_key in bench_raw_dict:
                        row['bench_raw'] = f"R$ {bench_raw_dict[date_key]:,.2f}"
                    else:
                        row['bench_raw'] = '-'
                    if date_key in index_raw_dict:
                        row['index_raw'] = f"{index_raw_dict[date_key]:.4f}"
                    else:
                        row['index_raw'] = '-'

                if overhead > 0:
                    columns.append({'name': f'{benchmark_name} +{overhead}% (simulado)', 'id': 'bench_overhead'})
                columns.append({'name': f'{benchmark_name} (simulado)', 'id': 'bench_raw'})
                if overhead > 0:
                    columns.append({'name': f'{benchmark_name} +{overhead}% (índice)', 'id': 'index_overhead'})
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
        Input('contributions-monthly-data', 'data'),
        Input('position-data', 'data'),
        State('inflation-toggle', 'value'),
        State('inflation-index-select', 'value'),
        State('inflation-reference-month', 'value'),
        State('date-range-data', 'data'),
    )
    def update_contributions_table(start_date, end_date, company_as_mine,
                                   monthly_data, position_data,
                                   inflation_toggle, inflation_index, inflation_ref_month,
                                   date_range):
        """Populate contributions data table."""
        if not monthly_data:
            return [], []

        df_monthly = pd.DataFrame(monthly_data)
        df_monthly['data'] = pd.to_datetime(df_monthly['data'])

        is_inflation_on = 'adjust' in (inflation_toggle or [])

        if position_data:
            df_pos = pd.DataFrame(position_data)
            df_pos['data'] = pd.to_datetime(df_pos['data'])
        else:
            df_pos = pd.DataFrame()

        start_dt = pd.to_datetime(start_date) if start_date else None
        end_dt = pd.to_datetime(end_date) if end_date else None

        if start_dt:
            df_monthly = df_monthly[df_monthly['data'] >= start_dt]
        if end_dt:
            df_monthly = df_monthly[df_monthly['data'] <= end_dt]

        if df_monthly.empty:
            return [], []

        show_split = 'as_mine' in (company_as_mine or [])
        if show_split:
            df_monthly['total_investido'] = df_monthly['contrib_participante'].cumsum()
            df_monthly['contrib_total_acum'] = df_monthly['contribuicao_total'].cumsum()
        else:
            df_monthly['total_investido'] = df_monthly['contribuicao_total'].cumsum()

        deflator_dict = {}
        if is_inflation_on and date_range and inflation_index:
            deflator_data = fetch_single_benchmark(
                inflation_index, date_range['start'], date_range['end']
            )
            if deflator_data is not None:
                deflator_data['date'] = pd.to_datetime(deflator_data['date'])
                deflator_dict = {row['date'].strftime('%b %Y'): row['value']
                                for _, row in deflator_data.iterrows()}

        table_data = []
        for _, row in df_monthly.iterrows():
            date_key = row['data'].strftime('%b %Y')
            row_data = {
                'data': date_key,
                'contrib_total': f"R$ {row['contribuicao_total']:,.2f}",
                'total_investido': f"R$ {row['total_investido']:,.2f}",
            }
            if show_split:
                row_data['contrib_participante'] = f"R$ {row['contrib_participante']:,.2f}"
                row_data['contrib_patrocinador'] = f"R$ {row['contrib_patrocinador']:,.2f}"
                row_data['contrib_total_acum'] = f"R$ {row['contrib_total_acum']:,.2f}"

            if not df_pos.empty:
                pos_row = df_pos[df_pos['data'] == row['data']]
                if not pos_row.empty:
                    row_data['posicao'] = f"R$ {pos_row['posicao'].iloc[0]:,.2f}"
                else:
                    row_data['posicao'] = '-'
            if is_inflation_on and deflator_dict:
                if date_key in deflator_dict:
                    row_data['deflator'] = f"{deflator_dict[date_key]:.6f}"
                else:
                    row_data['deflator'] = '-'
            table_data.append(row_data)

        columns = [{'name': 'Data', 'id': 'data'}]
        if show_split:
            columns.append({'name': 'Contrib. Participante', 'id': 'contrib_participante'})
            columns.append({'name': 'Contrib. Patrocinador', 'id': 'contrib_patrocinador'})
        columns.append({'name': 'Contrib. Total', 'id': 'contrib_total'})
        columns.append({'name': 'Total Investido', 'id': 'total_investido'})
        if show_split:
            columns.append({'name': 'Contrib. Total Acum.', 'id': 'contrib_total_acum'})
        if not df_pos.empty:
            columns.append({'name': 'Posição', 'id': 'posicao'})
        if is_inflation_on and deflator_dict:
            columns.append({'name': f'Deflator ({inflation_index})', 'id': 'deflator'})

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
