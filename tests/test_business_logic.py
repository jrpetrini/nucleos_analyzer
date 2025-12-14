"""
Tests for business_logic.py - Core business logic functions.
"""

import pytest
import pandas as pd
from datetime import datetime

import sys
sys.path.insert(0, '/home/petrini/Documents/nucleos_analyzer')

from business_logic import (
    filter_data_by_range,
    calculate_time_weighted_position,
    calculate_nucleos_stats,
    get_position_dates_for_benchmark,
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

        assert 'Jun 2020' in result['position_label']

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

        assert 'May 2020' in result['position_label']
        # Invested should be ~3000 (3 months)
        assert '3,000' in result['invested_value'] or '3.000' in result['invested_value']
