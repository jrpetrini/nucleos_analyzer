"""
Tests for calculator.py - Financial calculations and data processing.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

import sys
sys.path.insert(0, '/home/petrini/Documents/nucleos_analyzer')

from calculator import (
    xirr_bizdays,
    process_position_data,
    process_contributions_data,
    deflate_series,
    apply_deflation,
    calculate_summary_stats,
)


class TestXirrBizdays:
    """Tests for the xirr_bizdays function."""

    def test_simple_return(self):
        """Test XIRR with simple investment and return."""
        # Invest 1000, get back 1100 after ~1 year (252 business days)
        dates = [datetime(2020, 1, 2), datetime(2021, 1, 4)]
        amounts = [-1000, 1100]

        rate = xirr_bizdays(dates, amounts)

        assert rate is not None
        # Should be approximately 10% annual return
        assert 0.09 < rate < 0.11

    def test_zero_return(self):
        """Test XIRR with zero return (get back exactly what you put in)."""
        dates = [datetime(2020, 1, 2), datetime(2021, 1, 4)]
        amounts = [-1000, 1000]

        rate = xirr_bizdays(dates, amounts)

        assert rate is not None
        assert abs(rate) < 0.01  # Should be close to 0%

    def test_negative_return(self):
        """Test XIRR with negative return (loss)."""
        dates = [datetime(2020, 1, 2), datetime(2021, 1, 4)]
        amounts = [-1000, 900]

        rate = xirr_bizdays(dates, amounts)

        assert rate is not None
        assert -0.15 < rate < -0.05  # Should be negative

    def test_multiple_contributions(self):
        """Test XIRR with multiple contributions over time."""
        dates = [
            datetime(2020, 1, 2),
            datetime(2020, 4, 1),
            datetime(2020, 7, 1),
            datetime(2020, 10, 1),
            datetime(2021, 1, 4)
        ]
        amounts = [-1000, -1000, -1000, -1000, 4400]

        rate = xirr_bizdays(dates, amounts)

        assert rate is not None
        # Should be positive since we got back more than we put in
        assert rate > 0

    def test_insufficient_data(self):
        """Test XIRR returns None with insufficient data."""
        dates = [datetime(2020, 1, 2)]
        amounts = [-1000]

        rate = xirr_bizdays(dates, amounts)

        assert rate is None

    def test_mismatched_lengths(self):
        """Test XIRR returns None with mismatched list lengths."""
        dates = [datetime(2020, 1, 2), datetime(2021, 1, 4)]
        amounts = [-1000]

        rate = xirr_bizdays(dates, amounts)

        assert rate is None


class TestProcessPositionData:
    """Tests for the process_position_data function."""

    def test_basic_processing(self, sample_raw_transactions):
        """Test basic position data processing."""
        result = process_position_data(sample_raw_transactions)

        # Should have monthly rows
        assert len(result) == 3  # Jan, Feb, Mar

        # Should have correct columns
        assert 'data' in result.columns
        assert 'cotas' in result.columns
        assert 'posicao' in result.columns
        assert 'valor_cota' in result.columns

    def test_cumulative_cotas(self, sample_raw_transactions):
        """Test that cotas accumulate correctly."""
        result = process_position_data(sample_raw_transactions)

        # January: 50 + 50 = 100 cotas
        # February: 100 + 50 + 50 = 200 cotas
        # March: 200 + 100 = 300 cotas
        assert result.iloc[0]['cotas'] == 100
        assert result.iloc[1]['cotas'] == 200
        assert result.iloc[2]['cotas'] == 300

    def test_position_calculation(self, sample_raw_transactions):
        """Test that position = cotas * valor_cota."""
        result = process_position_data(sample_raw_transactions)

        for _, row in result.iterrows():
            expected_position = row['cotas'] * row['valor_cota']
            assert abs(row['posicao'] - expected_position) < 0.01


class TestProcessContributionsData:
    """Tests for the process_contributions_data function."""

    def test_monthly_aggregation(self, sample_contributions):
        """Test that contributions are aggregated by month."""
        result = process_contributions_data(sample_contributions)

        # Should have 6 months of data
        assert len(result) == 6

        # Each month should have 1000 total
        assert all(result['contribuicao_total'] == 1000.0)

    def test_cumulative_sums(self, sample_contributions):
        """Test cumulative sum columns."""
        result = process_contributions_data(sample_contributions)

        # Check cumulative totals
        expected_cumsum = [1000, 2000, 3000, 4000, 5000, 6000]
        assert list(result['contribuicao_acumulada']) == expected_cumsum

    def test_empty_dataframe(self):
        """Test handling of empty dataframe."""
        empty_df = pd.DataFrame()
        result = process_contributions_data(empty_df)

        assert result.empty


class TestDeflateSeries:
    """Tests for the deflate_series function."""

    def test_deflation_reduces_past_values(self, sample_position_data, sample_inflation_index):
        """Test that deflating past values reduces them (since inflation erodes purchasing power)."""
        # Use the last date as reference (present value)
        base_date = pd.Timestamp('2020-06-30')

        result = deflate_series(
            sample_position_data,
            sample_inflation_index,
            base_date,
            'posicao'
        )

        # Past values deflated to present should be HIGHER (they were worth more)
        # So posicao_real > posicao for earlier dates
        assert 'posicao_real' in result.columns

        # First month's real value should be higher than nominal
        # (1000 BRL in Jan 2020 is worth more than 1000 BRL in Jun 2020)
        first_real = result.iloc[0]['posicao_real']
        first_nominal = result.iloc[0]['posicao']
        assert first_real > first_nominal

    def test_deflation_with_same_base_date(self, sample_position_data, sample_inflation_index):
        """Test that deflating to the same date returns approximately the same value."""
        # Use first date as base
        base_date = pd.Timestamp('2020-01-31')

        result = deflate_series(
            sample_position_data,
            sample_inflation_index,
            base_date,
            'posicao'
        )

        # First row should be nearly identical (same reference point)
        first_real = result.iloc[0]['posicao_real']
        first_nominal = result.iloc[0]['posicao']
        assert abs(first_real - first_nominal) / first_nominal < 0.02  # Within 2%

    def test_deflation_preserves_original_data(self, sample_position_data, sample_inflation_index):
        """Test that original posicao column is unchanged."""
        original_values = sample_position_data['posicao'].copy()
        base_date = pd.Timestamp('2020-06-30')

        result = deflate_series(
            sample_position_data,
            sample_inflation_index,
            base_date,
            'posicao'
        )

        # Original column should be unchanged
        pd.testing.assert_series_equal(
            result['posicao'].reset_index(drop=True),
            original_values.reset_index(drop=True)
        )


class TestApplyDeflation:
    """Tests for the apply_deflation function."""

    def test_none_inflation_returns_unchanged(self, sample_position_data, sample_contributions):
        """Test that None inflation_index returns data unchanged."""
        df_pos, df_contrib = apply_deflation(
            sample_position_data,
            sample_contributions,
            inflation_index=None,
            reference_date=None
        )

        pd.testing.assert_frame_equal(df_pos, sample_position_data)
        pd.testing.assert_frame_equal(df_contrib, sample_contributions)

    def test_deflation_modifies_values_in_place(self, sample_position_data, sample_contributions, sample_inflation_index):
        """Test that deflation modifies values (no _real suffix columns)."""
        base_date = pd.Timestamp('2020-06-30')

        df_pos, df_contrib = apply_deflation(
            sample_position_data,
            sample_contributions,
            sample_inflation_index,
            base_date
        )

        # Should not have _real columns
        assert 'posicao_real' not in df_pos.columns
        assert 'contribuicao_total_real' not in df_contrib.columns

        # Values should have changed
        assert not df_pos['posicao'].equals(sample_position_data['posicao'])


class TestCalculateSummaryStats:
    """Tests for the calculate_summary_stats function."""

    def test_basic_stats(self, sample_position_data, sample_contributions):
        """Test basic summary statistics."""
        monthly_contrib = process_contributions_data(sample_contributions)

        stats = calculate_summary_stats(
            sample_position_data,
            sample_contributions,
            monthly_contrib
        )

        assert 'last_position' in stats
        assert 'last_date' in stats
        assert 'total_contributed' in stats
        assert 'total_return' in stats
        assert 'cagr_pct' in stats

    def test_total_return_calculation(self, sample_position_data, sample_contributions):
        """Test that total return = position - contributed."""
        monthly_contrib = process_contributions_data(sample_contributions)

        stats = calculate_summary_stats(
            sample_position_data,
            sample_contributions,
            monthly_contrib
        )

        expected_return = stats['last_position'] - stats['total_contributed']
        assert abs(stats['total_return'] - expected_return) < 0.01

    def test_cagr_is_calculated(self, sample_position_data, sample_contributions):
        """Test that CAGR is calculated and reasonable."""
        monthly_contrib = process_contributions_data(sample_contributions)

        stats = calculate_summary_stats(
            sample_position_data,
            sample_contributions,
            monthly_contrib
        )

        # CAGR should be a reasonable percentage (not None, not extreme)
        assert stats['cagr_pct'] is not None
        assert -50 < stats['cagr_pct'] < 100
