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


# =============================================================================
# FORECAST ASSUMPTIONS (documented for transparency)
# =============================================================================
# Forecasting assumptions (configurable via UI):
#
# Salary growth rate (user-selectable, REAL rates above inflation):
#   - Fast: 4.43% real (3 salary steps every 2 years)
#   - Medium: 2.56% real (geometric average)
#   - Slow: 1.48% real (0.5 steps per year)
#   - Formula: S(t) = S0 × exp(growth_rate × t), where t is in years
#
# COMPANY_MATCH_RATIO = 0.85
#   - Company matches 85% of participant contribution
#   - Total monthly investment = participant × 1.85
#   - This is the actual amount going into the fund each month
#
# The "company as mine" toggle affects ACCOUNTING only:
#   - Toggle OFF: count full 1.85× as "my investment" for CAGR
#   - Toggle ON: count only participant portion as "my investment" for CAGR
#   - Either way, the same total amount is invested
#
# These are PROJECTIONS, not guarantees. Actual results may vary significantly.
# =============================================================================

COMPANY_MATCH_RATIO = 0.85  # Company matches 85% of participant contribution


def generate_forecast(df_position: pd.DataFrame,
                      df_contributions: pd.DataFrame,
                      cagr: float,
                      years: int,
                      growth_rate: float,
                      include_company_match: bool = True) -> pd.DataFrame:
    """
    Generate forecast data for future position projection.

    ASSUMPTIONS (inform user):
    - Contributions grow at the selected real rate (above inflation)
    - Company matches 85% of participant contribution (if include_company_match=True)
    - Historical CAGR continues unchanged
    - Contributions happen on 1st of each month

    Args:
        df_position: Historical position data with 'data' and 'posicao' columns
        df_contributions: Historical contributions with 'data', 'contribuicao_total',
                         and optionally 'contrib_participante' columns
        cagr: Historical CAGR (as decimal, e.g., 0.10 for 10%)
        years: Number of years to forecast
        growth_rate: Annual real salary growth rate (e.g., 0.0256 for 2.56%)
        include_company_match: If True, total = participant × 1.85; if False, total = participant only
                              (use False for benchmark when "company as mine" is ON)

    Returns:
        DataFrame with forecasted data:
        - 'data': forecast date
        - 'posicao': projected position
        - 'is_forecast': True (marker for dashed line)
        - 'contribuicao_total_proj': total invested
        - 'contrib_participante_proj': participant portion only
    """
    if df_position.empty or df_contributions.empty or cagr is None:
        return pd.DataFrame()

    # Get last position and date
    last_date = df_position['data'].max()
    last_position = df_position.loc[df_position['data'] == last_date, 'posicao'].iloc[0]

    # Calculate base monthly contribution from last 12 months (participant only)
    recent_contrib = df_contributions[
        df_contributions['data'] >= last_date - pd.DateOffset(months=12)
    ]

    if 'contrib_participante' in recent_contrib.columns:
        base_participant = recent_contrib['contrib_participante'].mean()
    else:
        # Estimate participant as total / 1.85
        base_participant = recent_contrib['contribuicao_total'].mean() / (1 + COMPANY_MATCH_RATIO)

    if pd.isna(base_participant) or base_participant <= 0:
        # Fallback: use total contributions divided by 1.85
        base_participant = recent_contrib['contribuicao_total'].mean() / (1 + COMPANY_MATCH_RATIO)
        if pd.isna(base_participant):
            base_participant = 0

    # Calculate monthly growth rate from CAGR
    # CAGR is annual rate, convert to monthly: (1 + cagr)^(1/12) - 1
    monthly_rate = (1 + cagr) ** (1/12) - 1

    # Generate forecast months
    forecast_data = []
    current_position = last_position

    import math
    for month in range(1, years * 12 + 1):
        forecast_date = last_date + pd.DateOffset(months=month)
        t_years = month / 12  # Time in years from start of forecast

        # Calculate participant contribution with growth
        # S(t) = S0 × exp(growth_rate × t)
        participant_contrib = base_participant * math.exp(growth_rate * t_years)

        # Total invested depends on whether company match is included
        if include_company_match:
            total_contrib = participant_contrib * (1 + COMPANY_MATCH_RATIO)
        else:
            total_contrib = participant_contrib

        # Add contribution at start of month, then apply growth
        current_position += total_contrib
        current_position *= (1 + monthly_rate)

        forecast_data.append({
            'data': forecast_date,
            'posicao': current_position,
            'is_forecast': True,
            'contribuicao_total_proj': total_contrib,
            'contrib_participante_proj': participant_contrib,
        })

    return pd.DataFrame(forecast_data)


def get_forecast_assumptions_text(growth_rate: float) -> str:
    """Return text explaining forecast assumptions for UI display."""
    return (
        "Premissas da projeção:\n"
        f"• Contribuições crescem {growth_rate*100:.1f}% a.a. real (acima da inflação)\n"
        f"• Empresa aporta {COMPANY_MATCH_RATIO*100:.0f}% do participante\n"
        "• CAGR histórico mantém-se constante\n"
        "• Projeções não são garantias de retorno"
    )
