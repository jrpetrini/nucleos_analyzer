#!/usr/bin/env python3
"""
Financial calculations and data processing for Nucleos Analyzer.
"""

import pandas as pd
from bizdays import Calendar
from scipy.optimize import brentq
from pyxirr import xirr

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


def process_position_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Process raw transaction data to get monthly positions.

    Args:
        df_raw: Raw dataframe from extract_data_from_pdf

    Returns:
        DataFrame with monthly position data (data, cotas, posicao, valor_cota)
    """
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
    """
    Process contributions data for bar chart (aggregated by month).

    Args:
        df_contributions: Contributions dataframe from extract_data_from_pdf

    Returns:
        DataFrame with monthly contribution totals and cumulative sum
    """
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
