"""
Tests for benchmarks.py - Benchmark data fetching and simulation.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

import sys
sys.path.insert(0, '/home/petrini/Documents/nucleos_analyzer')

from benchmarks import (
    get_value_on_date,
    simulate_benchmark,
    apply_overhead_to_benchmark,
    AVAILABLE_BENCHMARKS,
)


class TestGetValueOnDate:
    """Tests for the get_value_on_date function."""

    def test_exact_match(self, sample_benchmark_data):
        """Test getting value on an exact date match."""
        target = pd.Timestamp('2020-02-01')
        value, actual_date = get_value_on_date(sample_benchmark_data, target)

        assert value is not None
        assert abs(value - 1.004) < 0.0001
        assert actual_date == target

    def test_interpolation_between_dates(self, sample_benchmark_data):
        """Test geometric interpolation between data points."""
        # Mid-point between Feb 1 (1.004) and Mar 1 (1.008016)
        target = pd.Timestamp('2020-02-15')
        value, actual_date = get_value_on_date(sample_benchmark_data, target)

        assert value is not None
        # Should be geometrically between 1.004 and 1.008016
        assert 1.004 < value < 1.008016
        assert actual_date == target

    def test_date_before_data_returns_none(self, sample_benchmark_data):
        """Test that dates before available data return None."""
        target = pd.Timestamp('2019-01-01')
        value, actual_date = get_value_on_date(sample_benchmark_data, target)

        assert value is None
        assert actual_date is None

    def test_extrapolation_after_data(self, sample_benchmark_data):
        """Test extrapolation beyond available data."""
        # One month after last data point
        target = pd.Timestamp('2020-08-01')
        value, actual_date = get_value_on_date(sample_benchmark_data, target)

        assert value is not None
        # Should be higher than last value (extrapolated growth)
        assert value > 1.024241
        # actual_date should be the last available date
        assert actual_date == pd.Timestamp('2020-07-01')

    def test_empty_dataframe(self):
        """Test handling of empty dataframe."""
        empty_df = pd.DataFrame({'date': [], 'value': []})
        target = pd.Timestamp('2020-02-01')
        value, actual_date = get_value_on_date(empty_df, target)

        assert value is None
        assert actual_date is None

    def test_single_data_point(self):
        """Test handling of single data point."""
        single_df = pd.DataFrame({
            'date': [pd.Timestamp('2020-01-01')],
            'value': [1.0]
        })

        # Exact match should work
        value, _ = get_value_on_date(single_df, pd.Timestamp('2020-01-01'))
        assert value == 1.0

        # Future date should extrapolate
        value, _ = get_value_on_date(single_df, pd.Timestamp('2020-02-01'))
        assert value is not None


class TestSimulateBenchmark:
    """Tests for the simulate_benchmark function."""

    def test_single_contribution(self, sample_benchmark_data):
        """Test simulation with a single contribution."""
        contributions = pd.DataFrame({
            'data': [pd.Timestamp('2020-01-01')],
            'contribuicao_total': [1000.0]
        })
        position_dates = pd.DataFrame({
            'data': [pd.Timestamp('2020-03-01')]
        })

        result = simulate_benchmark(contributions, sample_benchmark_data, position_dates)

        assert len(result) == 1
        # Value should have grown (1000 * 1.008016 / 1.0)
        expected = 1000.0 * 1.008016
        assert abs(result.iloc[0]['posicao'] - expected) < 0.01

    def test_multiple_contributions(self, sample_benchmark_data):
        """Test simulation with multiple contributions."""
        contributions = pd.DataFrame({
            'data': [pd.Timestamp('2020-01-01'), pd.Timestamp('2020-02-01')],
            'contribuicao_total': [1000.0, 1000.0]
        })
        position_dates = pd.DataFrame({
            'data': [pd.Timestamp('2020-03-01')]
        })

        result = simulate_benchmark(contributions, sample_benchmark_data, position_dates)

        # First contribution: 1000 units at value 1.0, valued at 1.008016
        # Second contribution: 1000/1.004 units at value 1.004, valued at 1.008016
        first_units = 1000.0 / 1.0
        second_units = 1000.0 / 1.004
        expected = (first_units + second_units) * 1.008016

        assert abs(result.iloc[0]['posicao'] - expected) < 0.1

    def test_contributions_accumulate(self, sample_benchmark_data):
        """Test that contributions properly accumulate over time."""
        contributions = pd.DataFrame({
            'data': [pd.Timestamp('2020-01-01')],
            'contribuicao_total': [1000.0]
        })
        position_dates = pd.DataFrame({
            'data': [
                pd.Timestamp('2020-01-01'),
                pd.Timestamp('2020-02-01'),
                pd.Timestamp('2020-03-01')
            ]
        })

        result = simulate_benchmark(contributions, sample_benchmark_data, position_dates)

        # Values should increase over time due to benchmark growth
        assert result.iloc[0]['posicao'] <= result.iloc[1]['posicao']
        assert result.iloc[1]['posicao'] <= result.iloc[2]['posicao']

    def test_position_before_contribution(self, sample_benchmark_data):
        """Test that position is 0 before any contribution."""
        contributions = pd.DataFrame({
            'data': [pd.Timestamp('2020-03-01')],
            'contribuicao_total': [1000.0]
        })
        position_dates = pd.DataFrame({
            'data': [pd.Timestamp('2020-01-01'), pd.Timestamp('2020-03-01')]
        })

        result = simulate_benchmark(contributions, sample_benchmark_data, position_dates)

        # Before contribution, position should be 0
        assert result.iloc[0]['posicao'] == 0
        # After contribution, should have value
        assert result.iloc[1]['posicao'] > 0


class TestApplyOverheadToBenchmark:
    """Tests for the apply_overhead_to_benchmark function."""

    def test_zero_overhead_unchanged(self, sample_benchmark_data):
        """Test that zero overhead returns unchanged data."""
        result = apply_overhead_to_benchmark(sample_benchmark_data, 0)

        pd.testing.assert_series_equal(
            result['value'].reset_index(drop=True),
            sample_benchmark_data['value'].reset_index(drop=True)
        )

    def test_positive_overhead_increases_values(self, sample_benchmark_data):
        """Test that positive overhead increases later values."""
        result = apply_overhead_to_benchmark(sample_benchmark_data, 4.0)  # 4% overhead

        # First value should be unchanged (t=0)
        assert abs(result.iloc[0]['value'] - sample_benchmark_data.iloc[0]['value']) < 0.0001

        # Later values should be higher
        for i in range(1, len(result)):
            assert result.iloc[i]['value'] > sample_benchmark_data.iloc[i]['value']

    def test_negative_overhead_decreases_values(self, sample_benchmark_data):
        """Test that negative overhead decreases later values."""
        result = apply_overhead_to_benchmark(sample_benchmark_data, -2.0)  # -2% overhead

        # First value should be unchanged (t=0)
        assert abs(result.iloc[0]['value'] - sample_benchmark_data.iloc[0]['value']) < 0.0001

        # Later values should be lower
        for i in range(1, len(result)):
            assert result.iloc[i]['value'] < sample_benchmark_data.iloc[i]['value']

    def test_overhead_compounds_over_time(self, sample_benchmark_data):
        """Test that overhead compounds (exponential growth)."""
        result = apply_overhead_to_benchmark(sample_benchmark_data, 12.0)  # 12% annual overhead

        # Calculate the multiplier for each point
        original = sample_benchmark_data['value'].values
        adjusted = result['value'].values

        multipliers = adjusted / original

        # Multipliers should be increasing (compound effect)
        for i in range(1, len(multipliers)):
            assert multipliers[i] > multipliers[i - 1]


class TestAvailableBenchmarks:
    """Tests for benchmark configuration."""

    def test_expected_benchmarks_available(self):
        """Test that expected benchmarks are in the list."""
        expected = ['CDI', 'IPCA', 'INPC', 'S&P 500', 'USD']

        for benchmark in expected:
            assert benchmark in AVAILABLE_BENCHMARKS, f"{benchmark} not in AVAILABLE_BENCHMARKS"


class TestBenchmarkIntegration:
    """Integration tests combining multiple benchmark functions.

    These tests verify the mathematical consistency of the 252/365 approximation
    used throughout the application.
    """

    def test_overhead_exactly_matches_expected_growth(self):
        """
        Test that overhead produces exactly the expected growth rate.

        With the 252/365 ratio, 1 calendar year = 252 business days exactly,
        so X% overhead should produce exactly X% growth over 365 calendar days.
        """
        # Create flat index over exactly 365 days
        start = pd.Timestamp('2020-01-01')
        end = pd.Timestamp('2021-01-01')  # 366 days (leap year), close enough
        dates = pd.date_range(start, end, freq='D')

        flat_data = pd.DataFrame({
            'date': dates,
            'value': [1.0] * len(dates)
        })

        # Apply 10% overhead
        result = apply_overhead_to_benchmark(flat_data, 10.0)

        # First value should be exactly 1.0
        assert result.iloc[0]['value'] == 1.0

        # Last value should be 1.10 (10% growth)
        # The formula: 1.0 * (1.10)^(366 * 252/365 / 252) = 1.10^(366/365) ≈ 1.1003
        expected = 1.10 ** (366 / 365)
        actual = result.iloc[-1]['value']

        assert abs(actual - expected) < 1e-9, \
            f"Expected {expected:.10f}, got {actual:.10f}"

    def test_inpc_plus_overhead_deflated_equals_overhead(self):
        """
        Test the key property: Index + X% deflated by Index ≈ X%.

        This is now exact (within floating point precision) because all
        calculations use the same 252/365 ratio.
        """
        from calculator import deflate_series

        # Create index with 6% annual growth over exactly 365 days
        start = pd.Timestamp('2020-01-01')
        end = pd.Timestamp('2020-12-31')  # 365 days
        dates = pd.date_range(start, end, freq='D')

        # Index value at day N = 1.06^(N/365) - simple calendar day growth
        values = [1.06 ** (i / 365) for i in range(len(dates))]
        index_data = pd.DataFrame({'date': dates, 'value': values})

        # Apply 4% overhead to create "Index + 4%"
        benchmark_with_overhead = apply_overhead_to_benchmark(index_data, 4.0)

        # Simulate single contribution at start, valued at end
        contributions = pd.DataFrame({
            'data': [start],
            'contribuicao_total': [10000.0]
        })
        position_dates = pd.DataFrame({'data': [end]})

        result = simulate_benchmark(contributions, benchmark_with_overhead, position_dates)
        final_nominal = result.iloc[0]['posicao']

        # To calculate real return, we need to deflate BOTH values to same reference
        # Deflate to END date (reference = end)
        # Initial contribution in real terms (deflated to end):
        #   10000 * (index_end / index_start) = 10000 * 1.06 = 10600
        # Final value in real terms (already at end): final_nominal

        index_start = values[0]   # 1.0
        index_end = values[-1]    # 1.06

        initial_real = 10000.0 * (index_end / index_start)  # 10600
        final_real = final_nominal  # Already in end-period terms

        # Real return = (final_real / initial_real) - 1
        real_return = (final_real / initial_real) - 1

        # Expected: 4% overhead applied over 365 calendar days
        # With 252/365 ratio: biz_days = 365 * 252/365 = 252
        # Overhead factor = 1.04^(252/252) = 1.04
        expected_return = 0.04

        # Should be exact within floating point precision
        assert abs(real_return - expected_return) < 1e-6, \
            f"Expected {expected_return:.6%} real return, got {real_return:.6%}"

    def test_deflation_cancels_inflation_exactly(self):
        """
        Test that deflating by inflation cancels out the inflation component.
        """
        from calculator import deflate_series

        # Create inflation index: 10% annual over 365 days
        dates = pd.date_range('2020-01-01', '2020-12-31', freq='D')
        biz_days_per_day = 252 / 365
        daily_factor = 1.10 ** (biz_days_per_day / 252)
        values = [daily_factor ** i for i in range(len(dates))]

        inflation_data = pd.DataFrame({'date': dates, 'value': values})

        # Position that grew by exactly 10% (same as inflation)
        start_value = 10000.0
        end_value = start_value * 1.10 ** (365 / 365)

        position_data = pd.DataFrame({
            'data': [pd.Timestamp('2020-01-01'), pd.Timestamp('2020-12-31')],
            'posicao': [start_value, end_value]
        })

        # Deflate to end date
        result = deflate_series(
            position_data,
            inflation_data,
            pd.Timestamp('2020-12-31'),
            'posicao'
        )

        # Real values should show ~0% growth
        start_real = result.iloc[0]['posicao_real']
        end_real = result.iloc[1]['posicao_real']

        real_growth = (end_real - start_real) / start_real

        # Should be very close to 0%
        assert abs(real_growth) < 1e-6, \
            f"Expected ~0% real growth, got {real_growth:.6%}"

    def test_xirr_with_known_return(self):
        """
        Test XIRR calculation with a known return rate.
        """
        from calculator import xirr_bizdays

        # Invest 10000, get back 11000 after exactly 365 days
        # This is 10% nominal return
        dates = [pd.Timestamp('2020-01-01'), pd.Timestamp('2021-01-01')]
        amounts = [-10000, 11000]

        rate = xirr_bizdays(dates, amounts)

        # With 252/365 ratio: 366 calendar days = 252.66 business days
        # So annual rate should be slightly less than 10% calendar
        # Actually: (11000/10000)^(252/(366*252/365)) - 1 = 10%^(365/366) ≈ 9.97%
        expected = (11000 / 10000) ** (365 / 366) - 1

        assert abs(rate - expected) < 1e-6, \
            f"Expected {expected:.6%}, got {rate:.6%}"
