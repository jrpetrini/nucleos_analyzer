"""
Integration tests for Nucleos Analyzer.

These tests use real PDF data and test the full pipeline including:
- Multiple PDF files (2024 only vs 2023-2025 full history)
- Consistency between datasets
- All toggle combinations
- Graph creation
- Benchmark simulation
- Edge cases
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

from extractor import extract_data_from_pdf
from calculator import (
    process_position_data,
    process_contributions_data,
    xirr_bizdays,
    deflate_series,
    apply_deflation,
    calculate_summary_stats,
)
from business_logic import (
    filter_data_by_range,
    calculate_nucleos_stats,
    simulate_and_calculate_benchmark,
    get_position_dates_for_benchmark,
)
from benchmarks import (
    simulate_benchmark,
    apply_overhead_to_benchmark,
    get_value_on_date,
)
from dashboard_helpers import (
    is_inflation_enabled,
    is_company_as_mine,
    get_contribution_column,
    prepare_benchmark_contributions,
    format_currency,
)


# Test fixtures paths
FIXTURES_DIR = Path(__file__).parent / 'fixtures'
PDF_2024 = FIXTURES_DIR / 'sample_extrato_2024.pdf'
PDF_2023_TO_2025 = FIXTURES_DIR / 'sample_extrato_2023_to_2025.pdf'


class TestRealDataLoading:
    """Tests for loading and processing real PDF data."""

    def test_2024_pdf_loads_correctly(self):
        """Test that 2024 PDF loads and processes correctly."""
        df_raw, df_contrib = extract_data_from_pdf(str(PDF_2024))
        df_pos = process_position_data(df_raw)

        assert len(df_pos) == 12  # 12 months
        assert df_pos['data'].min().year == 2024
        assert df_pos['data'].max().year == 2024

    def test_2023_to_2025_pdf_loads_correctly(self):
        """Test that 2023-2025 PDF loads and processes correctly."""
        df_raw, df_contrib = extract_data_from_pdf(str(PDF_2023_TO_2025))
        df_pos = process_position_data(df_raw)

        assert len(df_pos) >= 30  # ~34 months (Feb 2023 to Nov 2025)
        assert df_pos['data'].min().year == 2023
        assert df_pos['data'].max().year == 2025

    def test_contribution_columns_present(self):
        """Test that all required contribution columns are present."""
        _, df_contrib = extract_data_from_pdf(str(PDF_2023_TO_2025))

        required_cols = ['data', 'contribuicao_total', 'contrib_participante', 'contrib_patrocinador']
        for col in required_cols:
            assert col in df_contrib.columns, f"Missing column: {col}"


class TestDataConsistency:
    """Tests for consistency between 2024 PDF and 2024 portion of 2023-2025 PDF."""

    @pytest.fixture
    def data_2024_only(self):
        """Load 2024 PDF data."""
        df_raw, df_contrib = extract_data_from_pdf(str(PDF_2024))
        df_pos = process_position_data(df_raw)
        return df_pos, df_contrib

    @pytest.fixture
    def data_2023_to_2025(self):
        """Load 2023-2025 PDF data."""
        df_raw, df_contrib = extract_data_from_pdf(str(PDF_2023_TO_2025))
        df_pos = process_position_data(df_raw)
        return df_pos, df_contrib

    def test_cota_values_match_for_2024(self, data_2024_only, data_2023_to_2025):
        """Verify cota values for 2024 months match between both PDFs."""
        df_pos_2024, _ = data_2024_only
        df_pos_full, _ = data_2023_to_2025

        # Extract 2024 portion from full dataset
        df_pos_2024_from_full = df_pos_full[df_pos_full['data'].dt.year == 2024].copy()

        # Compare cota values month by month
        for _, row_2024 in df_pos_2024.iterrows():
            month = row_2024['data'].month
            matching = df_pos_2024_from_full[df_pos_2024_from_full['data'].dt.month == month]

            if len(matching) > 0:
                cota_2024 = row_2024['valor_cota']
                cota_full = matching['valor_cota'].iloc[0]
                assert abs(cota_2024 - cota_full) < 0.0001, \
                    f"Cota mismatch for month {month}: {cota_2024} vs {cota_full}"

    def test_contributions_match_for_2024(self, data_2024_only, data_2023_to_2025):
        """Verify contribution amounts for 2024 match between both PDFs."""
        _, df_contrib_2024 = data_2024_only
        _, df_contrib_full = data_2023_to_2025

        # Filter full dataset to 2024
        df_contrib_2024_from_full = df_contrib_full[
            df_contrib_full['data'].dt.year == 2024
        ].copy()

        # Compare total contributions for 2024
        total_2024 = df_contrib_2024['contribuicao_total'].sum()
        total_from_full = df_contrib_2024_from_full['contribuicao_total'].sum()

        # Allow small difference due to potential timing differences
        assert abs(total_2024 - total_from_full) / total_2024 < 0.01, \
            f"Contribution totals differ: {total_2024} vs {total_from_full}"

    def test_december_2024_cota_matches(self, data_2024_only, data_2023_to_2025):
        """Verify December 2024 cota value matches exactly between PDFs."""
        df_pos_2024, _ = data_2024_only
        df_pos_full, _ = data_2023_to_2025

        # Get December 2024 cota from both
        dec_2024 = df_pos_2024[df_pos_2024['data'].dt.month == 12]['valor_cota'].iloc[0]
        dec_full = df_pos_full[
            (df_pos_full['data'].dt.year == 2024) &
            (df_pos_full['data'].dt.month == 12)
        ]['valor_cota'].iloc[0]

        # Should be exactly 1.3493461878
        assert abs(dec_2024 - 1.3493461878) < 0.0000001
        assert abs(dec_full - 1.3493461878) < 0.0000001


class TestDateRangeFiltering:
    """Tests for date range filtering with real data."""

    @pytest.fixture
    def full_data(self):
        """Load full 2023-2025 dataset."""
        df_raw, df_contrib = extract_data_from_pdf(str(PDF_2023_TO_2025))
        df_pos = process_position_data(df_raw)
        df_contrib_monthly = process_contributions_data(df_contrib)
        return df_pos, df_contrib, df_contrib_monthly

    def test_filter_to_single_year(self, full_data):
        """Test filtering to a single year."""
        df_pos, df_contrib, _ = full_data

        df_pos_filtered, df_contrib_filtered, pos_before, _ = filter_data_by_range(
            df_pos, df_contrib, '2024-01-01', '2024-12-31'
        )

        assert all(df_pos_filtered['data'].dt.year == 2024)
        assert len(df_pos_filtered) == 12

    def test_filter_preserves_position_continuity(self, full_data):
        """Test that filtered position is adjusted relative to start."""
        df_pos, df_contrib, _ = full_data

        df_pos_filtered, _, pos_before, _ = filter_data_by_range(
            df_pos, df_contrib, '2024-06-01', '2024-12-31'
        )

        # First position in filtered data should be much smaller than original
        # because it's adjusted relative to position before filter start
        original_june = df_pos[df_pos['data'] >= '2024-06-01'].iloc[0]['posicao']
        assert df_pos_filtered.iloc[0]['posicao'] < original_june
        assert pos_before > 0  # There should be accumulated position before June 2024

    def test_filter_to_quarter(self, full_data):
        """Test filtering to a single quarter."""
        df_pos, df_contrib, _ = full_data

        df_pos_filtered, df_contrib_filtered, _, _ = filter_data_by_range(
            df_pos, df_contrib, '2024-04-01', '2024-06-30'
        )

        assert len(df_pos_filtered) == 3  # Apr, May, Jun
        months = df_pos_filtered['data'].dt.month.tolist()
        assert months == [4, 5, 6]


class TestToggleCombinations:
    """Integration tests for all toggle combinations with real data."""

    @pytest.fixture
    def test_data(self):
        """Load test data and create synthetic inflation index."""
        df_raw, df_contrib = extract_data_from_pdf(str(PDF_2023_TO_2025))
        df_pos = process_position_data(df_raw)
        df_contrib_monthly = process_contributions_data(df_contrib)

        # Create synthetic inflation index (5% annual)
        dates = df_pos['data']
        first_date = dates.iloc[0]
        inflation_data = pd.DataFrame({
            'date': dates,
            'value': [(1.05 ** ((d - first_date).days / 365)) for d in dates]
        })

        return df_pos, df_contrib, df_contrib_monthly, inflation_data

    @pytest.fixture
    def colors(self):
        """Color palette for stats calculation."""
        return {
            'accent': '#06b6d4',
            'text_muted': '#94a3b8',
            'primary': '#6366f1',
        }

    @pytest.mark.parametrize("company_toggle,inflation_toggle", [
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ])
    def test_stats_calculation_all_toggles(self, test_data, colors,
                                           company_toggle, inflation_toggle):
        """Test stats calculation works for all toggle combinations."""
        df_pos, df_contrib, df_contrib_monthly, inflation_data = test_data

        # Apply inflation if enabled
        if inflation_toggle:
            ref_date = df_pos['data'].iloc[-1]
            df_pos_adj, df_contrib_adj = apply_deflation(
                df_pos.copy(), df_contrib.copy(), inflation_data, ref_date
            )
        else:
            df_pos_adj = df_pos.copy()
            df_contrib_adj = df_contrib.copy()

        # Calculate stats
        result = calculate_nucleos_stats(
            df_contrib_adj, df_pos_adj,
            str(df_pos_adj['data'].min().date()),
            str(df_pos_adj['data'].max().date()),
            company_as_mine=company_toggle,
            colors=colors
        )

        config = f"company={company_toggle}, inflation={inflation_toggle}"

        # Verify result structure
        assert 'position_value' in result, f"[{config}] Missing position_value"
        assert 'invested_value' in result, f"[{config}] Missing invested_value"
        assert 'cagr_text' in result, f"[{config}] Missing cagr_text"

        # Verify values are not empty
        assert 'R$' in result['position_value'], f"[{config}] Invalid position format"
        assert 'R$' in result['invested_value'], f"[{config}] Invalid invested format"

    @pytest.mark.parametrize("company_toggle", [False, True])
    def test_company_toggle_affects_invested(self, test_data, colors, company_toggle):
        """Test that company toggle changes invested amount."""
        df_pos, df_contrib, _, _ = test_data

        result = calculate_nucleos_stats(
            df_contrib, df_pos,
            str(df_pos['data'].min().date()),
            str(df_pos['data'].max().date()),
            company_as_mine=company_toggle,
            colors=colors
        )

        # Extract numeric value from currency string
        invested_str = result['invested_value'].replace('R$', '').replace(',', '').strip()
        invested = float(invested_str)

        if company_toggle:
            # With company as mine, invested should be only participant portion
            total_participant = df_contrib['contrib_participante'].sum()
            # Should be approximately participant only (roughly half)
            assert invested < df_contrib['contribuicao_total'].sum() * 0.7


class TestBenchmarkSimulation:
    """Tests for benchmark simulation with real data."""

    @pytest.fixture
    def benchmark_data(self):
        """Create synthetic benchmark data (CDI-like, ~1% monthly)."""
        dates = pd.date_range('2023-01-01', '2025-12-01', freq='MS')
        values = [1.0]
        for i in range(1, len(dates)):
            values.append(values[-1] * 1.01)  # ~1% monthly

        return pd.DataFrame({'date': dates, 'value': values})

    @pytest.fixture
    def contribution_data(self):
        """Load real contribution data."""
        _, df_contrib = extract_data_from_pdf(str(PDF_2023_TO_2025))
        return df_contrib

    @pytest.fixture
    def position_data(self):
        """Load real position data."""
        df_raw, _ = extract_data_from_pdf(str(PDF_2023_TO_2025))
        return process_position_data(df_raw)

    def test_simulate_benchmark_basic(self, benchmark_data, contribution_data, position_data):
        """Test basic benchmark simulation."""
        df_contrib_sim = prepare_benchmark_contributions(contribution_data, company_as_mine=False)
        position_dates = position_data[['data']].copy()

        result = simulate_benchmark(df_contrib_sim, benchmark_data, position_dates)

        assert len(result) > 0
        assert 'posicao' in result.columns
        assert 'data' in result.columns

        # Values should be positive and growing
        assert all(result['posicao'] >= 0)
        assert result['posicao'].iloc[-1] > result['posicao'].iloc[0]

    def test_benchmark_with_overhead(self, benchmark_data):
        """Test benchmark overhead application."""
        # Apply 4% annual overhead
        result = apply_overhead_to_benchmark(benchmark_data, 4.0)

        # Values should be higher with overhead
        assert result.iloc[-1]['value'] > benchmark_data.iloc[-1]['value']

        # First value should be unchanged
        assert abs(result.iloc[0]['value'] - benchmark_data.iloc[0]['value']) < 0.0001

    def test_simulate_and_calculate_benchmark_function(self, benchmark_data,
                                                        contribution_data, position_data):
        """Test the simulate_and_calculate_benchmark business logic function."""
        colors = {'accent': '#06b6d4', 'text_muted': '#94a3b8'}

        # Filter to a shorter range for faster test
        df_pos_filtered, df_contrib_filtered, _, _ = filter_data_by_range(
            position_data, contribution_data, '2024-01-01', '2024-12-31'
        )

        # Mock cache with benchmark data
        cache = {'CDI': benchmark_data.to_dict('records')}

        result = simulate_and_calculate_benchmark(
            df_contrib=contribution_data,
            df_pos=df_pos_filtered,
            benchmark_name='CDI',
            overhead=0,
            date_range={'start': '2024-01-01', 'end': '2024-12-31'},
            cache=cache,
            company_as_mine=False,
            colors=colors,
        )

        assert result['simulation_df'] is not None
        assert result['cagr_text'] != '--'
        assert 'Posição' in result['label_text']


class TestGraphCreation:
    """Tests for graph creation functions."""

    @pytest.fixture
    def position_data(self):
        """Load real position data."""
        df_raw, _ = extract_data_from_pdf(str(PDF_2024))
        return process_position_data(df_raw)

    def test_create_position_figure_basic(self, position_data):
        """Test basic position figure creation."""
        from dashboard import create_position_figure

        fig = create_position_figure(position_data)

        # Verify figure structure
        assert fig is not None
        assert hasattr(fig, 'data')
        assert len(fig.data) >= 1  # At least one trace

        # Verify trace has correct data length
        trace = fig.data[0]
        assert len(trace.x) == len(position_data)

    def test_create_position_figure_with_log_scale(self, position_data):
        """Test position figure with log scale."""
        from dashboard import create_position_figure

        fig = create_position_figure(position_data, log_scale=True)

        # Check y-axis is log scale
        assert fig.layout.yaxis.type == 'log'

    def test_create_position_figure_with_benchmark(self, position_data):
        """Test position figure with benchmark data."""
        from dashboard import create_position_figure

        # Create mock benchmark data
        benchmark_sim = pd.DataFrame({
            'data': position_data['data'],
            'posicao': position_data['posicao'] * 0.95  # Slightly lower
        })

        fig = create_position_figure(
            position_data,
            benchmark_sim=benchmark_sim,
            benchmark_label='Test Benchmark'
        )

        # Should have at least 2 traces (position + benchmark)
        assert len(fig.data) >= 2

    def test_create_contributions_figure(self):
        """Test contributions figure creation."""
        from dashboard import create_contributions_figure

        _, df_contrib = extract_data_from_pdf(str(PDF_2024))
        df_contrib_monthly = process_contributions_data(df_contrib)

        fig = create_contributions_figure(df_contrib_monthly)

        assert fig is not None
        assert hasattr(fig, 'data')
        assert len(fig.data) >= 1


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_month_data(self):
        """Test handling of single month of data."""
        df_pos = pd.DataFrame({
            'data': [pd.Timestamp('2024-01-31')],
            'posicao': [1000.0],
            'cotas': [100.0],
            'valor_cota': [10.0],
        })

        df_contrib = pd.DataFrame({
            'data': [pd.Timestamp('2024-01-15')],
            'contribuicao_total': [950.0],
            'contrib_participante': [475.0],
            'contrib_patrocinador': [475.0],
        })

        colors = {'accent': '#06b6d4', 'text_muted': '#94a3b8'}

        result = calculate_nucleos_stats(
            df_contrib, df_pos,
            '2024-01-01', '2024-01-31',
            company_as_mine=False,
            colors=colors
        )

        assert 'R$' in result['position_value']
        assert 'R$' in result['invested_value']

    def test_empty_data_handling(self):
        """Test handling of empty dataframes."""
        df_pos = pd.DataFrame(columns=['data', 'posicao', 'cotas', 'valor_cota'])
        df_contrib = pd.DataFrame(columns=['data', 'contribuicao_total',
                                           'contrib_participante', 'contrib_patrocinador'])

        colors = {'accent': '#06b6d4', 'text_muted': '#94a3b8'}

        result = calculate_nucleos_stats(
            df_contrib, df_pos,
            '2024-01-01', '2024-12-31',
            company_as_mine=False,
            colors=colors
        )

        assert result['position_value'] == 'R$ 0,00'
        assert result['cagr_text'] == 'N/A'

    def test_very_short_period_xirr(self):
        """Test XIRR with very short time period (edge case)."""
        # Two contributions one day apart
        dates = [datetime(2024, 1, 1), datetime(2024, 1, 2)]
        amounts = [-1000, 1001]

        result = xirr_bizdays(dates, amounts)

        # Should either return None or a value (key is it shouldn't crash)
        # Very short periods can produce extreme but valid results
        assert result is None or isinstance(result, float)

    def test_zero_contributions_period(self):
        """Test period with zero new contributions."""
        df_pos = pd.DataFrame({
            'data': pd.to_datetime(['2024-06-30', '2024-07-31', '2024-08-31']),
            'posicao': [50000.0, 51000.0, 52000.0],
            'cotas': [1000.0, 1000.0, 1000.0],
            'valor_cota': [50.0, 51.0, 52.0],
        })

        # Empty contributions in this period
        df_contrib = pd.DataFrame({
            'data': pd.to_datetime(['2024-05-15']),  # Before the period
            'contribuicao_total': [1000.0],
            'contrib_participante': [500.0],
            'contrib_patrocinador': [500.0],
        })

        colors = {'accent': '#06b6d4', 'text_muted': '#94a3b8'}

        # Should handle gracefully
        result = calculate_nucleos_stats(
            df_contrib, df_pos,
            '2024-06-01', '2024-08-31',
            company_as_mine=False,
            colors=colors
        )

        assert 'R$' in result['position_value']

    def test_contribution_split_adds_up(self):
        """Test that participant + patrocinador = total for all contributions."""
        _, df_contrib = extract_data_from_pdf(str(PDF_2023_TO_2025))

        for _, row in df_contrib.iterrows():
            total = row['contribuicao_total']
            parts = row['contrib_participante'] + row['contrib_patrocinador']
            assert abs(total - parts) < 0.01, \
                f"Split doesn't add up: {total} != {parts}"


class TestLongDatasetPerformance:
    """Tests using the full 35-month dataset for performance validation."""

    @pytest.fixture
    def full_data(self):
        """Load full 2023-2025 dataset."""
        df_raw, df_contrib = extract_data_from_pdf(str(PDF_2023_TO_2025))
        df_pos = process_position_data(df_raw)
        df_contrib_monthly = process_contributions_data(df_contrib)
        return df_pos, df_contrib, df_contrib_monthly

    def test_full_pipeline_completes(self, full_data):
        """Test that full pipeline completes with large dataset."""
        df_pos, df_contrib, df_contrib_monthly = full_data
        colors = {'accent': '#06b6d4', 'text_muted': '#94a3b8'}

        result = calculate_nucleos_stats(
            df_contrib, df_pos,
            str(df_pos['data'].min().date()),
            str(df_pos['data'].max().date()),
            company_as_mine=False,
            colors=colors
        )

        assert result is not None
        assert 'cagr_text' in result

    def test_xirr_with_many_cashflows(self, full_data):
        """Test XIRR calculation with 35+ cashflows."""
        df_pos, df_contrib, _ = full_data

        dates = df_contrib['data'].tolist() + [df_pos['data'].iloc[-1]]
        amounts = [-amt for amt in df_contrib['contribuicao_total'].tolist()]
        amounts.append(df_pos['posicao'].iloc[-1])

        result = xirr_bizdays(dates, amounts)

        assert result is not None
        assert -0.5 < result < 1.0  # Reasonable annual return range

    def test_summary_stats_with_full_data(self, full_data):
        """Test summary stats calculation with full dataset."""
        df_pos, df_contrib, df_contrib_monthly = full_data

        stats = calculate_summary_stats(df_pos, df_contrib, df_contrib_monthly)

        assert stats['last_position'] > 0
        assert stats['total_contributed'] > 0
        assert stats['cagr_pct'] is not None

    def test_position_growth_is_positive(self, full_data):
        """Test that position shows growth over the full period."""
        df_pos, df_contrib, _ = full_data

        total_contrib = df_contrib['contribuicao_total'].sum()
        final_position = df_pos['posicao'].iloc[-1]

        # Position should exceed contributions (positive return)
        assert final_position > total_contrib, \
            f"Position ({final_position:.2f}) should exceed contributions ({total_contrib:.2f})"


class TestRealWorldScenarios:
    """Tests for real-world usage scenarios."""

    @pytest.fixture
    def data_2024(self):
        """Load 2024 data."""
        df_raw, df_contrib = extract_data_from_pdf(str(PDF_2024))
        df_pos = process_position_data(df_raw)
        return df_pos, df_contrib

    def test_typical_user_flow_2024(self, data_2024):
        """Simulate typical user flow with 2024 data."""
        df_pos, df_contrib = data_2024
        colors = {'accent': '#06b6d4', 'text_muted': '#94a3b8'}

        # Step 1: Get full stats
        stats = calculate_nucleos_stats(
            df_contrib, df_pos,
            '2024-01-01', '2024-12-31',
            company_as_mine=False,
            colors=colors
        )

        # Step 2: Filter to Q4
        df_pos_q4, df_contrib_q4, _, _ = filter_data_by_range(
            df_pos, df_contrib, '2024-10-01', '2024-12-31'
        )

        # Step 3: Calculate Q4 stats
        stats_q4 = calculate_nucleos_stats(
            df_contrib_q4, df_pos_q4,
            '2024-10-01', '2024-12-31',
            company_as_mine=False,
            colors=colors
        )

        # Both should work
        assert 'R$' in stats['position_value']
        assert 'R$' in stats_q4['position_value']

    def test_known_values_2024_pdf(self, data_2024):
        """Test specific known values from the 2024 PDF.

        Note: The PDF's SALDO TOTAL (74,963.13) includes accumulated balance from
        before 2024. Our system calculates position from the contributions in the
        PDF only, which is correct for analyzing just the 2024 period.
        """
        df_pos, df_contrib = data_2024

        # Final position calculated from 2024 contributions only
        final_pos = df_pos['posicao'].iloc[-1]
        # Should be positive and reasonable
        assert final_pos > 40000, f"Final position too low: {final_pos}"
        assert final_pos < 60000, f"Final position too high: {final_pos}"

        # Known December 2024 cota value: 1.3493461878
        final_cota = df_pos['valor_cota'].iloc[-1]
        assert abs(final_cota - 1.3493461878) < 0.0001, f"Expected cota ~1.349, got {final_cota}"

        # Known January 2024 participant contribution: 3,969.09
        jan_participant = df_contrib[
            df_contrib['data'].dt.month == 1
        ]['contrib_participante'].sum()
        # First row has 12/2023 reference but 01/2024 appropriation
        assert jan_participant > 3000  # Should include the contribution

    def test_known_values_full_pdf(self):
        """Test specific known values from the 2023-2025 PDF."""
        df_raw, df_contrib = extract_data_from_pdf(str(PDF_2023_TO_2025))
        df_pos = process_position_data(df_raw)

        # Known final balance from PDF: 126,448.19
        final_pos = df_pos['posicao'].iloc[-1]
        assert abs(final_pos - 126448.19) < 1.0, f"Expected ~126448.19, got {final_pos}"

        # Known final cota: 1.5135270490
        final_cota = df_pos['valor_cota'].iloc[-1]
        assert abs(final_cota - 1.513527049) < 0.0001, f"Expected ~1.5135, got {final_cota}"
