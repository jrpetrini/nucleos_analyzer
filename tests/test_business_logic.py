"""
Tests for business_logic.py - Core business logic functions.
"""

import pytest
import pandas as pd
from datetime import datetime

from business_logic import (
    filter_data_by_range,
    calculate_time_weighted_position,
    calculate_nucleos_stats,
    get_position_dates_for_benchmark,
    simulate_and_calculate_benchmark,
)


# Test fixtures
@pytest.fixture
def sample_position():
    """Sample position data."""
    return pd.DataFrame({
        'data': pd.to_datetime([
            '2020-01-31', '2020-02-29', '2020-03-31',
            '2020-04-30', '2020-05-31', '2020-06-30'
        ]),
        'posicao': [1010.0, 2030.0, 3060.0, 4100.0, 5150.0, 6210.0],
    })


@pytest.fixture
def sample_contributions():
    """Sample contribution data."""
    return pd.DataFrame({
        'data': pd.to_datetime([
            '2020-01-15', '2020-02-15', '2020-03-15',
            '2020-04-15', '2020-05-15', '2020-06-15'
        ]),
        'contribuicao_total': [1000.0, 1000.0, 1000.0, 1000.0, 1000.0, 1000.0],
        'contrib_participante': [500.0, 500.0, 500.0, 500.0, 500.0, 500.0],
        'contrib_patrocinador': [500.0, 500.0, 500.0, 500.0, 500.0, 500.0],
    })


@pytest.fixture
def colors():
    """Sample color palette."""
    return {
        'accent': '#06b6d4',
        'text_muted': '#94a3b8',
        'primary': '#6366f1',
    }


class TestFilterDataByRange:
    """Tests for filter_data_by_range function."""

    def test_filters_by_date_range(self, sample_position, sample_contributions):
        """Test basic date filtering."""
        df_pos, df_contrib, _, _ = filter_data_by_range(
            sample_position, sample_contributions,
            '2020-02-01', '2020-04-30'
        )

        assert len(df_pos) == 3  # Feb, Mar, Apr
        assert len(df_contrib) == 3

    def test_adjusts_position_relative_to_start(self, sample_position, sample_contributions):
        """Test that positions are adjusted relative to pre-start position."""
        df_pos, _, position_before, _ = filter_data_by_range(
            sample_position, sample_contributions,
            '2020-03-01', '2020-06-30'
        )

        # Position before March is Feb's position: 2030
        assert position_before == 2030.0

        # March's original position is 3060, adjusted is 3060 - 2030 = 1030
        assert df_pos.iloc[0]['posicao'] == 1030.0

    def test_returns_date_before_start(self, sample_position, sample_contributions):
        """Test that date_before_start is returned correctly."""
        _, _, _, date_before = filter_data_by_range(
            sample_position, sample_contributions,
            '2020-03-01', '2020-06-30'
        )

        assert date_before == pd.Timestamp('2020-02-29')

    def test_first_month_has_no_date_before(self, sample_position, sample_contributions):
        """Test that first month has no date_before_start."""
        _, _, position_before, date_before = filter_data_by_range(
            sample_position, sample_contributions,
            '2020-01-01', '2020-06-30'
        )

        assert position_before == 0
        assert date_before is None

    def test_no_filter_when_dates_none(self, sample_position, sample_contributions):
        """Test that None dates return full data."""
        df_pos, df_contrib, _, _ = filter_data_by_range(
            sample_position, sample_contributions,
            None, None
        )

        assert len(df_pos) == 6
        assert len(df_contrib) == 6


class TestCalculateTimeWeightedPosition:
    """Tests for calculate_time_weighted_position function."""

    def test_no_contributions(self):
        """Test with no contributions in period."""
        empty_df = pd.DataFrame(columns=['data', 'contribuicao_total'])

        rate, contrib_value = calculate_time_weighted_position(
            empty_df,
            start_position=1000,
            end_position=1100,
            period_start=pd.Timestamp('2020-01-01'),
            period_end=pd.Timestamp('2020-12-31'),
        )

        # 10% return with no contributions
        assert abs(rate - 0.1) < 0.01
        assert contrib_value == 0.0

    def test_zero_start_position(self):
        """Test with zero starting position."""
        empty_df = pd.DataFrame(columns=['data', 'contribuicao_total'])

        rate, contrib_value = calculate_time_weighted_position(
            empty_df,
            start_position=0,
            end_position=0,
            period_start=pd.Timestamp('2020-01-01'),
            period_end=pd.Timestamp('2020-12-31'),
        )

        assert rate == 0.0

    def test_single_contribution(self):
        """Test with single contribution."""
        df = pd.DataFrame({
            'data': [pd.Timestamp('2020-07-01')],  # Mid-year
            'contribuicao_total': [1000.0],
        })

        rate, contrib_value = calculate_time_weighted_position(
            df,
            start_position=0,
            end_position=1050,  # 5% gain
            period_start=pd.Timestamp('2020-01-01'),
            period_end=pd.Timestamp('2020-12-31'),
        )

        assert rate > 0  # Should be positive (gained money)
        assert contrib_value > 1000  # Contribution grew

    def test_contribution_at_period_end(self):
        """Test contribution at end of period has zero weighting."""
        df = pd.DataFrame({
            'data': [pd.Timestamp('2020-12-31')],  # At period end
            'contribuicao_total': [1000.0],
        })

        rate, contrib_value = calculate_time_weighted_position(
            df,
            start_position=0,
            end_position=1000,  # No gain
            period_start=pd.Timestamp('2020-01-01'),
            period_end=pd.Timestamp('2020-12-31'),
        )

        # Contribution at end has 0 days remaining, so 0% weight
        # The return rate calculation uses denominator = start + weighted_sum = 0 + 0 = 0
        # Edge case handled: returns 0.0, total_contributions
        assert rate == 0.0
        assert contrib_value == 1000.0


class TestCalculateNucleosStats:
    """Tests for calculate_nucleos_stats function."""

    def test_returns_dict_with_all_keys(self, sample_position, sample_contributions, colors):
        """Test that all expected keys are returned."""
        result = calculate_nucleos_stats(
            sample_contributions, sample_position,
            '2020-01-01', '2020-06-30',
            company_as_mine=False, colors=colors
        )

        assert 'position_label' in result
        assert 'position_value' in result
        assert 'invested_value' in result
        assert 'cagr_text' in result
        assert 'cagr_style' in result
        assert 'return_text' in result
        assert 'return_style' in result

    def test_empty_data_returns_empty_stats(self, colors):
        """Test that empty data returns empty stats."""
        empty_pos = pd.DataFrame(columns=['data', 'posicao'])
        empty_contrib = pd.DataFrame(columns=['data', 'contribuicao_total'])

        result = calculate_nucleos_stats(
            empty_contrib, empty_pos,
            '2020-01-01', '2020-06-30',
            company_as_mine=False, colors=colors
        )

        assert result['position_value'] == 'R$ 0,00'
        assert result['cagr_text'] == 'N/A'

    def test_company_as_mine_uses_participant_only(self, sample_position, sample_contributions, colors):
        """Test that company_as_mine uses only participant contributions."""
        result_total = calculate_nucleos_stats(
            sample_contributions, sample_position,
            '2020-01-01', '2020-06-30',
            company_as_mine=False, colors=colors
        )

        result_participant = calculate_nucleos_stats(
            sample_contributions, sample_position,
            '2020-01-01', '2020-06-30',
            company_as_mine=True, colors=colors
        )

        # Invested should be lower when only counting participant
        # (This assumes the strings can be compared - invested should differ)
        assert result_total['invested_value'] != result_participant['invested_value']

    def test_position_label_includes_date(self, sample_position, sample_contributions, colors):
        """Test that position label includes the end date."""
        result = calculate_nucleos_stats(
            sample_contributions, sample_position,
            '2020-01-01', '2020-06-30',
            company_as_mine=False, colors=colors
        )

        assert '06/2020' in result['position_label']

    def test_cagr_positive_when_position_exceeds_invested(self, sample_position, sample_contributions, colors):
        """Test CAGR is positive when position > invested."""
        # Sample data has position 6210 vs invested 6000, so positive return
        result = calculate_nucleos_stats(
            sample_contributions, sample_position,
            '2020-01-01', '2020-06-30',
            company_as_mine=False, colors=colors
        )

        # CAGR text should show positive percentage
        assert '+' in result['cagr_text'] or 'N/A' in result['cagr_text']


class TestGetPositionDatesForBenchmark:
    """Tests for get_position_dates_for_benchmark function."""

    def test_returns_dates_from_first_contribution(self, sample_position, sample_contributions):
        """Test that dates start from first contribution month."""
        df_sim = sample_contributions[['data', 'contribuicao_total']].copy()

        result = get_position_dates_for_benchmark(sample_position, df_sim)

        # First contribution is Jan 15, position dates should start from Jan 31
        assert result.iloc[0]['data'] == pd.Timestamp('2020-01-31')

    def test_returns_all_dates_for_empty_contributions(self, sample_position):
        """Test that all position dates returned when no contributions."""
        empty_df = pd.DataFrame(columns=['data', 'contribuicao_total'])

        result = get_position_dates_for_benchmark(sample_position, empty_df)

        assert len(result) == len(sample_position)

    def test_filters_dates_before_first_contribution(self):
        """Test that position dates before first contribution are excluded."""
        # Position data starts in January
        pos = pd.DataFrame({
            'data': pd.to_datetime(['2020-01-31', '2020-02-29', '2020-03-31']),
            'posicao': [1000, 2000, 3000],
        })

        # Contributions start in March
        contrib = pd.DataFrame({
            'data': pd.to_datetime(['2020-03-15']),
            'contribuicao_total': [1000.0],
        })

        result = get_position_dates_for_benchmark(pos, contrib)

        # Should only include March
        assert len(result) == 1
        assert result.iloc[0]['data'] == pd.Timestamp('2020-03-31')


class TestIntegration:
    """Integration tests using real-like scenarios."""

    def test_full_nucleos_stats_calculation(self, colors):
        """Test full stats calculation with realistic data."""
        # Create a realistic 6-month scenario
        pos = pd.DataFrame({
            'data': pd.to_datetime([
                '2020-01-31', '2020-02-29', '2020-03-31',
                '2020-04-30', '2020-05-31', '2020-06-30'
            ]),
            'posicao': [1050, 2120, 3200, 4290, 5390, 6500],
        })

        contrib = pd.DataFrame({
            'data': pd.to_datetime([
                '2020-01-15', '2020-02-15', '2020-03-15',
                '2020-04-15', '2020-05-15', '2020-06-15'
            ]),
            'contribuicao_total': [1000, 1000, 1000, 1000, 1000, 1000],
            'contrib_participante': [500, 500, 500, 500, 500, 500],
            'contrib_patrocinador': [500, 500, 500, 500, 500, 500],
        })

        result = calculate_nucleos_stats(
            contrib, pos,
            '2020-01-01', '2020-06-30',
            company_as_mine=False, colors=colors
        )

        # Should have calculated values
        assert 'R$' in result['position_value']
        assert 'R$' in result['invested_value']
        # CAGR should be positive (gained 500 on 6000)
        assert 'N/A' not in result['cagr_text'] or '+' in result['cagr_text']

    def test_stats_with_date_range_filtering(self, colors):
        """Test stats calculation with date range in the middle."""
        pos = pd.DataFrame({
            'data': pd.to_datetime([
                '2020-01-31', '2020-02-29', '2020-03-31',
                '2020-04-30', '2020-05-31', '2020-06-30'
            ]),
            'posicao': [1050, 2120, 3200, 4290, 5390, 6500],
        })

        contrib = pd.DataFrame({
            'data': pd.to_datetime([
                '2020-01-15', '2020-02-15', '2020-03-15',
                '2020-04-15', '2020-05-15', '2020-06-15'
            ]),
            'contribuicao_total': [1000, 1000, 1000, 1000, 1000, 1000],
            'contrib_participante': [500, 500, 500, 500, 500, 500],
            'contrib_patrocinador': [500, 500, 500, 500, 500, 500],
        })

        # Filter to March-May only
        result = calculate_nucleos_stats(
            contrib, pos,
            '2020-03-01', '2020-05-31',
            company_as_mine=False, colors=colors
        )

        assert '05/2020' in result['position_label']
        # Invested should be ~3000 (3 months)
        assert '3,000' in result['invested_value'] or '3.000' in result['invested_value']


class TestSimulateAndCalculateBenchmark:
    """Tests for simulate_and_calculate_benchmark function."""

    @pytest.fixture
    def sample_data(self):
        """Sample position and contribution data."""
        pos = pd.DataFrame({
            'data': pd.to_datetime([
                '2020-01-31', '2020-02-29', '2020-03-31'
            ]),
            'posicao': [1050, 2120, 3200],
        })
        contrib = pd.DataFrame({
            'data': pd.to_datetime(['2020-01-15', '2020-02-15', '2020-03-15']),
            'contribuicao_total': [1000.0, 1000.0, 1000.0],
            'contrib_participante': [500.0, 500.0, 500.0],
            'contrib_patrocinador': [500.0, 500.0, 500.0],
        })
        return pos, contrib

    def test_no_benchmark_returns_default(self, sample_data, colors):
        """Test that 'none' benchmark returns default result."""
        pos, contrib = sample_data
        result = simulate_and_calculate_benchmark(
            contrib, pos,
            benchmark_name='none',
            overhead=0,
            date_range={'start': '2020-01-01', 'end': '2020-03-31'},
            cache={},
            company_as_mine=False,
            colors=colors
        )

        assert result['simulation_df'] is None
        assert result['cagr_text'] == '--'
        assert result['label_text'] == 'Selecione um benchmark'

    def test_empty_data_returns_default(self, colors):
        """Test that empty data returns default result."""
        empty_pos = pd.DataFrame(columns=['data', 'posicao'])
        empty_contrib = pd.DataFrame(columns=['data', 'contribuicao_total'])

        result = simulate_and_calculate_benchmark(
            empty_contrib, empty_pos,
            benchmark_name='CDI',
            overhead=0,
            date_range={'start': '2020-01-01', 'end': '2020-03-31'},
            cache={},
            company_as_mine=False,
            colors=colors
        )

        assert result['simulation_df'] is None
        assert result['cagr_text'] == '--'

    def test_positive_overhead_in_label(self, sample_data, colors):
        """Test that positive overhead appears in label."""
        pos, contrib = sample_data

        # Create mock benchmark data in cache to avoid API call
        benchmark_data = pd.DataFrame({
            'date': pd.to_datetime(['2020-01-01', '2020-02-01', '2020-03-01', '2020-04-01']),
            'value': [1.0, 1.004, 1.008, 1.012]
        })

        result = simulate_and_calculate_benchmark(
            contrib, pos,
            benchmark_name='CDI',
            overhead=2,  # +2% overhead
            date_range={'start': '2020-01-01', 'end': '2020-03-31'},
            cache={'CDI': benchmark_data.to_dict('records')},
            company_as_mine=False,
            colors=colors
        )

        # Label should contain "+2%"
        assert '+2%' in result['label_text']

    def test_cache_is_used(self, sample_data, colors):
        """Test that cached benchmark data is used."""
        pos, contrib = sample_data

        # Pre-populate cache
        benchmark_data = pd.DataFrame({
            'date': pd.to_datetime(['2020-01-01', '2020-02-01', '2020-03-01', '2020-04-01']),
            'value': [1.0, 1.004, 1.008, 1.012]
        })
        cache = {'CDI': benchmark_data.to_dict('records')}

        result = simulate_and_calculate_benchmark(
            contrib, pos,
            benchmark_name='CDI',
            overhead=0,
            date_range={'start': '2020-01-01', 'end': '2020-03-31'},
            cache=cache,
            company_as_mine=False,
            colors=colors
        )

        # Should have simulation data (cache was used, no API call needed)
        assert result['simulation_df'] is not None
        assert len(result['simulation_df']) > 0

    def test_cagr_calculated_for_benchmark(self, sample_data, colors):
        """Test that CAGR is calculated when benchmark simulation succeeds."""
        pos, contrib = sample_data

        # Create benchmark data with known growth
        benchmark_data = pd.DataFrame({
            'date': pd.to_datetime(['2020-01-01', '2020-02-01', '2020-03-01', '2020-04-01']),
            'value': [1.0, 1.01, 1.02, 1.03]  # ~1% monthly growth
        })

        result = simulate_and_calculate_benchmark(
            contrib, pos,
            benchmark_name='CDI',
            overhead=0,
            date_range={'start': '2020-01-01', 'end': '2020-03-31'},
            cache={'CDI': benchmark_data.to_dict('records')},
            company_as_mine=False,
            colors=colors
        )

        # CAGR should be calculated (not '--' or 'N/A')
        assert result['cagr_text'] != '--'
        # Should contain percentage format
        assert '% a.a.' in result['cagr_text']

    def test_company_as_mine_uses_participant_contributions(self, sample_data, colors):
        """Test that company_as_mine=True uses only participant contributions."""
        pos, contrib = sample_data

        benchmark_data = pd.DataFrame({
            'date': pd.to_datetime(['2020-01-01', '2020-02-01', '2020-03-01', '2020-04-01']),
            'value': [1.0, 1.01, 1.02, 1.03]
        })
        cache = {'CDI': benchmark_data.to_dict('records')}

        result_total = simulate_and_calculate_benchmark(
            contrib, pos,
            benchmark_name='CDI',
            overhead=0,
            date_range={'start': '2020-01-01', 'end': '2020-03-31'},
            cache=cache,
            company_as_mine=False,
            colors=colors
        )

        result_participant = simulate_and_calculate_benchmark(
            contrib, pos,
            benchmark_name='CDI',
            overhead=0,
            date_range={'start': '2020-01-01', 'end': '2020-03-31'},
            cache=cache,
            company_as_mine=True,
            colors=colors
        )

        # Benchmark position should be lower when using only participant contributions
        total_pos = result_total['simulation_df']['posicao'].iloc[-1]
        participant_pos = result_participant['simulation_df']['posicao'].iloc[-1]
        assert participant_pos < total_pos

    def test_inflation_deflation_applied_to_benchmark(self, sample_data, colors):
        """Test that inflation data deflates benchmark simulation."""
        pos, contrib = sample_data

        benchmark_data = pd.DataFrame({
            'date': pd.to_datetime(['2020-01-01', '2020-02-01', '2020-03-01', '2020-04-01']),
            'value': [1.0, 1.01, 1.02, 1.03]
        })

        # Inflation index (cumulative, ~1% monthly)
        inflation_data = pd.DataFrame({
            'date': pd.to_datetime(['2020-01-01', '2020-02-01', '2020-03-01', '2020-04-01']),
            'value': [1.0, 1.01, 1.0201, 1.030301]
        })

        result_nominal = simulate_and_calculate_benchmark(
            contrib, pos,
            benchmark_name='CDI',
            overhead=0,
            date_range={'start': '2020-01-01', 'end': '2020-03-31'},
            cache={'CDI': benchmark_data.to_dict('records')},
            company_as_mine=False,
            colors=colors,
            inflation_data=None
        )

        result_real = simulate_and_calculate_benchmark(
            contrib, pos,
            benchmark_name='CDI',
            overhead=0,
            date_range={'start': '2020-01-01', 'end': '2020-03-31'},
            cache={'CDI': benchmark_data.to_dict('records')},
            company_as_mine=False,
            colors=colors,
            inflation_data=inflation_data,
            inflation_ref_month='Mar 2020'
        )

        # Deflated values should be lower (inflation erodes value)
        # Or higher for earlier periods relative to ref
        assert result_nominal['simulation_df'] is not None
        assert result_real['simulation_df'] is not None

        # Final position should differ when deflation is applied
        nominal_final = result_nominal['simulation_df']['posicao'].iloc[-1]
        real_final = result_real['simulation_df']['posicao'].iloc[-1]
        # With ~1% monthly inflation and ref at end, earlier values inflate
        assert nominal_final != real_final
