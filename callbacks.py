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
from calculator import calculate_summary_stats, generate_forecast, xirr_bizdays
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
            dropdown_style = {'color': '#000'}
            label_style = {'color': COLORS['text'], 'fontSize': '0.8rem', 'marginBottom': '0.25rem', 'display': 'block'}
        else:
            dropdown_style = {'color': '#000', 'opacity': '0.5'}
            label_style = {'color': COLORS['text_muted'], 'fontSize': '0.8rem', 'marginBottom': '0.25rem', 'display': 'block'}

        return (not is_enabled, not is_enabled,
                dropdown_style, dropdown_style,
                label_style, label_style)

    @callback(
        Output('forecast-years', 'disabled'),
        Output('forecast-years', 'style'),
        Output('forecast-years-label', 'style'),
        Output('growth-rate', 'disabled'),
        Output('growth-rate', 'style'),
        Output('growth-rate-label', 'style'),
        Input('forecast-toggle', 'value')
    )
    def toggle_forecast_controls(forecast_toggle):
        """Enable/disable forecast controls based on toggle."""
        is_enabled = 'enabled' in (forecast_toggle or [])

        if is_enabled:
            dropdown_style = {'color': '#000'}
            label_style = {'color': COLORS['text'], 'fontSize': '0.8rem', 'marginBottom': '0.25rem', 'display': 'block'}
        else:
            dropdown_style = {'color': '#000', 'opacity': '0.5'}
            label_style = {'color': COLORS['text_muted'], 'fontSize': '0.8rem', 'marginBottom': '0.25rem', 'display': 'block'}

        return (not is_enabled, dropdown_style, label_style,
                not is_enabled, dropdown_style, label_style)

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
        Output('forecast-data', 'data'),
        Input('scale-toggle', 'value'),
        Input('start-month', 'value'),
        Input('end-month', 'value'),
        Input('benchmark-select', 'value'),
        Input('overhead-select', 'value'),
        Input('company-as-mine-toggle', 'value'),
        Input('position-data', 'data'),
        Input('contributions-data', 'data'),
        Input('forecast-toggle', 'value'),
        Input('forecast-years', 'value'),
        Input('growth-rate', 'value'),
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
                              forecast_toggle, forecast_years, growth_rate,
                              inflation_toggle, inflation_index, inflation_ref_month,
                              contributions_original, date_range, cache, pdf_metadata):
        """Update the position graph and benchmark calculations."""
        if not position_data or not contributions_data:
            empty_fig = create_empty_figure("Carregue um PDF para visualizar")
            return (empty_fig, '--', {'color': COLORS['text_muted'], 'margin': '0.5rem 0'},
                    'Selecione um benchmark', cache or {}, None)

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
        bench_cagr = None  # For forecast
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

        # Generate forecast if toggle is ON
        forecast_nucleos = None
        forecast_benchmark = None
        forecast_store_data = None

        is_forecast_on = 'enabled' in (forecast_toggle or [])
        if is_forecast_on and forecast_years and not df_pos_filtered.empty:
            # IMPORTANT: For forecasting, always use the REAL fund CAGR
            # (calculated with total contributions), not the inflated
            # "company as mine" CAGR. The fund's growth rate is the same
            # regardless of how we account for contributions.
            last_date = df_pos_filtered['data'].iloc[-1]
            last_position = df_pos_filtered['posicao'].iloc[-1]

            # Calculate the REAL Nucleos CAGR using TOTAL contributions
            dates = df_contrib_filtered['data'].tolist() + [last_date]
            amounts = [-amt for amt in df_contrib_filtered['contribuicao_total'].tolist()] + [last_position]
            nucleos_cagr = xirr_bizdays(dates, amounts)

            if nucleos_cagr is not None:
                # Generate Nucleos forecast
                # Note: company_as_mine only affects accounting display,
                # not the actual growth (total × 1.85 is always invested)
                forecast_nucleos = generate_forecast(
                    df_pos_filtered,
                    df_contrib_filtered,
                    nucleos_cagr,
                    forecast_years,
                    growth_rate,
                    include_company_match=True  # Nucleos always gets company match
                )

                # Store forecast data for table display (will add benchmark later)
                if not forecast_nucleos.empty:
                    forecast_store_data = {
                        'nucleos': forecast_nucleos.to_dict('records'),
                        'benchmark': None
                    }

            # Generate benchmark forecast if benchmark is selected
            # The benchmark CAGR should be the REAL index growth rate,
            # regardless of "company as mine" toggle. We need to simulate
            # with total contributions to get the real benchmark performance.
            if benchmark_name and benchmark_name != 'none' and date_range:
                # Get benchmark data for forecast CAGR calculation
                cache_key = benchmark_name
                if cache_key in cache:
                    bench_raw = pd.DataFrame(cache[cache_key])
                else:
                    bench_raw = fetch_single_benchmark(
                        benchmark_name, date_range['start'], date_range['end']
                    )

                if bench_raw is not None:
                    # Apply overhead for consistency
                    bench_with_overhead = apply_overhead_to_benchmark(bench_raw, overhead)

                    # Simulate with TOTAL contributions (not participant only)
                    df_contrib_full = df_contrib_orig_filtered[['data']].copy()
                    df_contrib_full['contribuicao_total'] = df_contrib_orig_filtered['contribuicao_total']

                    if not df_contrib_full.empty:
                        first_month = df_contrib_full['data'].min().to_period('M')
                        pos_dates = df_pos_filtered[
                            df_pos_filtered['data'].dt.to_period('M') >= first_month
                        ][['data']].copy()
                    else:
                        pos_dates = df_pos_filtered[['data']].copy()

                    bench_sim_full = simulate_benchmark(
                        df_contrib_full, bench_with_overhead, pos_dates
                    )

                    # Apply inflation adjustment if enabled
                    if is_inflation_on and inflation_data is not None and not bench_sim_full.empty:
                        from calculator import deflate_series
                        bench_sim_full = deflate_series(bench_sim_full, inflation_data, inflation_ref_month, 'posicao')
                        bench_sim_full['posicao'] = bench_sim_full['posicao_real']
                        bench_sim_full = bench_sim_full.drop(columns=['posicao_real'])

                    if not bench_sim_full.empty:
                        bench_final_full = bench_sim_full['posicao'].iloc[-1]
                        # Use deflated contributions when inflation is ON for consistent CAGR
                        # df_contrib_filtered is already deflated by apply_inflation_adjustment callback
                        contrib_for_bench_cagr = df_contrib_filtered if is_inflation_on else df_contrib_full
                        bench_dates = contrib_for_bench_cagr['data'].tolist() + [last_date]
                        bench_amounts = [-amt for amt in contrib_for_bench_cagr['contribuicao_total'].tolist()] + [bench_final_full]
                        real_bench_cagr = xirr_bizdays(bench_dates, bench_amounts)

                        if real_bench_cagr is not None:
                            # Generate forecast starting from the displayed benchmark_sim
                            # When "company as mine" is ON, benchmark gets NO company match
                            # (counterfactual: you invested only YOUR money in the benchmark)
                            if benchmark_sim is not None and not benchmark_sim.empty:
                                treat_company_as_mine = 'as_mine' in (company_as_mine or [])
                                forecast_benchmark = generate_forecast(
                                    benchmark_sim,
                                    df_contrib_filtered,
                                    real_bench_cagr,
                                    forecast_years,
                                    growth_rate,
                                    include_company_match=not treat_company_as_mine
                                )
                                # Add benchmark forecast to store data
                                if forecast_store_data is not None and not forecast_benchmark.empty:
                                    forecast_store_data['benchmark'] = forecast_benchmark.to_dict('records')

        fig = create_position_figure(
            df_pos_filtered,
            log_scale=(scale == 'log'),
            benchmark_sim=benchmark_sim,
            benchmark_label=benchmark_label,
            forecast_data=forecast_nucleos,
            forecast_benchmark=forecast_benchmark
        )

        return fig, benchmark_cagr_text, benchmark_cagr_style, benchmark_label_text, cache, forecast_store_data

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
            'width': '100%',
            'textAlign': 'center',
            'padding': '0.75rem 1rem',
            'color': COLORS['text'],
            'border': 'none',
            'borderRadius': '0.5rem',
            'cursor': 'pointer',
            'marginBottom': '1rem',
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
            'marginTop': '0.5rem',
            'display': 'flex',
            'alignItems': 'center',
        }
        if pdf_metadata and pdf_metadata.get('is_partial'):
            base_style['display'] = 'flex'
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

    @callback(
        Output('forecast-table-section', 'style'),
        Input('forecast-toggle', 'value'),
    )
    def toggle_forecast_table_visibility(forecast_toggle):
        """Show/hide the forecast table section based on forecast toggle."""
        is_forecast_on = 'enabled' in (forecast_toggle or [])
        if is_forecast_on:
            # Show section immediately so loading spinner is visible
            return {'display': 'block', 'marginTop': '2rem'}
        return {'display': 'none'}

    @callback(
        Output('forecast-data-table', 'data'),
        Output('forecast-data-table', 'columns'),
        Input('forecast-data', 'data'),
        Input('company-as-mine-toggle', 'value'),
        Input('forecast-toggle', 'value'),
        State('contributions-data', 'data'),
    )
    def update_forecast_table(forecast_data, company_as_mine, forecast_toggle, contributions_data):
        """Populate forecast data table with projected positions and cumulative contributions."""
        is_forecast_on = 'enabled' in (forecast_toggle or [])

        if not forecast_data:
            if is_forecast_on:
                # Show placeholder while data is being computed
                return [{'data': 'Calculando projeção...', 'posicao': '', 'benchmark': '', 'total_contrib': ''}], [
                    {'name': 'Data', 'id': 'data'},
                    {'name': 'Posição (Projeção)', 'id': 'posicao'},
                    {'name': 'Simulado (Projeção)', 'id': 'benchmark'},
                    {'name': 'Contrib. Total Acum.', 'id': 'total_contrib'},
                ]
            return [], []

        # Handle new dict structure with 'nucleos' and 'benchmark' keys
        nucleos_data = forecast_data.get('nucleos', []) if isinstance(forecast_data, dict) else forecast_data
        benchmark_data = forecast_data.get('benchmark', []) if isinstance(forecast_data, dict) else []

        if not nucleos_data:
            return [], []

        # Get last cumulative contribution from historical data
        last_cumulative_total = 0
        last_cumulative_participant = 0
        if contributions_data:
            df_contrib = pd.DataFrame(contributions_data)
            last_cumulative_total = df_contrib['contribuicao_total'].sum()
            if 'contrib_participante' in df_contrib.columns:
                last_cumulative_participant = df_contrib['contrib_participante'].sum()

        treat_company_as_mine = 'as_mine' in (company_as_mine or [])

        # Build benchmark lookup by date
        benchmark_lookup = {}
        if benchmark_data:
            for b_row in benchmark_data:
                b_date = pd.to_datetime(b_row['data']).strftime('%b %Y')
                benchmark_lookup[b_date] = b_row['posicao']

        # Build table data with cumulative contributions
        table_data = []
        cumulative_total = last_cumulative_total
        cumulative_participant = last_cumulative_participant

        for fc_row in nucleos_data:
            fc_date = pd.to_datetime(fc_row['data'])
            fc_date_str = fc_date.strftime('%b %Y')
            monthly_total = fc_row.get('contribuicao_total_proj', 0)
            monthly_participant = fc_row.get('contrib_participante_proj', 0)

            cumulative_total += monthly_total
            cumulative_participant += monthly_participant

            row_data = {
                'data': fc_date_str,
                'posicao': f"R$ {fc_row['posicao']:,.2f}",
                'total_contrib': f"R$ {cumulative_total:,.2f}",
            }

            # Add benchmark projection if available
            if fc_date_str in benchmark_lookup:
                row_data['benchmark'] = f"R$ {benchmark_lookup[fc_date_str]:,.2f}"
            else:
                row_data['benchmark'] = '-'

            if treat_company_as_mine:
                row_data['participant_contrib'] = f"R$ {cumulative_participant:,.2f}"

            table_data.append(row_data)

        # Build columns
        columns = [
            {'name': 'Data', 'id': 'data'},
            {'name': 'Posição (Projeção)', 'id': 'posicao'},
            {'name': 'Simulado (Projeção)', 'id': 'benchmark'},
            {'name': 'Contrib. Total Acum.', 'id': 'total_contrib'},
        ]
        if treat_company_as_mine:
            columns.append({'name': 'Contrib. Participante Acum.', 'id': 'participant_contrib'})

        return table_data, columns

    @callback(
        Output('forecast-download', 'data'),
        Input('forecast-export-btn', 'n_clicks'),
        State('forecast-data-table', 'data'),
        State('forecast-export-format', 'value'),
        prevent_initial_call=True
    )
    def export_forecast_data(n_clicks, table_data, export_format):
        """Export forecast table data to CSV or Excel."""
        if not table_data:
            raise dash.exceptions.PreventUpdate

        df = pd.DataFrame(table_data)

        if export_format == 'csv':
            return dcc.send_data_frame(df.to_csv, 'nucleos_projecao.csv', index=False)
        else:
            return dcc.send_data_frame(df.to_excel, 'nucleos_projecao.xlsx', index=False, engine='openpyxl')

    @callback(
        Output('settings-panel', 'style'),
        Output('settings-overlay', 'style'),
        Output('settings-panel-open', 'data'),
        Output('settings-content', 'style'),
        Output('page-container', 'style'),
        Input('settings-btn', 'n_clicks'),
        Input('settings-close-btn', 'n_clicks'),
        Input('settings-ok-btn', 'n_clicks'),
        Input('settings-overlay', 'n_clicks'),
        State('settings-panel-open', 'data'),
        prevent_initial_call=True
    )
    def toggle_settings_panel(open_clicks, close_clicks, ok_clicks, overlay_clicks, is_open):
        """Toggle the settings panel visibility."""
        ctx = dash.callback_context
        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate

        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        # Determine new state
        if trigger_id == 'settings-btn':
            new_is_open = not is_open
        elif trigger_id in ['settings-close-btn', 'settings-ok-btn', 'settings-overlay']:
            new_is_open = False
        else:
            new_is_open = is_open

        # Panel style
        panel_base_style = {
            'position': 'fixed',
            'top': '0',
            'right': '0',
            'width': '320px',
            'height': '100vh',
            'backgroundColor': COLORS['background'],
            'boxShadow': '-4px 0 20px rgba(0, 0, 0, 0.3)',
            'transition': 'transform 0.3s ease',
            'zIndex': '1000',
            'display': 'flex',
            'flexDirection': 'column',
        }

        if new_is_open:
            panel_base_style['transform'] = 'translateX(0)'
        else:
            panel_base_style['transform'] = 'translateX(100%)'

        # Overlay style
        overlay_style = {
            'position': 'fixed',
            'top': '0',
            'left': '0',
            'right': '0',
            'bottom': '0',
            'backgroundColor': 'rgba(0, 0, 0, 0.5)',
            'zIndex': '999',
            'display': 'block' if new_is_open else 'none',
        }

        # Content style - force scroll to top when opening by changing a property
        content_style = {
            'padding': '1.25rem',
            'overflowY': 'auto',
            'flex': '1',
        }

        # Page container style - lock scroll when panel is open
        page_style = {
            'backgroundColor': COLORS['background'],
            'overflow': 'hidden' if new_is_open else 'auto',
            'height': '100vh' if new_is_open else 'auto',
        }

        return panel_base_style, overlay_style, new_is_open, content_style, page_style

    @callback(
        Output('settings-panel', 'style', allow_duplicate=True),
        Output('settings-overlay', 'style', allow_duplicate=True),
        Output('settings-panel-open', 'data', allow_duplicate=True),
        Output('settings-content', 'style', allow_duplicate=True),
        Output('page-container', 'style', allow_duplicate=True),
        Input('settings-panel-open', 'data'),
        prevent_initial_call='initial_duplicate'
    )
    def sync_settings_panel_on_load(is_open):
        """Sync settings panel state on page load."""
        # Panel style
        panel_base_style = {
            'position': 'fixed',
            'top': '0',
            'right': '0',
            'width': '320px',
            'height': '100vh',
            'backgroundColor': COLORS['background'],
            'boxShadow': '-4px 0 20px rgba(0, 0, 0, 0.3)',
            'transition': 'transform 0.3s ease',
            'zIndex': '1000',
            'display': 'flex',
            'flexDirection': 'column',
        }

        if is_open:
            panel_base_style['transform'] = 'translateX(0)'
        else:
            panel_base_style['transform'] = 'translateX(100%)'

        # Overlay style
        overlay_style = {
            'position': 'fixed',
            'top': '0',
            'left': '0',
            'right': '0',
            'bottom': '0',
            'backgroundColor': 'rgba(0, 0, 0, 0.5)',
            'zIndex': '999',
            'display': 'block' if is_open else 'none',
        }

        # Content style
        content_style = {
            'padding': '1.25rem',
            'overflowY': 'auto',
            'flex': '1',
        }

        # Page container style - lock scroll when panel is open
        page_style = {
            'backgroundColor': COLORS['background'],
            'overflow': 'hidden' if is_open else 'auto',
            'height': '100vh' if is_open else 'auto',
        }

        return panel_base_style, overlay_style, is_open, content_style, page_style
