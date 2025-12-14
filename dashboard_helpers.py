#!/usr/bin/env python3
"""
Helper functions extracted from dashboard.py for better testability.
"""

import pandas as pd


def prepare_dataframe(data: list | None, date_column: str = 'data') -> pd.DataFrame:
    """
    Convert list of dicts to DataFrame with parsed dates.

    Args:
        data: List of dictionaries (from dcc.Store)
        date_column: Name of the date column to parse

    Returns:
        DataFrame with parsed datetime column, or empty DataFrame if data is None/empty
    """
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    if date_column in df.columns:
        df[date_column] = pd.to_datetime(df[date_column])
    return df


def is_inflation_enabled(toggle_value: list | None) -> bool:
    """
    Check if inflation adjustment toggle is ON.

    Args:
        toggle_value: Value from dcc.Checklist (list of selected values or None)

    Returns:
        True if inflation adjustment is enabled
    """
    return 'adjust' in (toggle_value or [])


def is_company_as_mine(toggle_value: list | None) -> bool:
    """
    Check if company-as-mine toggle is ON.

    Args:
        toggle_value: Value from dcc.Checklist (list of selected values or None)

    Returns:
        True if company contributions should be treated as "free money"
    """
    return 'as_mine' in (toggle_value or [])


def get_contribution_column(df: pd.DataFrame, company_as_mine: bool) -> str:
    """
    Get the appropriate contribution column based on toggle.

    Args:
        df: DataFrame with contribution columns
        company_as_mine: Whether to use only participant contributions

    Returns:
        Column name to use ('contrib_participante' or 'contribuicao_total')
    """
    if company_as_mine and 'contrib_participante' in df.columns:
        return 'contrib_participante'
    return 'contribuicao_total'


def get_contribution_amounts(df: pd.DataFrame, company_as_mine: bool) -> pd.Series:
    """
    Get contribution amounts based on toggle setting.

    Args:
        df: DataFrame with contribution columns
        company_as_mine: Whether to use only participant contributions

    Returns:
        Series of contribution amounts
    """
    col = get_contribution_column(df, company_as_mine)
    return df[col]


def prepare_benchmark_contributions(df_contrib: pd.DataFrame, company_as_mine: bool) -> pd.DataFrame:
    """
    Prepare contribution DataFrame for benchmark simulation.

    Creates a DataFrame with 'data' and 'contribuicao_total' columns,
    where 'contribuicao_total' contains the appropriate amounts based on toggle.

    Args:
        df_contrib: Source contribution DataFrame
        company_as_mine: Whether to use only participant contributions

    Returns:
        DataFrame ready for benchmark simulation
    """
    if df_contrib.empty:
        return pd.DataFrame(columns=['data', 'contribuicao_total'])

    amounts = get_contribution_amounts(df_contrib, company_as_mine)

    df_sim = df_contrib[['data']].copy()
    df_sim['contribuicao_total'] = amounts.values
    return df_sim


def build_deflator_dict(inflation_data: pd.DataFrame | None) -> dict[str, float]:
    """
    Build month->deflator lookup dictionary from inflation index data.

    Args:
        inflation_data: DataFrame with 'date' and 'value' columns

    Returns:
        Dictionary mapping 'Mon YYYY' strings to deflator values
    """
    if inflation_data is None or inflation_data.empty:
        return {}

    df = inflation_data.copy()
    df['date'] = pd.to_datetime(df['date'])

    return {
        row['date'].strftime('%b %Y'): row['value']
        for _, row in df.iterrows()
    }


def format_currency(value: float) -> str:
    """
    Format a value as Brazilian currency string.

    Args:
        value: Numeric value to format

    Returns:
        Formatted string like 'R$ 1.234,56'
    """
    return f"R$ {value:,.2f}"


def format_percentage(value: float, signed: bool = True) -> str:
    """
    Format a value as percentage string.

    Args:
        value: Percentage value (e.g., 10.5 for 10.5%)
        signed: Whether to include + sign for positive values

    Returns:
        Formatted string like '+10.50% a.a.' or '10.50% a.a.'
    """
    if signed:
        return f"{value:+.2f}% a.a."
    return f"{value:.2f}% a.a."


def get_cagr_color(cagr_pct: float | None, colors: dict) -> str:
    """
    Get the appropriate color for CAGR display.

    Args:
        cagr_pct: CAGR percentage value (can be None)
        colors: Color palette dictionary with 'accent' and optionally 'negative' keys

    Returns:
        Color hex code
    """
    if cagr_pct is None or cagr_pct >= 0:
        return colors.get('accent', '#06b6d4')
    return '#ef4444'  # Red for negative


def get_return_color(return_value: float, colors: dict) -> str:
    """
    Get the appropriate color for return display.

    Args:
        return_value: Total return value
        colors: Color palette dictionary

    Returns:
        Color hex code
    """
    if return_value >= 0:
        return colors.get('accent', '#06b6d4')
    return '#ef4444'  # Red for negative
