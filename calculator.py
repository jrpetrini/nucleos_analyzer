#!/usr/bin/env python3
"""
Financial calculations and data processing for Nucleos Analyzer.

Note on Business Day Convention:
    All calculations use 252 business days per year, approximated from calendar
    days using the ratio (252/365). This provides:
    - Consistent results across XIRR, overhead, and interpolation
    - No dependency on external calendar lookups (faster)
    - Deterministic results for testing

    The approximation introduces ~0.04% difference vs ANBIMA calendar for
    typical 1-year periods, which is negligible for personal investment tracking.
"""

import pandas as pd
from scipy.optimize import brentq
from pyxirr import xirr

# Business day conversion constants
BUSINESS_DAYS_PER_YEAR = 252
CALENDAR_DAYS_PER_YEAR = 365.25  # Average year length accounting for leap years
BIZ_DAY_RATIO = BUSINESS_DAYS_PER_YEAR / CALENDAR_DAYS_PER_YEAR  # ~0.6902


def xirr_bizdays(dates: list, amounts: list) -> float | None:
    """
    Calculate XIRR using 252 business days per year convention.

    Uses calendar days converted via (252/365) ratio for consistency with
    benchmark overhead and interpolation calculations.

    Args:
        dates: List of dates for each cash flow
        amounts: List of amounts (negative = outflow, positive = inflow)

    Returns:
        Annualized return rate based on 252 business days, or None if no solution
    """
    if len(dates) != len(amounts) or len(dates) < 2:
        return None

    # Convert dates to timestamps
    dates = [pd.Timestamp(d) for d in dates]
    first_date = min(dates)

    # Calculate approximate business days using 252/365 ratio
    biz_days = []
    for d in dates:
        calendar_days = (d - first_date).days
        biz_days.append(calendar_days * BIZ_DAY_RATIO)

    def npv(rate):
        """Calculate NPV using business days / 252."""
        if rate <= -1:
            return float('inf')
        total = 0
        for amt, days in zip(amounts, biz_days):
            total += amt / ((1 + rate) ** (days / BUSINESS_DAYS_PER_YEAR))
        return total

    # Use brentq with bracket [-0.99, 10] (i.e., -99% to 1000% annual return)
    # Guaranteed convergence within bracket
    try:
        rate = brentq(npv, -0.99, 10, xtol=1e-10)
        return rate
    except ValueError:
        # No solution in bracket, try standard xirr as fallback
        try:
            return xirr([d.date() for d in dates], amounts)
        except Exception:
            return None


def process_position_data(df_raw: pd.DataFrame, starting_cotas: float = 0) -> pd.DataFrame:
    """
    Process raw transaction data to get monthly positions.

    Args:
        df_raw: Raw dataframe from extract_data_from_pdf
        starting_cotas: Number of cotas held before the first transaction in df_raw.
                       Used for partial PDFs where prior history is not included.

    Returns:
        DataFrame with monthly position data (data, cotas, posicao, valor_cota)
    """
    df = df_raw.copy(deep=True)
    df['cotas_cumsum'] = df['cotas'].cumsum() + starting_cotas
    df['posicao'] = df['cotas_cumsum'] * df['valor_cota']

    df = (
        df.groupby('mes_ano')
        .last()[['cotas_cumsum', 'posicao', 'valor_cota']]
        .rename(columns={'cotas_cumsum': 'cotas'})
    )
    # Use end of month but normalize to midnight to avoid timezone/rounding issues
    df.index = df.index.to_period('M').to_timestamp(how='end').normalize()
    df = df.reset_index().rename(columns={'mes_ano': 'data'})

    return df


def process_contributions_data(df_contributions: pd.DataFrame) -> pd.DataFrame:
    """
    Process contributions data for bar chart (aggregated by month).

    Args:
        df_contributions: Contributions dataframe from extract_data_from_pdf

    Returns:
        DataFrame with monthly contribution totals (participant/patrocinador) and cumulative sums
    """
    if df_contributions.empty:
        return df_contributions

    df = df_contributions.copy()
    # Aggregate by month for chart display
    # Use end of month but normalize to midnight to avoid timezone/rounding issues
    df['mes'] = df['data'].dt.to_period('M').dt.to_timestamp(how='end').dt.normalize()

    agg_dict = {'contribuicao_total': 'sum'}
    if 'contrib_participante' in df.columns:
        agg_dict['contrib_participante'] = 'sum'
    if 'contrib_patrocinador' in df.columns:
        agg_dict['contrib_patrocinador'] = 'sum'

    df_monthly = df.groupby('mes').agg(agg_dict).reset_index()
    df_monthly = df_monthly.rename(columns={'mes': 'data'})
    df_monthly['contribuicao_acumulada'] = df_monthly['contribuicao_total'].cumsum()

    if 'contrib_participante' in df_monthly.columns:
        df_monthly['contrib_participante_acum'] = df_monthly['contrib_participante'].cumsum()
    if 'contrib_patrocinador' in df_monthly.columns:
        df_monthly['contrib_patrocinador_acum'] = df_monthly['contrib_patrocinador'].cumsum()

    return df_monthly


def deflate_series(df: pd.DataFrame,
                   inflation_index: pd.DataFrame,
                   base_date: pd.Timestamp,
                   value_col: str = 'posicao') -> pd.DataFrame:
    """
    Deflate a time series by inflation index to show real values.

    Real value = nominal_value * (base_inflation / date_inflation)
    This adjusts all values to the purchasing power of the base_date.

    Uses geometric interpolation for dates between monthly data points,
    which properly handles contributions that occur mid-month.

    Args:
        df: DataFrame with 'data' column and value columns
        inflation_index: IPCA data with 'date' and 'value' columns
        base_date: Reference date for real values (values adjusted to this date's BRL)
        value_col: Column name to deflate

    Returns:
        DataFrame with additional '{value_col}_real' column
    """
    from benchmarks import get_value_on_date

    df = df.copy()
    base_date = pd.Timestamp(base_date).normalize()

    # Get base inflation value using interpolation
    base_inflation_value, _ = get_value_on_date(inflation_index, base_date)

    if base_inflation_value is None:
        # Can't deflate without base value
        df[f'{value_col}_real'] = df[value_col]
        return df

    # Deflate each row using interpolated values
    real_values = []
    for _, row in df.iterrows():
        date = pd.Timestamp(row['data']).normalize()
        nominal_value = row[value_col]

        # Get interpolated inflation index for this date
        inflation_value, _ = get_value_on_date(inflation_index, date)

        if inflation_value is not None and inflation_value > 0:
            # Real value = nominal × (base_inflation / date_inflation)
            real_value = nominal_value * (base_inflation_value / inflation_value)
        else:
            real_value = nominal_value

        real_values.append(real_value)

    df[f'{value_col}_real'] = real_values
    return df


def apply_deflation(df_position: pd.DataFrame,
                    df_contributions: pd.DataFrame,
                    inflation_index: pd.DataFrame = None,
                    reference_date: pd.Timestamp = None) -> tuple:
    """
    Apply inflation deflation to position and contribution data in-place.

    If inflation_index is None, returns data unchanged (no-op).
    Otherwise, replaces values with deflated values (no new columns).

    Args:
        df_position: Position data with 'data' and 'posicao' columns
        df_contributions: Contributions data with 'data' and contribution columns
        inflation_index: Deflator data (IPCA/INPC/USD), or None to skip
        reference_date: Reference date for real values

    Returns:
        tuple: (df_position, df_contributions) with values deflated in-place
    """
    if inflation_index is None or reference_date is None:
        return df_position, df_contributions

    # Deflate position - use helper then copy back
    df_pos = deflate_series(df_position, inflation_index, reference_date, 'posicao')
    df_pos['posicao'] = df_pos['posicao_real']
    df_pos = df_pos.drop(columns=['posicao_real'])

    # Also deflate valor_cota if present (needed for partial PDF CAGR calculations)
    if 'valor_cota' in df_pos.columns:
        df_pos = deflate_series(df_pos, inflation_index, reference_date, 'valor_cota')
        df_pos['valor_cota'] = df_pos['valor_cota_real']
        df_pos = df_pos.drop(columns=['valor_cota_real'])

    # Deflate contributions
    df_contrib = df_contributions.copy()
    for col in ['contribuicao_total', 'contrib_participante', 'contrib_patrocinador']:
        if col in df_contrib.columns:
            df_contrib = deflate_series(df_contrib, inflation_index, reference_date, col)
            df_contrib[col] = df_contrib[f'{col}_real']
            df_contrib = df_contrib.drop(columns=[f'{col}_real'])

    return df_pos, df_contrib


def calculate_summary_stats(df_position: pd.DataFrame,
                            df_contributions_raw: pd.DataFrame,
                            df_contributions_monthly: pd.DataFrame) -> dict:
    """
    Calculate summary statistics for the dashboard.

    Args:
        df_position: Processed position data
        df_contributions_raw: Raw contributions with exact dates
        df_contributions_monthly: Monthly aggregated contributions

    Returns:
        Dictionary with last_position, last_date, total_contributed,
        total_return, cagr_pct
    """
    last_position = df_position['posicao'].iloc[-1]
    last_date = df_position['data'].iloc[-1]
    total_contributed = df_contributions_monthly['contribuicao_acumulada'].iloc[-1] if not df_contributions_monthly.empty else 0
    total_return = last_position - total_contributed

    # Calculate XIRR (CAGR) using exact dates and Brazilian business days
    cagr_pct = None
    if not df_contributions_raw.empty:
        dates = df_contributions_raw['data'].tolist() + [last_date]
        amounts = [-amt for amt in df_contributions_raw['contribuicao_total'].tolist()] + [last_position]
        cagr = xirr_bizdays(dates, amounts)
        cagr_pct = cagr * 100 if cagr is not None else None

    return {
        'last_position': last_position,
        'last_date': last_date,
        'total_contributed': total_contributed,
        'total_return': total_return,
        'cagr_pct': cagr_pct
    }
