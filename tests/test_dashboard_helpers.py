"""
Tests for dashboard_helpers.py - Helper functions for dashboard callbacks.
"""

import pytest
import pandas as pd

from dashboard_helpers import (
    prepare_dataframe,
    is_inflation_enabled,
    is_company_as_mine,
    get_contribution_column,
    get_contribution_amounts,
    prepare_benchmark_contributions,
    build_deflator_dict,
    format_currency,
    format_percentage,
    get_cagr_color,
    get_return_color,
)


class TestPrepareDataframe:
    """Tests for prepare_dataframe function."""

    def test_converts_list_to_dataframe(self):
        """Test basic conversion from list of dicts to DataFrame."""
        data = [
            {'data': '2020-01-15', 'value': 100},
            {'data': '2020-02-15', 'value': 200},
        ]
        result = prepare_dataframe(data)

        assert len(result) == 2
        assert 'data' in result.columns
        assert 'value' in result.columns

    def test_parses_date_column(self):
        """Test that date column is parsed to datetime."""
        data = [{'data': '2020-01-15', 'value': 100}]
        result = prepare_dataframe(data)

        assert pd.api.types.is_datetime64_any_dtype(result['data'])

    def test_custom_date_column(self):
        """Test parsing with custom date column name."""
        data = [{'date': '2020-01-15', 'value': 100}]
        result = prepare_dataframe(data, date_column='date')

        assert pd.api.types.is_datetime64_any_dtype(result['date'])

    def test_none_data_returns_empty(self):
        """Test that None data returns empty DataFrame."""
        result = prepare_dataframe(None)
        assert result.empty

    def test_empty_list_returns_empty(self):
        """Test that empty list returns empty DataFrame."""
        result = prepare_dataframe([])
        assert result.empty


class TestToggleChecks:
    """Tests for toggle state checking functions."""

    def test_is_inflation_enabled_true(self):
        """Test inflation enabled with 'adjust' in list."""
        assert is_inflation_enabled(['adjust']) is True

    def test_is_inflation_enabled_false(self):
        """Test inflation disabled with empty list."""
        assert is_inflation_enabled([]) is False

    def test_is_inflation_enabled_none(self):
        """Test inflation disabled with None."""
        assert is_inflation_enabled(None) is False

    def test_is_company_as_mine_true(self):
        """Test company as mine with 'as_mine' in list."""
        assert is_company_as_mine(['as_mine']) is True

    def test_is_company_as_mine_false(self):
        """Test company as mine disabled with empty list."""
        assert is_company_as_mine([]) is False

    def test_is_company_as_mine_none(self):
        """Test company as mine disabled with None."""
        assert is_company_as_mine(None) is False


class TestContributionHelpers:
    """Tests for contribution-related helper functions."""

    @pytest.fixture
    def sample_contrib_df(self):
        """Sample contribution DataFrame."""
        return pd.DataFrame({
            'data': pd.to_datetime(['2020-01-15', '2020-02-15']),
            'contribuicao_total': [1000.0, 1000.0],
            'contrib_participante': [500.0, 500.0],
            'contrib_patrocinador': [500.0, 500.0],
        })

    def test_get_contribution_column_total(self, sample_contrib_df):
        """Test getting total column when company_as_mine is False."""
        result = get_contribution_column(sample_contrib_df, company_as_mine=False)
        assert result == 'contribuicao_total'

    def test_get_contribution_column_participant(self, sample_contrib_df):
        """Test getting participant column when company_as_mine is True."""
        result = get_contribution_column(sample_contrib_df, company_as_mine=True)
        assert result == 'contrib_participante'

    def test_get_contribution_column_fallback(self):
        """Test fallback to total when participant column missing."""
        df = pd.DataFrame({'contribuicao_total': [1000.0]})
        result = get_contribution_column(df, company_as_mine=True)
        assert result == 'contribuicao_total'

    def test_get_contribution_amounts_total(self, sample_contrib_df):
        """Test getting total amounts."""
        result = get_contribution_amounts(sample_contrib_df, company_as_mine=False)
        assert list(result) == [1000.0, 1000.0]

    def test_get_contribution_amounts_participant(self, sample_contrib_df):
        """Test getting participant amounts."""
        result = get_contribution_amounts(sample_contrib_df, company_as_mine=True)
        assert list(result) == [500.0, 500.0]

    def test_prepare_benchmark_contributions(self, sample_contrib_df):
        """Test preparing contributions for benchmark simulation."""
        result = prepare_benchmark_contributions(sample_contrib_df, company_as_mine=False)

        assert 'data' in result.columns
        assert 'contribuicao_total' in result.columns
        assert list(result['contribuicao_total']) == [1000.0, 1000.0]

    def test_prepare_benchmark_contributions_participant_only(self, sample_contrib_df):
        """Test preparing contributions with only participant amounts."""
        result = prepare_benchmark_contributions(sample_contrib_df, company_as_mine=True)

        assert list(result['contribuicao_total']) == [500.0, 500.0]

    def test_prepare_benchmark_contributions_empty(self):
        """Test preparing empty DataFrame."""
        result = prepare_benchmark_contributions(pd.DataFrame(), company_as_mine=False)

        assert result.empty
        assert 'data' in result.columns
        assert 'contribuicao_total' in result.columns


class TestBuildDeflatorDict:
    """Tests for build_deflator_dict function."""

    def test_builds_dict_from_dataframe(self):
        """Test building deflator dictionary."""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2020-01-01', '2020-02-01', '2020-03-01']),
            'value': [1.0, 1.005, 1.010]
        })
        result = build_deflator_dict(df)

        assert 'Jan 2020' in result
        assert 'Feb 2020' in result
        assert 'Mar 2020' in result
        assert result['Jan 2020'] == 1.0
        assert result['Feb 2020'] == 1.005

    def test_none_returns_empty_dict(self):
        """Test that None returns empty dictionary."""
        result = build_deflator_dict(None)
        assert result == {}

    def test_empty_df_returns_empty_dict(self):
        """Test that empty DataFrame returns empty dictionary."""
        result = build_deflator_dict(pd.DataFrame())
        assert result == {}

    def test_handles_string_dates(self):
        """Test that string dates are converted properly."""
        df = pd.DataFrame({
            'date': ['2020-01-01', '2020-02-01'],
            'value': [1.0, 1.005]
        })
        result = build_deflator_dict(df)

        assert 'Jan 2020' in result


class TestFormatFunctions:
    """Tests for formatting helper functions."""

    def test_format_currency_positive(self):
        """Test currency formatting for positive value."""
        result = format_currency(1234.56)
        assert result == "R$ 1,234.56"

    def test_format_currency_zero(self):
        """Test currency formatting for zero."""
        result = format_currency(0)
        assert result == "R$ 0.00"

    def test_format_currency_negative(self):
        """Test currency formatting for negative value."""
        result = format_currency(-500.00)
        assert result == "R$ -500.00"

    def test_format_percentage_positive(self):
        """Test percentage formatting for positive value."""
        result = format_percentage(10.5)
        assert result == "+10.50% a.a."

    def test_format_percentage_negative(self):
        """Test percentage formatting for negative value."""
        result = format_percentage(-5.25)
        assert result == "-5.25% a.a."

    def test_format_percentage_unsigned(self):
        """Test percentage formatting without sign."""
        result = format_percentage(10.5, signed=False)
        assert result == "10.50% a.a."


class TestColorHelpers:
    """Tests for color helper functions."""

    @pytest.fixture
    def colors(self):
        """Sample color palette."""
        return {
            'accent': '#06b6d4',
            'primary': '#6366f1',
        }

    def test_get_cagr_color_positive(self, colors):
        """Test CAGR color for positive value."""
        result = get_cagr_color(10.0, colors)
        assert result == colors['accent']

    def test_get_cagr_color_negative(self, colors):
        """Test CAGR color for negative value."""
        result = get_cagr_color(-5.0, colors)
        assert result == '#ef4444'

    def test_get_cagr_color_zero(self, colors):
        """Test CAGR color for zero."""
        result = get_cagr_color(0.0, colors)
        assert result == colors['accent']

    def test_get_cagr_color_none(self, colors):
        """Test CAGR color for None."""
        result = get_cagr_color(None, colors)
        assert result == colors['accent']

    def test_get_return_color_positive(self, colors):
        """Test return color for positive value."""
        result = get_return_color(100.0, colors)
        assert result == colors['accent']

    def test_get_return_color_negative(self, colors):
        """Test return color for negative value."""
        result = get_return_color(-100.0, colors)
        assert result == '#ef4444'
