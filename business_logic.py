#!/usr/bin/env python3
"""
Business logic extracted from dashboard.py for better testability.

This module contains the core business logic that was previously embedded
in dashboard callbacks, now separated for easier testing and maintenance.
"""

import pandas as pd
from calculator import xirr_bizdays
from benchmarks import (
    fetch_single_benchmark,
    apply_overhead_to_benchmark,
    simulate_benchmark,
)
from dashboard_helpers import (
    prepare_dataframe,
    is_company_as_mine,
    get_contribution_column,
    prepare_benchmark_contributions,
    build_deflator_dict,
    format_currency,
    format_percentage,
    get_cagr_color,
    get_return_color,
)


def filter_data_by_range(df_pos: pd.DataFrame, df_contrib: pd.DataFrame,
                          start_date: str, end_date: str) -> tuple:
    """
    Filter position and contribution data to the selected date range.
    Adjusts position values to be relative to the position before the start date.

    Args:
        df_pos: Position DataFrame with 'data' and 'posicao' columns
        df_contrib: Contribution DataFrame with 'data' column
        start_date: Start date as ISO string
        end_date: End date as ISO string

    Returns:
        tuple: (df_pos_filtered, df_contrib_filtered, position_before_start, date_before_start)
               date_before_start is None if there's no previous month (first month selected)
    """
    # Handle empty DataFrames
    if df_pos.empty or df_contrib.empty:
        return df_pos.copy(), df_contrib.copy(), 0, None

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


def calculate_nucleos_stats(df_contrib: pd.DataFrame, df_pos: pd.DataFrame,
                            start_date: str, end_date: str,
                            company_as_mine: bool, colors: dict,
                            missing_cotas: float = 0.0) -> dict:
    """
    Calculate Nucleos stats (position, invested, CAGR, return).

    Extracted from update_nucleos_stats callback.

    Args:
        df_contrib: Contribution DataFrame
        df_pos: Position DataFrame
        start_date: Start date ISO string
        end_date: End date ISO string
        company_as_mine: Whether to treat company contributions as "free"
        colors: Color palette dictionary
        missing_cotas: For partial PDFs, the number of cotas from prior history

    Returns:
        dict with keys: position_label, position_value, invested_value,
                       cagr_text, cagr_style, return_text, return_style
    """
    # Filter data using helper function
    df_pos_filtered, df_contrib_filtered, position_before_start, date_before_start = filter_data_by_range(
        df_pos, df_contrib, start_date, end_date
    )

    if df_pos_filtered.empty:
        return _empty_nucleos_stats(colors)

    # Determine which contribution column to use
    contrib_col = get_contribution_column(df_contrib_filtered, company_as_mine)

    # Calculate total invested within date range
    total_invested_in_range = df_contrib_filtered[contrib_col].sum() if not df_contrib_filtered.empty else 0

    # Get period boundaries for time-weighted calculation
    period_start = date_before_start if date_before_start is not None else df_pos_filtered['data'].iloc[0]
    period_end = df_pos_filtered['data'].iloc[-1]
    end_position_original = df_pos_filtered['posicao'].iloc[-1] + position_before_start

    # DYNAMIC PARTIAL DETECTION:
    # When start date is changed (position_before_start > 0), calculate equivalent
    # missing_cotas. This unifies behavior between:
    # - Actual partial PDFs (missing_cotas from SALDO_TOTAL discrepancy)
    # - Full PDFs with start date filter (equivalent missing_cotas from position_before_start)
    #
    # Note: position_before_start already INCLUDES the value of any existing missing_cotas.
    # So cotas_before_start REPLACES missing_cotas, not adds to it.
    if position_before_start > 0 and 'valor_cota' in df_pos.columns:
        start_dt = df_pos_filtered['data'].iloc[0]
        df_before = df_pos[df_pos['data'] < start_dt]
        if not df_before.empty and 'valor_cota' in df_before.columns:
            valor_cota_start = df_before['valor_cota'].iloc[-1]
            # Cotas that existed before the filtered start date (includes any original missing_cotas)
            cotas_before_start = position_before_start / valor_cota_start
            # Replace missing_cotas - cotas_before_start already accounts for original missing_cotas
            missing_cotas = cotas_before_start

    # Exclude the value of invisible cotas from positions for CAGR calculation
    # This applies to both partial PDFs and full PDFs with start date filter
    if missing_cotas > 0 and 'valor_cota' in df_pos_filtered.columns:
        valor_cota_end = df_pos_filtered['valor_cota'].iloc[-1]
        invisible_position_end = missing_cotas * valor_cota_end

        # Adjusted positions exclude invisible cotas
        adjusted_end_position = end_position_original - invisible_position_end
        adjusted_start_position = 0  # All invisible cotas are now accounted for in missing_cotas
    else:
        adjusted_end_position = end_position_original
        adjusted_start_position = position_before_start
        invisible_position_end = 0

    # Calculate time-weighted position for this period's contributions
    _, position_from_contributions = calculate_time_weighted_position(
        df_contrib_filtered,
        start_position=adjusted_start_position,
        end_position=adjusted_end_position,
        period_start=period_start,
        period_end=period_end,
        contribution_col=contrib_col
    )

    # Position card shows TOTAL position (what user actually has)
    # This matches the graph and SALDO TOTAL from the PDF
    position_display = end_position_original

    # Total return = what visible contributions grew to minus what was invested
    # (For partial PDFs, this is the return on visible contributions only)
    total_return = position_from_contributions - total_invested_in_range

    # Calculate XIRR for the selected period
    amounts_for_xirr = df_contrib_filtered[contrib_col].tolist() if not df_contrib_filtered.empty else []

    # Build cash flows: contributions (outflows) + final position of visible contributions (inflow)
    contrib_dates = df_contrib_filtered['data'].tolist() if not df_contrib_filtered.empty else []
    contrib_amounts = [-amt for amt in amounts_for_xirr]

    dates = contrib_dates + [period_end]
    amounts = contrib_amounts + [position_from_contributions]

    cagr = xirr_bizdays(dates, amounts)
    cagr_pct = cagr * 100 if cagr is not None else None

    # Format values
    position_text = format_currency(position_display)
    invested_text = format_currency(total_invested_in_range)
    cagr_text = format_percentage(cagr_pct) if cagr_pct is not None else 'N/A'
    return_text = f'{format_currency(total_return)} total'

    # Get colors
    cagr_color = get_cagr_color(cagr_pct, colors)
    return_color = get_return_color(total_return, colors)

    # Format position label with end date
    position_label = f"Posição em {period_end.strftime('%m/%Y')}"

    # Format invested label with date range
    start_month_str = period_start.strftime('%m/%Y')
    end_month_str = period_end.strftime('%m/%Y')
    if start_month_str == end_month_str:
        invested_label = f"Investido em {end_month_str}"
    else:
        invested_label = f"Investido de {start_month_str} a {end_month_str}"

    return {
        'position_label': position_label,
        'position_value': position_text,
        'invested_label': invested_label,
        'invested_value': invested_text,
        'cagr_text': cagr_text,
        'cagr_style': {'color': cagr_color, 'margin': '0.5rem 0'},
        'return_text': return_text,
        'return_style': {'color': return_color, 'margin': '0', 'fontSize': '0.875rem'},
    }


def _empty_nucleos_stats(colors: dict) -> dict:
    """Return empty stats structure."""
    return {
        'position_label': 'Posição',
        'position_value': 'R$ 0,00',
        'invested_label': 'Total Investido',
        'invested_value': 'R$ 0,00',
        'cagr_text': 'N/A',
        'cagr_style': {'color': colors.get('text_muted', '#94a3b8'), 'margin': '0.5rem 0'},
        'return_text': 'R$ 0,00 total',
        'return_style': {'color': colors.get('text_muted', '#94a3b8'), 'margin': '0', 'fontSize': '0.875rem'},
    }


def simulate_and_calculate_benchmark(df_contrib: pd.DataFrame, df_pos: pd.DataFrame,
                                      benchmark_name: str, overhead: float,
                                      date_range: dict, cache: dict,
                                      company_as_mine: bool, colors: dict,
                                      inflation_data: pd.DataFrame = None,
                                      inflation_ref_month: str = None) -> dict:
    """
    Fetch, simulate benchmark and calculate CAGR.

    Extracted from update_position_graph callback.

    Args:
        df_contrib: Contribution DataFrame (original, not deflated)
        df_pos: Position DataFrame (filtered)
        benchmark_name: Benchmark name (CDI, IPCA, etc.)
        overhead: Overhead percentage
        date_range: Dict with 'start' and 'end' date strings
        cache: Benchmark data cache dict
        company_as_mine: Whether to use only participant contributions
        colors: Color palette dictionary
        inflation_data: Inflation index data for deflation (optional)
        inflation_ref_month: Reference month for deflation (optional)

    Returns:
        dict with keys: simulation_df, cagr_text, cagr_style, label_text, cache
    """
    result = {
        'simulation_df': None,
        'cagr_text': '--',
        'cagr_style': {'color': colors.get('text_muted', '#94a3b8'), 'margin': '0.5rem 0'},
        'label_text': 'Selecione um benchmark',
        'cache': cache or {},
    }

    if not benchmark_name or benchmark_name == 'none':
        return result

    if df_contrib.empty or df_pos.empty:
        return result

    # Check cache first
    cache_key = benchmark_name
    if cache_key in result['cache']:
        benchmark_raw = pd.DataFrame(result['cache'][cache_key])
    else:
        # Fetch benchmark data
        benchmark_raw = fetch_single_benchmark(
            benchmark_name,
            date_range['start'],
            date_range['end']
        )
        if benchmark_raw is not None:
            result['cache'][cache_key] = benchmark_raw.to_dict('records')

    if benchmark_raw is None:
        return result

    # Apply overhead
    benchmark_with_overhead = apply_overhead_to_benchmark(benchmark_raw, overhead)

    # Create label
    if overhead > 0:
        benchmark_label = f'{benchmark_name} +{overhead}%'
    else:
        benchmark_label = benchmark_name

    # Prepare contributions for simulation
    df_contrib_sim = prepare_benchmark_contributions(df_contrib, company_as_mine)

    # Filter position dates to start from first contribution month
    if not df_contrib_sim.empty:
        first_contrib_month = df_contrib_sim['data'].min().to_period('M')
        position_dates_for_bench = df_pos[
            df_pos['data'].dt.to_period('M') >= first_contrib_month
        ][['data']].copy()
    else:
        position_dates_for_bench = df_pos[['data']].copy()

    # Simulate benchmark
    benchmark_sim = simulate_benchmark(
        df_contrib_sim,
        benchmark_with_overhead,
        position_dates_for_bench
    )

    # If inflation is ON, deflate the simulated benchmark position
    if inflation_data is not None and not benchmark_sim.empty and inflation_ref_month:
        from calculator import deflate_series
        benchmark_sim = deflate_series(benchmark_sim, inflation_data, inflation_ref_month, 'posicao')
        benchmark_sim['posicao'] = benchmark_sim['posicao_real']
        benchmark_sim = benchmark_sim.drop(columns=['posicao_real'])

    result['simulation_df'] = benchmark_sim

    # Calculate benchmark value and CAGR
    if not benchmark_sim.empty:
        benchmark_final_value = benchmark_sim['posicao'].iloc[-1]
        last_date = df_pos['data'].iloc[-1]

        # Calculate CAGR
        contrib_col = get_contribution_column(df_contrib, company_as_mine)
        dates = df_contrib['data'].tolist() + [last_date]
        amounts = [-amt for amt in df_contrib[contrib_col].tolist()] + [benchmark_final_value]
        bench_cagr = xirr_bizdays(dates, amounts)

        if bench_cagr is not None:
            bench_cagr_pct = bench_cagr * 100
            result['cagr_text'] = format_percentage(bench_cagr_pct)
            result['cagr_style'] = {
                'color': get_cagr_color(bench_cagr_pct, colors),
                'margin': '0.5rem 0'
            }
        else:
            result['cagr_text'] = 'N/A'

        result['label_text'] = f'Posição {benchmark_label}: {format_currency(benchmark_final_value)}'

    return result


def get_position_dates_for_benchmark(df_pos: pd.DataFrame, df_contrib_sim: pd.DataFrame) -> pd.DataFrame:
    """
    Get position dates for benchmark simulation, aligned with contributions.

    Args:
        df_pos: Position DataFrame
        df_contrib_sim: Contribution DataFrame prepared for simulation

    Returns:
        DataFrame with 'data' column for benchmark simulation dates
    """
    if df_contrib_sim.empty:
        return df_pos[['data']].copy()

    first_contrib_month = df_contrib_sim['data'].min().to_period('M')
    return df_pos[
        df_pos['data'].dt.to_period('M') >= first_contrib_month
    ][['data']].copy()
