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


