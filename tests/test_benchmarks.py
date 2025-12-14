"""
Tests for benchmarks.py - Benchmark data fetching and simulation.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

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
    """Integration tests for consistent business day calculations.

    These tests verify that using 252/365.25 ratio everywhere produces
    mathematically consistent results.
    """

    def test_overhead_exactly_matches_expected_growth(self):
        """Test that 4% overhead over 1 year gives exactly 4% growth."""
        from calculator import CALENDAR_DAYS_PER_YEAR, BIZ_DAY_RATIO

        # Create 1-year benchmark data (flat index at 1.0)
        dates = pd.date_range('2024-01-01', '2025-01-01', freq='MS')
        flat_data = pd.DataFrame({
            'date': dates,
            'value': [1.0] * len(dates)
        })

        result = apply_overhead_to_benchmark(flat_data, 4.0)

        # Calculate expected: (1.04)^(biz_days/252)
        calendar_days = (dates[-1] - dates[0]).days
        biz_days = calendar_days * BIZ_DAY_RATIO
        expected_final = 1.0 * (1.04 ** (biz_days / 252))

        assert abs(result.iloc[-1]['value'] - expected_final) < 1e-10

    def test_inpc_plus_overhead_deflated_equals_overhead(self, sample_inflation_index):
        """Test that INPC+4% deflated by INPC equals exactly 4% real return.

        This is the key consistency test: when we add overhead to an inflation
        index and then deflate by that same index, we should get exactly the
        overhead rate.
        """
        from calculator import deflate_series, CALENDAR_DAYS_PER_YEAR, BIZ_DAY_RATIO

        # Apply 4% overhead to inflation index
        inpc_plus_4 = apply_overhead_to_benchmark(sample_inflation_index, 4.0)

        # Create position-like dataframe
        df_position = pd.DataFrame({
            'data': inpc_plus_4['date'],
            'posicao': inpc_plus_4['value']
        })

        # Deflate by the original inflation index
        reference_date = sample_inflation_index['date'].iloc[-1]
        df_deflated = deflate_series(df_position, sample_inflation_index, reference_date, 'posicao')

        # Calculate real annual return
        first_real = df_deflated['posicao_real'].iloc[0]
        last_real = df_deflated['posicao_real'].iloc[-1]
        calendar_days = (df_deflated['data'].iloc[-1] - df_deflated['data'].iloc[0]).days
        years = calendar_days / CALENDAR_DAYS_PER_YEAR

        real_return_annual = ((last_real / first_real) ** (1 / years) - 1) * 100

        # Should be exactly 4%
        assert abs(real_return_annual - 4.0) < 0.01, f"Expected 4.00%, got {real_return_annual:.2f}%"

    def test_deflation_cancels_inflation_exactly(self, sample_inflation_index):
        """Test that deflating by inflation produces flat real values."""
        from calculator import deflate_series

        # Position that grows exactly with inflation
        df_position = pd.DataFrame({
            'data': sample_inflation_index['date'],
            'posicao': sample_inflation_index['value'] * 1000  # Scale up
        })

        reference_date = sample_inflation_index['date'].iloc[-1]
        df_deflated = deflate_series(df_position, sample_inflation_index, reference_date, 'posicao')

        # All real values should be approximately equal (flat purchasing power)
        real_values = df_deflated['posicao_real'].values
        # All should be close to the last value (deflated to reference date)
        expected = sample_inflation_index['value'].iloc[-1] * 1000

        for val in real_values:
            assert abs(val - expected) < 0.01, f"Expected ~{expected:.2f}, got {val:.2f}"

    def test_xirr_with_known_return(self):
        """Test XIRR calculation with known expected return."""
        from calculator import xirr_bizdays, CALENDAR_DAYS_PER_YEAR, BIZ_DAY_RATIO
        from datetime import date

        # Simple case: invest 1000, get back 1100 after 1 year
        # Using calendar days, this is exactly 10% annual return
        dates = [date(2024, 1, 1), date(2025, 1, 1)]
        amounts = [-1000.0, 1100.0]

        xirr_result = xirr_bizdays(dates, amounts)

        # Calculate expected XIRR with 252/365.25 ratio
        # If biz_days = 366 * BIZ_DAY_RATIO = 252.5 days
        # Then 10% calendar return becomes (1.10)^(365.25/366) ≈ 9.997% in biz day terms
        calendar_days = 366  # 2024 is a leap year
        biz_days = calendar_days * BIZ_DAY_RATIO

        # The XIRR solves: -1000 + 1100/(1+r)^(biz_days/252) = 0
        # So (1+r)^(biz_days/252) = 1.1
        # r = 1.1^(252/biz_days) - 1
        expected = (1.1 ** (252 / biz_days)) - 1

        assert abs(xirr_result - expected) < 1e-6, f"Expected {expected*100:.4f}%, got {xirr_result*100:.4f}%"


class TestRealDataIntegration:
    """Integration tests using real PDF data with variable time lengths."""

    @pytest.fixture
    def real_2024_data(self):
        """Load real 2024 PDF data."""
        from extractor import extract_data_from_pdf

        pdf_path = Path(__file__).parent / 'fixtures' / 'sample_extrato_2024.pdf'
        df_raw, df_contributions = extract_data_from_pdf(str(pdf_path))
        return df_raw, df_contributions

    @pytest.fixture
    def processed_2024_data(self, real_2024_data):
        """Process real data into position and contribution DataFrames."""
        from calculator import process_position_data, process_contributions_data

        df_raw, df_contributions = real_2024_data
        df_position = process_position_data(df_raw)
        df_contrib_monthly = process_contributions_data(df_contributions)
        return df_position, df_contributions, df_contrib_monthly

    def test_xirr_stability_across_periods(self, real_2024_data):
        """Test that XIRR calculation produces valid results across different periods.

        Note: Very short periods may produce extreme results due to the nature
        of XIRR calculations. We test that longer periods (6+ months) produce
        reasonable results.
        """
        from calculator import xirr_bizdays, process_position_data

        df_raw, df_contributions = real_2024_data
        df_position = process_position_data(df_raw)

        # Test different period lengths starting from 6 months (more stable)
        period_months = [6, 9, len(df_contributions)]
        xirr_results = []

        for months in period_months:
            if months > len(df_contributions):
                continue

            # Get subset of data
            contrib_subset = df_contributions.iloc[:months]
            pos_subset = df_position[df_position['data'] <= contrib_subset['data'].max()]

            if len(pos_subset) == 0:
                continue

            # Prepare XIRR inputs
            dates = contrib_subset['data'].tolist() + [pos_subset['data'].iloc[-1]]
            amounts = [-amt for amt in contrib_subset['contribuicao_total'].tolist()]
            amounts.append(pos_subset['posicao'].iloc[-1])

            xirr_result = xirr_bizdays(dates, amounts)

            if xirr_result is not None:
                xirr_results.append((months, xirr_result * 100))

        # XIRRs for 6+ months should be calculable and reasonable
        for months, xirr_pct in xirr_results:
            assert -100 < xirr_pct < 200, f"XIRR for {months} months is unreasonable: {xirr_pct:.2f}%"

        # Should have at least one valid result
        assert len(xirr_results) > 0, "No valid XIRR results calculated"

    def test_overhead_consistency_across_periods(self, real_2024_data):
        """Test that overhead application is consistent across time periods."""
        from calculator import BIZ_DAY_RATIO

        df_raw, df_contributions = real_2024_data

        # Create flat benchmark matching contribution dates
        dates = df_contributions['data'].unique()
        flat_benchmark = pd.DataFrame({
            'date': pd.to_datetime(dates),
            'value': [1.0] * len(dates)
        }).sort_values('date')

        # Apply 5% overhead
        result = apply_overhead_to_benchmark(flat_benchmark, 5.0)

        # For each period, verify the overhead formula is consistent
        first_date = result['date'].iloc[0]
        for _, row in result.iterrows():
            calendar_days = (row['date'] - first_date).days
            biz_days = calendar_days * BIZ_DAY_RATIO
            expected = 1.0 * (1.05 ** (biz_days / 252))

            assert abs(row['value'] - expected) < 1e-10, \
                f"Overhead mismatch at {row['date']}: got {row['value']}, expected {expected}"

    def test_deflation_consistency_with_real_data(self, real_2024_data):
        """Test deflation calculations with real data structure."""
        from calculator import deflate_series, process_position_data

        df_raw, df_contributions = real_2024_data
        df_position = process_position_data(df_raw)

        # Create synthetic inflation that matches position dates
        inflation_data = pd.DataFrame({
            'date': df_position['data'],
            'value': [1.0 + 0.005 * i for i in range(len(df_position))]  # ~0.5% monthly
        })

        # Deflate position data
        reference_date = df_position['data'].iloc[-1]
        df_deflated = deflate_series(df_position, inflation_data, reference_date, 'posicao')

        # Verify deflation produces reasonable results
        assert 'posicao_real' in df_deflated.columns
        assert len(df_deflated) == len(df_position)

        # Real values should be less than or equal to nominal (deflating to last date)
        # Actually, when deflating to the latest date, earlier values get inflated
        # So real values for earlier dates should be >= nominal values
        for i, row in df_deflated.iterrows():
            if row['data'] < reference_date:
                # Earlier dates: real value should be higher (adjusted for inflation)
                assert row['posicao_real'] >= row['posicao'] * 0.95, \
                    f"Deflation error at {row['data']}"

    def test_variable_period_overhead_deflation(self, real_2024_data):
        """Test overhead + deflation combination across variable periods."""
        from calculator import deflate_series, CALENDAR_DAYS_PER_YEAR

        df_raw, df_contributions = real_2024_data

        # Create inflation index matching real data dates
        dates = pd.to_datetime(df_contributions['data'].unique())
        dates = pd.Series(dates).sort_values()

        # Simulate 5% annual inflation
        inflation_data = pd.DataFrame({
            'date': dates,
            'value': [(1.05 ** ((d - dates.iloc[0]).days / 365)) for d in dates]
        })

        # Apply 8% overhead to inflation (simulating IPCA+8%)
        ipca_plus_8 = apply_overhead_to_benchmark(inflation_data, 8.0)

        # Convert to position-like format and deflate
        df_position = pd.DataFrame({
            'data': ipca_plus_8['date'],
            'posicao': ipca_plus_8['value'] * 10000  # Scale up
        })

        reference_date = inflation_data['date'].iloc[-1]
        df_deflated = deflate_series(df_position, inflation_data, reference_date, 'posicao')

        # Calculate real return
        first_real = df_deflated['posicao_real'].iloc[0]
        last_real = df_deflated['posicao_real'].iloc[-1]
        calendar_days = (df_deflated['data'].iloc[-1] - df_deflated['data'].iloc[0]).days

        if calendar_days > 0:
            years = calendar_days / CALENDAR_DAYS_PER_YEAR
            real_return = ((last_real / first_real) ** (1 / years) - 1) * 100

            # Should be approximately 8% (the overhead we added)
            assert abs(real_return - 8.0) < 0.5, \
                f"Expected ~8% real return, got {real_return:.2f}%"


class TestComponentConsistency:
    """Tests to verify consistency between cards, graphs, and tables.

    Tests all 4 toggle configurations:
    - Company as mine: ON/OFF
    - Inflation adjustment: ON/OFF
    """

    @pytest.fixture
    def real_data_full(self):
        """Load real 2024 PDF data with all processing."""
        from extractor import extract_data_from_pdf
        from calculator import process_position_data, process_contributions_data

        pdf_path = Path(__file__).parent / 'fixtures' / 'sample_extrato_2024.pdf'
        df_raw, df_contributions = extract_data_from_pdf(str(pdf_path))
        df_position = process_position_data(df_raw)
        df_contrib_monthly = process_contributions_data(df_contributions)

        return df_raw, df_position, df_contributions, df_contrib_monthly

    @pytest.fixture
    def inflation_index(self, real_data_full):
        """Create inflation index matching the data period."""
        _, df_position, _, _ = real_data_full

        # Create synthetic 5% annual inflation matching position dates
        dates = df_position['data']
        first_date = dates.iloc[0]
        inflation_data = pd.DataFrame({
            'date': dates,
            'value': [(1.05 ** ((d - first_date).days / 365)) for d in dates]
        })
        return inflation_data

    def _apply_company_toggle(self, df_contributions, company_as_mine):
        """Apply company toggle - if ON, set patrocinador to 0."""
        df = df_contributions.copy()
        if company_as_mine and 'contrib_patrocinador' in df.columns:
            # When company toggle is ON, we treat patrocinador as "free"
            # so it doesn't count as our contribution
            df['contribuicao_total'] = df['contrib_participante']
        return df

    @pytest.mark.parametrize("company_toggle,inflation_toggle", [
        (False, False),  # Both OFF
        (True, False),   # Company ON, Inflation OFF
        (False, True),   # Company OFF, Inflation ON
        (True, True),    # Both ON
    ])
    def test_card_matches_graph_all_configs(self, real_data_full, inflation_index,
                                             company_toggle, inflation_toggle):
        """Test card position matches graph last point for all toggle configs."""
        from calculator import calculate_summary_stats, apply_deflation, process_contributions_data

        _, df_position, df_contributions, df_contrib_monthly = real_data_full

        # Apply company toggle
        df_contrib_adjusted = self._apply_company_toggle(df_contributions, company_toggle)
        df_contrib_monthly_adj = process_contributions_data(df_contrib_adjusted)

        # Apply inflation toggle
        if inflation_toggle:
            reference_date = df_position['data'].iloc[-1]
            df_pos_final, df_contrib_final = apply_deflation(
                df_position.copy(), df_contrib_adjusted.copy(),
                inflation_index, reference_date
            )
        else:
            df_pos_final = df_position.copy()
            df_contrib_final = df_contrib_adjusted.copy()

        # Recalculate monthly after deflation
        df_contrib_monthly_final = process_contributions_data(df_contrib_final)

        # Card value
        stats = calculate_summary_stats(df_pos_final, df_contrib_final, df_contrib_monthly_final)
        card_position = stats['last_position']

        # Graph last point
        graph_last = df_pos_final['posicao'].iloc[-1]

        config = f"company={company_toggle}, inflation={inflation_toggle}"
        assert abs(card_position - graph_last) < 0.01, \
            f"[{config}] Card ({card_position:.2f}) != Graph ({graph_last:.2f})"

    @pytest.mark.parametrize("company_toggle,inflation_toggle", [
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ])
    def test_total_contributed_matches_table_all_configs(self, real_data_full, inflation_index,
                                                          company_toggle, inflation_toggle):
        """Test total contributed matches table sum for all toggle configs."""
        from calculator import calculate_summary_stats, apply_deflation, process_contributions_data

        _, df_position, df_contributions, _ = real_data_full

        # Apply company toggle
        df_contrib_adjusted = self._apply_company_toggle(df_contributions, company_toggle)

        # Apply inflation toggle
        if inflation_toggle:
            reference_date = df_position['data'].iloc[-1]
            _, df_contrib_final = apply_deflation(
                df_position.copy(), df_contrib_adjusted.copy(),
                inflation_index, reference_date
            )
        else:
            df_contrib_final = df_contrib_adjusted.copy()

        df_contrib_monthly_final = process_contributions_data(df_contrib_final)

        # Card total
        stats = calculate_summary_stats(df_position, df_contrib_final, df_contrib_monthly_final)
        card_total = stats['total_contributed']

        # Table sum
        table_sum = df_contrib_monthly_final['contribuicao_total'].sum()

        config = f"company={company_toggle}, inflation={inflation_toggle}"
        assert abs(card_total - table_sum) < 0.01, \
            f"[{config}] Card total ({card_total:.2f}) != Table sum ({table_sum:.2f})"

    @pytest.mark.parametrize("company_toggle,inflation_toggle", [
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ])
    def test_cagr_consistent_all_configs(self, real_data_full, inflation_index,
                                          company_toggle, inflation_toggle):
        """Test CAGR calculation is consistent for all toggle configs."""
        from calculator import (calculate_summary_stats, apply_deflation,
                               process_contributions_data, xirr_bizdays)

        _, df_position, df_contributions, _ = real_data_full

        # Apply company toggle
        df_contrib_adjusted = self._apply_company_toggle(df_contributions, company_toggle)

        # Apply inflation toggle
        if inflation_toggle:
            reference_date = df_position['data'].iloc[-1]
            df_pos_final, df_contrib_final = apply_deflation(
                df_position.copy(), df_contrib_adjusted.copy(),
                inflation_index, reference_date
            )
        else:
            df_pos_final = df_position.copy()
            df_contrib_final = df_contrib_adjusted.copy()

        df_contrib_monthly_final = process_contributions_data(df_contrib_final)

        # Card CAGR
        stats = calculate_summary_stats(df_pos_final, df_contrib_final, df_contrib_monthly_final)
        card_cagr = stats['cagr_pct']

        # Manual XIRR
        dates = df_contrib_final['data'].tolist() + [df_pos_final['data'].iloc[-1]]
        amounts = [-amt for amt in df_contrib_final['contribuicao_total'].tolist()]
        amounts.append(df_pos_final['posicao'].iloc[-1])

        manual_xirr = xirr_bizdays(dates, amounts)
        manual_cagr = manual_xirr * 100 if manual_xirr else None

        config = f"company={company_toggle}, inflation={inflation_toggle}"
        if card_cagr is not None and manual_cagr is not None:
            assert abs(card_cagr - manual_cagr) < 0.01, \
                f"[{config}] Card CAGR ({card_cagr:.2f}%) != Manual ({manual_cagr:.2f}%)"

    @pytest.mark.parametrize("company_toggle,inflation_toggle", [
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ])
    def test_cumulative_contribution_consistency(self, real_data_full, inflation_index,
                                                  company_toggle, inflation_toggle):
        """Test cumulative contributions in table are internally consistent."""
        from calculator import apply_deflation, process_contributions_data

        _, df_position, df_contributions, _ = real_data_full

        # Apply toggles
        df_contrib_adjusted = self._apply_company_toggle(df_contributions, company_toggle)

        if inflation_toggle:
            reference_date = df_position['data'].iloc[-1]
            _, df_contrib_final = apply_deflation(
                df_position.copy(), df_contrib_adjusted.copy(),
                inflation_index, reference_date
            )
        else:
            df_contrib_final = df_contrib_adjusted.copy()

        df_contrib_monthly = process_contributions_data(df_contrib_final)

        # Verify cumulative sum
        running_sum = 0
        config = f"company={company_toggle}, inflation={inflation_toggle}"

        for _, row in df_contrib_monthly.iterrows():
            running_sum += row['contribuicao_total']
            assert abs(row['contribuicao_acumulada'] - running_sum) < 0.01, \
                f"[{config}] Cumulative mismatch at {row['data']}"


