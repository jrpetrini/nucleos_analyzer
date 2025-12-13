#!/usr/bin/env python3
"""
Benchmark data fetching and simulation for Nucleos Analyzer.

Fetches historical data for various indices and simulates
what contributions would be worth if invested in each benchmark.
"""

import pandas as pd
import yfinance as yf
from bcb import sgs
from datetime import datetime, timedelta


# BCB Series codes
BCB_SERIES = {
    'CDI': 12,      # CDI daily rate
    'IPCA': 433,    # IPCA monthly
    'INPC': 188,    # INPC monthly
}

# Yahoo Finance tickers
YFINANCE_TICKERS = {
    'SP500TR': '^SP500TR',   # S&P 500 Total Return
    'USD': 'USDBRL=X',       # USD/BRL exchange rate
}


def fetch_bcb_series(series_code: int, start_date: str, end_date: str = None) -> pd.Series:
    """
    Fetch a series from BCB (Banco Central do Brasil).

    Args:
        series_code: BCB SGS series code
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD), defaults to today

    Returns:
        pandas Series with the data
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    data = sgs.get({'series': series_code}, start=start_date, end=end_date)
    return data['series']


def fetch_cdi(start_date: str, end_date: str = None) -> pd.DataFrame:
    """
    Fetch CDI accumulated index from BCB.

    Returns DataFrame with 'date' and 'value' columns,
    where 'value' is the accumulated CDI factor (starts at 1).
    """
    daily_rate = fetch_bcb_series(BCB_SERIES['CDI'], start_date, end_date)

    # Convert daily rate to accumulated factor
    # CDI is given as daily % rate, so we compound it
    daily_factor = 1 + (daily_rate / 100)
    accumulated = daily_factor.cumprod()

    # Normalize to start at 1
    accumulated = accumulated / accumulated.iloc[0]

    df = pd.DataFrame({
        'date': accumulated.index,
        'value': accumulated.values
    })
    df['date'] = pd.to_datetime(df['date'])
    return df


def fetch_ipca(start_date: str, end_date: str = None) -> pd.DataFrame:
    """
    Fetch IPCA accumulated index from BCB.

    Returns DataFrame with 'date' and 'value' columns,
    where 'value' is the accumulated IPCA factor (starts at 1).
    """
    monthly_rate = fetch_bcb_series(BCB_SERIES['IPCA'], start_date, end_date)

    # Convert monthly rate to accumulated factor
    monthly_factor = 1 + (monthly_rate / 100)
    accumulated = monthly_factor.cumprod()

    # Normalize to start at 1
    accumulated = accumulated / accumulated.iloc[0]

    df = pd.DataFrame({
        'date': accumulated.index,
        'value': accumulated.values
    })
    df['date'] = pd.to_datetime(df['date'])
    return df


def fetch_inpc(start_date: str, end_date: str = None) -> pd.DataFrame:
    """
    Fetch INPC accumulated index from BCB.

    Returns DataFrame with 'date' and 'value' columns,
    where 'value' is the accumulated INPC factor (starts at 1).
    """
    monthly_rate = fetch_bcb_series(BCB_SERIES['INPC'], start_date, end_date)

    # Convert monthly rate to accumulated factor
    monthly_factor = 1 + (monthly_rate / 100)
    accumulated = monthly_factor.cumprod()

    # Normalize to start at 1
    accumulated = accumulated / accumulated.iloc[0]

    df = pd.DataFrame({
        'date': accumulated.index,
        'value': accumulated.values
    })
    df['date'] = pd.to_datetime(df['date'])
    return df


def fetch_sp500tr(start_date: str, end_date: str = None) -> pd.DataFrame:
    """
    Fetch S&P 500 Total Return index from Yahoo Finance.

    Returns DataFrame with 'date' and 'value' columns.
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    ticker = yf.Ticker(YFINANCE_TICKERS['SP500TR'])
    hist = ticker.history(start=start_date, end=end_date)

    if hist.empty:
        raise ValueError("No S&P 500 TR data found for the given date range")

    df = pd.DataFrame({
        'date': hist.index.tz_localize(None),
        'value': hist['Close'].values
    })
    df['date'] = pd.to_datetime(df['date'])
    return df


def fetch_usd(start_date: str, end_date: str = None) -> pd.DataFrame:
    """
    Fetch USD/BRL exchange rate from Yahoo Finance.

    Returns DataFrame with 'date' and 'value' columns.
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    ticker = yf.Ticker(YFINANCE_TICKERS['USD'])
    hist = ticker.history(start=start_date, end=end_date)

    if hist.empty:
        raise ValueError("No USD/BRL data found for the given date range")

    df = pd.DataFrame({
        'date': hist.index.tz_localize(None),
        'value': hist['Close'].values
    })
    df['date'] = pd.to_datetime(df['date'])
    return df


def get_value_on_date(df: pd.DataFrame, target_date: pd.Timestamp,
                       extrapolate_annual_rate: float = None) -> tuple[float | None, pd.Timestamp | None]:
    """
    Get the index value for a specific date, with interpolation and extrapolation.

    For dates between available data points: uses geometric interpolation
    (assumes continuous compound growth between points).

    For dates beyond available data: extrapolates using the provided annual rate,
    or uses the average historical rate if not provided.

    Uses 252 business days per year convention, approximated from calendar days
    using the ratio (252/365). This provides consistent results across all
    calculations without requiring calendar lookups.

    Returns:
        tuple: (value, actual_date) where actual_date is the reference date used
    """
    target_date = pd.Timestamp(target_date).normalize()
    df = df.copy()
    df['date'] = pd.to_datetime(df['date']).dt.normalize()
    df = df.sort_values('date').reset_index(drop=True)

    if df.empty:
        return None, None

    # Check if target is before first data point
    if target_date < df['date'].iloc[0]:
        return None, None

    # Check if target is after last data point - need to extrapolate
    last_date = df['date'].iloc[-1]
    if target_date > last_date:
        last_value = df['value'].iloc[-1]

        # Calculate extrapolation rate using 252 business days/year convention
        if extrapolate_annual_rate is not None:
            annual_rate = extrapolate_annual_rate
        elif len(df) > 1:
            # Use historical average rate from the data
            first_value = df['value'].iloc[0]
            first_date = df['date'].iloc[0]
            # Approximate business days using 252/365 ratio
            calendar_days = (last_date - first_date).days
            years = (calendar_days * 252 / 365) / 252  # = calendar_days / 365

            if years > 0 and first_value > 0:
                annual_rate = ((last_value / first_value) ** (1 / years) - 1) * 100
            else:
                annual_rate = 0
        else:
            annual_rate = 0

        # Extrapolate using approximate business days
        calendar_days_diff = (target_date - last_date).days
        biz_days_diff = calendar_days_diff * (252 / 365)
        annual_factor = 1 + (annual_rate / 100)
        value = last_value * (annual_factor ** (biz_days_diff / 252))

        return value, last_date

    # Find surrounding data points for interpolation
    before = df[df['date'] <= target_date]
    after = df[df['date'] > target_date]

    if before.empty:
        return None, None

    prev_row = before.iloc[-1]
    prev_date = prev_row['date']
    prev_value = prev_row['value']

    # Exact match
    if prev_date == target_date:
        return prev_value, prev_date

    # Interpolate between prev and next using geometric mean
    if not after.empty:
        next_row = after.iloc[0]
        next_date = next_row['date']
        next_value = next_row['value']

        total_days = (next_date - prev_date).days
        days_from_prev = (target_date - prev_date).days

        if total_days > 0 and prev_value > 0 and next_value > 0:
            # Geometric interpolation: value = prev * (next/prev)^(fraction)
            # Note: fraction is the same whether using calendar or business days
            fraction = days_from_prev / total_days
            value = prev_value * ((next_value / prev_value) ** fraction)
            return value, target_date

    # Fallback to previous value
    return prev_value, prev_date


def simulate_benchmark(contributions: pd.DataFrame,
                       benchmark_data: pd.DataFrame,
                       position_dates: pd.DataFrame,
                       extrapolate_annual_rate: float = None) -> pd.DataFrame:
    """
    Simulate what contributions would be worth if invested in a benchmark.

    For each contribution, calculates how many "units" of the benchmark
    could be bought, then values the total holdings at each position date.

    Args:
        contributions: DataFrame with 'data' (date) and 'contribuicao_total' columns
        benchmark_data: DataFrame with 'date' and 'value' columns
        position_dates: DataFrame with 'data' column (dates to calculate value for)
        extrapolate_annual_rate: Annual rate (%) to extrapolate if position date
                                  is beyond available benchmark data

    Returns:
        DataFrame with 'data' and 'posicao' columns showing simulated wealth
    """
    units_held = 0.0
    results = []

    # Sort contributions by date
    contributions = contributions.sort_values('data').copy()
    position_dates = position_dates.sort_values('data').copy()

    # Track which contributions have been made
    contrib_idx = 0
    n_contribs = len(contributions)

    for _, pos_row in position_dates.iterrows():
        pos_date = pos_row['data']

        # Add any contributions made on or before this position date
        while contrib_idx < n_contribs:
            contrib_row = contributions.iloc[contrib_idx]
            contrib_date = contrib_row['data']

            if contrib_date <= pos_date:
                # Get benchmark value on contribution date (with extrapolation if needed)
                bench_value, _ = get_value_on_date(
                    benchmark_data, contrib_date,
                    extrapolate_annual_rate=extrapolate_annual_rate
                )
                if bench_value is not None and bench_value > 0:
                    # Buy units of the benchmark
                    units_bought = contrib_row['contribuicao_total'] / bench_value
                    units_held += units_bought
                contrib_idx += 1
            else:
                break

        # Value holdings at position date (with extrapolation if needed)
        current_value, _ = get_value_on_date(
            benchmark_data, pos_date,
            extrapolate_annual_rate=extrapolate_annual_rate
        )
        if current_value is not None:
            position_value = units_held * current_value
        else:
            position_value = 0

        results.append({
            'data': pos_date,
            'posicao': position_value
        })

    return pd.DataFrame(results)


def apply_overhead_to_benchmark(benchmark_data: pd.DataFrame, annual_overhead_pct: float) -> pd.DataFrame:
    """
    Apply an annual overhead percentage to benchmark data.

    For example, if the benchmark is INPC and overhead is 4%,
    this simulates investing in "INPC + 4% a.a."

    Uses 252 business days per year convention, approximated from calendar days
    using the ratio (252/365). This provides consistent results across all
    calculations without requiring calendar lookups.

    Args:
        benchmark_data: DataFrame with 'date' and 'value' columns
        annual_overhead_pct: Annual overhead in percentage (e.g., 4 for 4%)

    Returns:
        DataFrame with adjusted values
    """
    if annual_overhead_pct == 0:
        return benchmark_data.copy()

    df = benchmark_data.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # Calculate approximate business days using 252/365 ratio
    first_date = df['date'].iloc[0]
    df['calendar_days'] = (df['date'] - first_date).dt.days
    df['biz_days'] = df['calendar_days'] * (252 / 365)

    # Apply compound overhead: value * (1 + overhead)^(biz_days/252)
    annual_factor = 1 + (annual_overhead_pct / 100)
    df['value'] = df['value'] * (annual_factor ** (df['biz_days'] / 252))

    return df[['date', 'value']]


BENCHMARK_FETCHERS = {
    'CDI': fetch_cdi,
    'IPCA': fetch_ipca,
    'INPC': fetch_inpc,
    'S&P 500': fetch_sp500tr,
    'USD': fetch_usd,
}

AVAILABLE_BENCHMARKS = list(BENCHMARK_FETCHERS.keys())


def fetch_single_benchmark(name: str, start_date: str, end_date: str = None) -> pd.DataFrame | None:
    """
    Fetch a single benchmark by name.

    Args:
        name: Benchmark name (CDI, IPCA, INPC, S&P 500, USD)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with 'date' and 'value' columns, or None if fetch fails
    """
    if name not in BENCHMARK_FETCHERS:
        return None

    # Fetch with some buffer before start_date for lookback
    buffer_start = (pd.to_datetime(start_date) - timedelta(days=30)).strftime('%Y-%m-%d')

    try:
        return BENCHMARK_FETCHERS[name](buffer_start, end_date)
    except Exception as e:
        print(f"Warning: Could not fetch {name}: {e}")
        return None


def fetch_all_benchmarks(start_date: str, end_date: str = None) -> dict[str, pd.DataFrame]:
    """
    Fetch all benchmark data.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        Dictionary mapping benchmark names to DataFrames
    """
    benchmarks = {}

    for name in AVAILABLE_BENCHMARKS:
        print(f"Fetching {name}...")
        data = fetch_single_benchmark(name, start_date, end_date)
        if data is not None:
            benchmarks[name] = data

    return benchmarks


def simulate_all_benchmarks(contributions: pd.DataFrame,
                            position_dates: pd.DataFrame,
                            benchmarks: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """
    Simulate contributions invested in all benchmarks.

    Args:
        contributions: DataFrame with 'data' and 'contribuicao_total'
        position_dates: DataFrame with 'data' column
        benchmarks: Dictionary of benchmark DataFrames

    Returns:
        Dictionary mapping benchmark names to simulated position DataFrames
    """
    simulations = {}

    for name, bench_data in benchmarks.items():
        print(f"Simulating {name}...")
        try:
            simulations[name] = simulate_benchmark(contributions, bench_data, position_dates)
        except Exception as e:
            print(f"  Warning: Could not simulate {name}: {e}")

    return simulations
