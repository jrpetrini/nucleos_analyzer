"""
Tests for extractor.py - PDF extraction functionality.

Uses the redacted 2024 sample PDF which contains no personal information.
"""

import pytest
import pandas as pd
from pathlib import Path

from extractor import extract_data_from_pdf


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / 'fixtures'
SAMPLE_PDF = FIXTURES_DIR / 'sample_extrato_2024.pdf'


class TestExtractDataFromPdf:
    """Tests for the extract_data_from_pdf function using real PDF data."""

    @pytest.fixture(autouse=True)
    def check_fixture_exists(self):
        """Ensure the test PDF exists."""
        if not SAMPLE_PDF.exists():
            pytest.skip(f"Test fixture not found: {SAMPLE_PDF}")

    def test_returns_two_dataframes(self):
        """Test that extraction returns tuple of two DataFrames."""
        df_raw, df_contributions = extract_data_from_pdf(str(SAMPLE_PDF))

        assert isinstance(df_raw, pd.DataFrame)
        assert isinstance(df_contributions, pd.DataFrame)

    def test_raw_dataframe_columns(self):
        """Test that raw DataFrame has expected columns."""
        df_raw, _ = extract_data_from_pdf(str(SAMPLE_PDF))

        assert 'mes_ano' in df_raw.columns
        assert 'valor_cota' in df_raw.columns
        assert 'cotas' in df_raw.columns

    def test_contributions_dataframe_columns(self):
        """Test that contributions DataFrame has expected columns."""
        _, df_contributions = extract_data_from_pdf(str(SAMPLE_PDF))

        assert 'data' in df_contributions.columns
        assert 'contribuicao_total' in df_contributions.columns
        assert 'contrib_participante' in df_contributions.columns
        assert 'contrib_patrocinador' in df_contributions.columns
        assert 'contribuicao_acumulada' in df_contributions.columns

    def test_extracts_multiple_months(self):
        """Test that extraction finds data from multiple months."""
        df_raw, df_contributions = extract_data_from_pdf(str(SAMPLE_PDF))

        # The 2024 PDF should have 12 months of data
        unique_months = df_raw['mes_ano'].nunique()
        assert unique_months >= 12, f"Expected at least 12 months, got {unique_months}"

    def test_cota_values_reasonable(self):
        """Test that cota values are in reasonable range."""
        df_raw, _ = extract_data_from_pdf(str(SAMPLE_PDF))

        # Cota values for 2024 should be between 1.0 and 2.0
        assert df_raw['valor_cota'].min() > 1.0
        assert df_raw['valor_cota'].max() < 2.0

    def test_contributions_accumulate_correctly(self):
        """Test that cumulative contributions are calculated correctly."""
        _, df_contributions = extract_data_from_pdf(str(SAMPLE_PDF))

        # Manual cumsum should match the column
        expected_cumsum = df_contributions['contribuicao_total'].cumsum()
        pd.testing.assert_series_equal(
            df_contributions['contribuicao_acumulada'].reset_index(drop=True),
            expected_cumsum.reset_index(drop=True),
            check_names=False
        )

    def test_participant_patrocinador_sum_to_total(self):
        """Test that participant + patrocinador = total for each row."""
        _, df_contributions = extract_data_from_pdf(str(SAMPLE_PDF))

        calculated_total = (
            df_contributions['contrib_participante'] +
            df_contributions['contrib_patrocinador']
        )

        pd.testing.assert_series_equal(
            df_contributions['contribuicao_total'].reset_index(drop=True),
            calculated_total.reset_index(drop=True),
            check_names=False
        )

    def test_dates_are_chronological(self):
        """Test that contribution dates are in chronological order."""
        _, df_contributions = extract_data_from_pdf(str(SAMPLE_PDF))

        dates = df_contributions['data'].tolist()
        assert dates == sorted(dates), "Dates should be in chronological order"

    def test_no_negative_contributions(self):
        """Test that contributions (not fees) are positive."""
        _, df_contributions = extract_data_from_pdf(str(SAMPLE_PDF))

        # Total contributions should be positive
        assert (df_contributions['contribuicao_total'] > 0).all()

    def test_2024_specific_values(self):
        """Test specific known values from the 2024 PDF.

        Based on the PDF content:
        - January 2024 participant contribution: 3,969.09
        - Final cota value (Dec 2024): 1.3493461878
        - Final balance: 74,963.13
        """
        df_raw, df_contributions = extract_data_from_pdf(str(SAMPLE_PDF))

        # Check January 2024 participant contribution exists
        jan_2024 = df_contributions[
            df_contributions['data'].dt.month == 1
        ]['contrib_participante'].iloc[0]

        # Should be close to 3969.09 (allowing for small float differences)
        assert abs(jan_2024 - 3969.09) < 1.0, \
            f"January participant contribution should be ~3969.09, got {jan_2024}"

        # Check final cota value (December 2024)
        dec_2024_cotas = df_raw[
            df_raw['mes_ano'].dt.month == 12
        ]['valor_cota']

        assert any(abs(v - 1.3493461878) < 0.0001 for v in dec_2024_cotas), \
            "December 2024 should have cota value ~1.3493461878"


class TestExtractorIntegration:
    """Integration tests for the full extraction pipeline."""

    @pytest.fixture(autouse=True)
    def check_fixture_exists(self):
        """Ensure the test PDF exists."""
        if not SAMPLE_PDF.exists():
            pytest.skip(f"Test fixture not found: {SAMPLE_PDF}")

    def test_full_pipeline_with_calculator(self):
        """Test that extracted data works with calculator functions."""
        from calculator import process_position_data, process_contributions_data

        df_raw, df_contributions = extract_data_from_pdf(str(SAMPLE_PDF))

        # Process position data
        df_position = process_position_data(df_raw)

        assert not df_position.empty
        assert 'data' in df_position.columns
        assert 'posicao' in df_position.columns
        assert 'cotas' in df_position.columns

        # Process contributions
        df_monthly = process_contributions_data(df_contributions)

        assert not df_monthly.empty
        assert 'contribuicao_acumulada' in df_monthly.columns

    def test_xirr_calculation_with_real_data(self):
        """Test XIRR calculation with real extracted data."""
        from calculator import process_position_data, xirr_bizdays

        df_raw, df_contributions = extract_data_from_pdf(str(SAMPLE_PDF))
        df_position = process_position_data(df_raw)

        # Calculate XIRR
        last_position = df_position['posicao'].iloc[-1]
        last_date = df_position['data'].iloc[-1]

        dates = df_contributions['data'].tolist() + [last_date]
        amounts = [-amt for amt in df_contributions['contribuicao_total'].tolist()] + [last_position]

        cagr = xirr_bizdays(dates, amounts)

        # XIRR should return a reasonable value
        assert cagr is not None
        assert -0.5 < cagr < 1.0, f"XIRR {cagr} seems unreasonable"

        # For 2024, the fund should have positive returns
        assert cagr > 0, "2024 should have positive returns"
