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


def get_value_on_date(df: pd.DataFrame, target_date: pd.Timestamp) -> float | None:
    """
    Get the index value on or before a specific date.

    Uses forward-fill logic: if exact date not found,
    uses the most recent available value.
    """
    target_date = pd.Timestamp(target_date).normalize()
    df = df.copy()
    df['date'] = pd.to_datetime(df['date']).dt.normalize()

    # Filter to dates on or before target
    available = df[df['date'] <= target_date]

    if available.empty:
        return None

    return available.iloc[-1]['value']


def simulate_benchmark(contributions: pd.DataFrame,
                       benchmark_data: pd.DataFrame,
                       position_dates: pd.DataFrame) -> pd.DataFrame:
    """
    Simulate what contributions would be worth if invested in a benchmark.

    For each contribution, calculates how many "units" of the benchmark
    could be bought, then values the total holdings at each position date.

    Args:
        contributions: DataFrame with 'data' (date) and 'contribuicao_total' columns
        benchmark_data: DataFrame with 'date' and 'value' columns
        position_dates: DataFrame with 'data' column (dates to calculate value for)

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
                # Get benchmark value on contribution date
                bench_value = get_value_on_date(benchmark_data, contrib_date)
                if bench_value is not None and bench_value > 0:
                    # Buy units of the benchmark
                    units_bought = contrib_row['contribuicao_total'] / bench_value
                    units_held += units_bought
                contrib_idx += 1
            else:
                break

        # Value holdings at position date
        current_value = get_value_on_date(benchmark_data, pos_date)
        if current_value is not None:
            position_value = units_held * current_value
        else:
            position_value = 0

        results.append({
            'data': pos_date,
            'posicao': position_value
        })

    return pd.DataFrame(results)


def fetch_all_benchmarks(start_date: str, end_date: str = None) -> dict[str, pd.DataFrame]:
    """
    Fetch all benchmark data.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        Dictionary mapping benchmark names to DataFrames
    """
    # Fetch with some buffer before start_date for lookback
    buffer_start = (pd.to_datetime(start_date) - timedelta(days=30)).strftime('%Y-%m-%d')

    benchmarks = {}

    print("Fetching CDI...")
    try:
        benchmarks['CDI'] = fetch_cdi(buffer_start, end_date)
    except Exception as e:
        print(f"  Warning: Could not fetch CDI: {e}")

    print("Fetching IPCA...")
    try:
        benchmarks['IPCA'] = fetch_ipca(buffer_start, end_date)
    except Exception as e:
        print(f"  Warning: Could not fetch IPCA: {e}")

    print("Fetching INPC...")
    try:
        benchmarks['INPC'] = fetch_inpc(buffer_start, end_date)
    except Exception as e:
        print(f"  Warning: Could not fetch INPC: {e}")

    print("Fetching S&P 500 TR...")
    try:
        benchmarks['S&P 500'] = fetch_sp500tr(buffer_start, end_date)
    except Exception as e:
        print(f"  Warning: Could not fetch S&P 500 TR: {e}")

    print("Fetching USD/BRL...")
    try:
        benchmarks['USD'] = fetch_usd(buffer_start, end_date)
    except Exception as e:
        print(f"  Warning: Could not fetch USD/BRL: {e}")

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
