"""
Tests for extractor.py - PDF extraction functionality.

Uses the redacted sample PDFs which contain no personal information.
"""

import pytest
import pandas as pd
from pathlib import Path

from extractor import extract_data_from_pdf


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / 'fixtures'
SAMPLE_PDF = FIXTURES_DIR / 'sample_extrato_2024.pdf'
PDF_2023_TO_2025 = FIXTURES_DIR / 'sample_extrato_2023_to_2025.pdf'
PDF_PARTIAL_2024 = FIXTURES_DIR / 'sample_extrato_partial_2024.pdf'


# Expected SALDO values from each PDF (manually verified)
EXPECTED_SALDO = {
    'full_2023_2025': {
        'saldo_total': 126448.19,
        'total_cotas': 83545.3819766684,
        'cota_value': 1.5135270490,
        'cota_date': '01/11/2025',
        'rentabilidade_months': 36,  # 12/2022 to 11/2025
    },
    '2024': {
        'saldo_total': 74963.13,
        'total_cotas': 55555.1486062447,
        'cota_value': 1.3493461878,
        'cota_date': '01/12/2024',
        'rentabilidade_months': 12,  # 01/2024 to 12/2024
    },
    'partial_2024': {
        'saldo_total': 74963.13,  # Same as 2024 full
        'total_cotas': 55555.1486062447,  # Same as 2024
        'cota_value': 1.3493461878,
        'cota_date': '01/12/2024',
        'rentabilidade_months': 6,  # 07/2024 to 12/2024
    },
}


class TestExtractDataFromPdf:
    """Tests for the extract_data_from_pdf function using real PDF data."""

    @pytest.fixture(autouse=True)
    def check_fixture_exists(self):
        """Ensure the test PDF exists - FAIL if missing (not skip)."""
        assert SAMPLE_PDF.exists(), f"REQUIRED fixture missing: {SAMPLE_PDF}"

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
        """Test that cota values match known 2024 PDF values.

        Known values from 2024 PDF:
        - January 2024: 1.23418293
        - December 2024: 1.3493461878
        """
        df_raw, _ = extract_data_from_pdf(str(SAMPLE_PDF))

        # Exact known values with tight tolerance
        assert abs(df_raw['valor_cota'].min() - 1.23418293) < 0.0001, \
            f"Min cota {df_raw['valor_cota'].min()} != expected 1.23418293"
        assert abs(df_raw['valor_cota'].max() - 1.3493461878) < 0.0001, \
            f"Max cota {df_raw['valor_cota'].max()} != expected 1.3493461878"

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

        # Exact value with 1 cent tolerance
        assert abs(jan_2024 - 3969.09) < 0.01, \
            f"January participant contribution should be 3969.09, got {jan_2024}"

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
        """Ensure the test PDF exists - FAIL if missing (not skip)."""
        assert SAMPLE_PDF.exists(), f"REQUIRED fixture missing: {SAMPLE_PDF}"

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


class TestExtractSaldoTotal:
    """Tests for SALDO TOTAL extraction from PDF.

    Tests are written BEFORE implementation (TDD approach).
    The _extract_saldo_total function should extract from the SALDO DE CONTAS section:
    - saldo_total: R$ value
    - total_cotas: number of cotas
    - cota_value: cota value from observation
    - cota_date: date from observation
    """

    def test_extract_saldo_full_pdf(self):
        """Test SALDO extraction from full 2023-2025 PDF."""
        from extractor import _extract_saldo_total

        assert PDF_2023_TO_2025.exists(), f"REQUIRED fixture missing: {PDF_2023_TO_2025}"

        result = _extract_saldo_total(str(PDF_2023_TO_2025))
        expected = EXPECTED_SALDO['full_2023_2025']

        assert result is not None, "Should extract SALDO data"
        assert abs(result['saldo_total'] - expected['saldo_total']) < 0.01, \
            f"saldo_total: expected {expected['saldo_total']}, got {result['saldo_total']}"
        assert abs(result['total_cotas'] - expected['total_cotas']) < 0.01, \
            f"total_cotas: expected {expected['total_cotas']}, got {result['total_cotas']}"
        assert abs(result['cota_value'] - expected['cota_value']) < 0.0000001, \
            f"cota_value: expected {expected['cota_value']}, got {result['cota_value']}"
        assert result['cota_date'] == expected['cota_date'], \
            f"cota_date: expected {expected['cota_date']}, got {result['cota_date']}"

    def test_extract_saldo_2024_pdf(self):
        """Test SALDO extraction from 2024 PDF."""
        from extractor import _extract_saldo_total

        assert SAMPLE_PDF.exists(), f"REQUIRED fixture missing: {SAMPLE_PDF}"

        result = _extract_saldo_total(str(SAMPLE_PDF))
        expected = EXPECTED_SALDO['2024']

        assert result is not None, "Should extract SALDO data"
        assert abs(result['saldo_total'] - expected['saldo_total']) < 0.01
        assert abs(result['total_cotas'] - expected['total_cotas']) < 0.01
        assert abs(result['cota_value'] - expected['cota_value']) < 0.0000001
        assert result['cota_date'] == expected['cota_date']

    def test_extract_saldo_partial_pdf(self):
        """Test SALDO extraction from partial 2024 PDF (Jul-Dec).

        Partial PDF should have the SAME SALDO as full 2024 PDF.
        """
        from extractor import _extract_saldo_total

        assert PDF_PARTIAL_2024.exists(), f"REQUIRED fixture missing: {PDF_PARTIAL_2024}"

        result = _extract_saldo_total(str(PDF_PARTIAL_2024))
        expected = EXPECTED_SALDO['partial_2024']

        assert result is not None, "Should extract SALDO data"
        assert abs(result['saldo_total'] - expected['saldo_total']) < 0.01
        assert abs(result['total_cotas'] - expected['total_cotas']) < 0.01
        assert abs(result['cota_value'] - expected['cota_value']) < 0.0000001
        assert result['cota_date'] == expected['cota_date']

    def test_partial_and_full_2024_have_same_saldo(self):
        """Verify that partial and full 2024 PDFs have identical SALDO TOTAL."""
        from extractor import _extract_saldo_total

        assert SAMPLE_PDF.exists(), f"REQUIRED fixture missing: {SAMPLE_PDF}"
        assert PDF_PARTIAL_2024.exists(), f"REQUIRED fixture missing: {PDF_PARTIAL_2024}"

        result_full = _extract_saldo_total(str(SAMPLE_PDF))
        result_partial = _extract_saldo_total(str(PDF_PARTIAL_2024))

        assert abs(result_full['saldo_total'] - result_partial['saldo_total']) < 0.01, \
            "Full and partial 2024 PDFs should have same SALDO TOTAL"
        assert abs(result_full['total_cotas'] - result_partial['total_cotas']) < 0.01, \
            "Full and partial 2024 PDFs should have same total cotas"


class TestExtractRentabilidadeCota:
    """Tests for RENTABILIDADE DA COTA extraction from PDF.

    The _extract_rentabilidade_cota function should extract the monthly cota values
    from the RENTABILIDADE DA COTA section.
    """

    def test_extract_rentabilidade_full_pdf(self):
        """Test RENTABILIDADE extraction from full 2023-2025 PDF."""
        from extractor import _extract_rentabilidade_cota

        assert PDF_2023_TO_2025.exists(), f"REQUIRED fixture missing: {PDF_2023_TO_2025}"

        result = _extract_rentabilidade_cota(str(PDF_2023_TO_2025))
        expected_months = EXPECTED_SALDO['full_2023_2025']['rentabilidade_months']

        assert result is not None, "Should extract RENTABILIDADE data"
        assert len(result) == expected_months, \
            f"Expected {expected_months} months, got {len(result)}"

        # Check first month (12/2022)
        assert '12/2022' in result, "Should have 12/2022"
        # Check last month (11/2025)
        assert '11/2025' in result, "Should have 11/2025"

        # Verify cota values match known range for full PDF
        # Known: Dec 2022 = 1.09541556, Nov 2025 = 1.513527049
        min_cota = min(result.values())
        max_cota = max(result.values())
        assert abs(min_cota - 1.09541556) < 0.0001, \
            f"Min cota {min_cota} != expected 1.09541556"
        assert abs(max_cota - 1.513527049) < 0.0001, \
            f"Max cota {max_cota} != expected 1.513527049"

    def test_extract_rentabilidade_2024_pdf(self):
        """Test RENTABILIDADE extraction from 2024 PDF."""
        from extractor import _extract_rentabilidade_cota

        assert SAMPLE_PDF.exists(), f"REQUIRED fixture missing: {SAMPLE_PDF}"

        result = _extract_rentabilidade_cota(str(SAMPLE_PDF))
        expected_months = EXPECTED_SALDO['2024']['rentabilidade_months']

        assert result is not None, "Should extract RENTABILIDADE data"
        assert len(result) == expected_months, \
            f"Expected {expected_months} months, got {len(result)}"

        # Check first month (01/2024)
        assert '01/2024' in result, "Should have 01/2024"
        # Check last month (12/2024)
        assert '12/2024' in result, "Should have 12/2024"

        # Final cota should match expected value
        assert abs(result['12/2024'] - EXPECTED_SALDO['2024']['cota_value']) < 0.0000001

    def test_extract_rentabilidade_partial_pdf(self):
        """Test RENTABILIDADE extraction from partial PDF.

        Partial PDF should have FEWER months than full PDF.
        """
        from extractor import _extract_rentabilidade_cota

        assert PDF_PARTIAL_2024.exists(), f"REQUIRED fixture missing: {PDF_PARTIAL_2024}"

        result = _extract_rentabilidade_cota(str(PDF_PARTIAL_2024))
        expected_months = EXPECTED_SALDO['partial_2024']['rentabilidade_months']

        assert result is not None, "Should extract RENTABILIDADE data"
        assert len(result) == expected_months, \
            f"Expected {expected_months} months (Jul-Dec), got {len(result)}"

        # Check first month (07/2024)
        assert '07/2024' in result, "Partial PDF should start at 07/2024"
        # Check last month (12/2024)
        assert '12/2024' in result, "Should have 12/2024"

        # Should NOT have earlier months
        assert '01/2024' not in result, "Partial PDF should not have 01/2024"
        assert '06/2024' not in result, "Partial PDF should not have 06/2024"

    def test_partial_has_fewer_months_than_full(self):
        """Verify that partial PDF has fewer RENTABILIDADE months than full."""
        from extractor import _extract_rentabilidade_cota

        assert SAMPLE_PDF.exists(), f"REQUIRED fixture missing: {SAMPLE_PDF}"
        assert PDF_PARTIAL_2024.exists(), f"REQUIRED fixture missing: {PDF_PARTIAL_2024}"

        result_full = _extract_rentabilidade_cota(str(SAMPLE_PDF))
        result_partial = _extract_rentabilidade_cota(str(PDF_PARTIAL_2024))

        assert len(result_partial) < len(result_full), \
            f"Partial ({len(result_partial)}) should have fewer months than full ({len(result_full)})"


class TestPartialHistoryDetection:
    """Tests for detecting partial history PDFs using cotas comparison.

    A PDF is partial if: total_cotas (from SALDO) > sum(cotas from transactions)

    Test design - each PDF must:
    - Pass its category's tests (full → complete, partial → partial)
    - Fail the opposite category's tests

    Fixtures:
    - sample_extrato_2023_to_2025.pdf: FULL (complete history, missing_cotas ≈ 0)
    - sample_extrato_2024.pdf: PARTIAL (single year, missing ~19k cotas)
    - sample_extrato_partial_2024.pdf: PARTIAL (half year, missing ~42k cotas)
    """

    PARTIAL_THRESHOLD = 0.1  # Missing cotas above this = partial history

    @pytest.fixture
    def full_pdf_analysis(self):
        """Analyze the FULL history PDF."""
        from extractor import _extract_saldo_total
        assert PDF_2023_TO_2025.exists(), f"REQUIRED fixture missing: {PDF_2023_TO_2025}"
        df_raw, _ = extract_data_from_pdf(str(PDF_2023_TO_2025))
        saldo = _extract_saldo_total(str(PDF_2023_TO_2025))
        return {
            'sum_cotas': df_raw['cotas'].sum(),
            'total_cotas': saldo['total_cotas'],
            'missing_cotas': saldo['total_cotas'] - df_raw['cotas'].sum(),
            'saldo_total': saldo['saldo_total'],
            'first_cota_value': df_raw['valor_cota'].iloc[0],
        }

    @pytest.fixture
    def partial_year_pdf_analysis(self):
        """Analyze the PARTIAL single-year PDF."""
        from extractor import _extract_saldo_total
        assert SAMPLE_PDF.exists(), f"REQUIRED fixture missing: {SAMPLE_PDF}"
        df_raw, _ = extract_data_from_pdf(str(SAMPLE_PDF))
        saldo = _extract_saldo_total(str(SAMPLE_PDF))
        return {
            'sum_cotas': df_raw['cotas'].sum(),
            'total_cotas': saldo['total_cotas'],
            'missing_cotas': saldo['total_cotas'] - df_raw['cotas'].sum(),
            'saldo_total': saldo['saldo_total'],
            'first_cota_value': df_raw['valor_cota'].iloc[0],
        }

    @pytest.fixture
    def partial_half_year_pdf_analysis(self):
        """Analyze the PARTIAL half-year PDF."""
        from extractor import _extract_saldo_total
        assert PDF_PARTIAL_2024.exists(), f"REQUIRED fixture missing: {PDF_PARTIAL_2024}"
        df_raw, _ = extract_data_from_pdf(str(PDF_PARTIAL_2024))
        saldo = _extract_saldo_total(str(PDF_PARTIAL_2024))
        return {
            'sum_cotas': df_raw['cotas'].sum(),
            'total_cotas': saldo['total_cotas'],
            'missing_cotas': saldo['total_cotas'] - df_raw['cotas'].sum(),
            'saldo_total': saldo['saldo_total'],
            'first_cota_value': df_raw['valor_cota'].iloc[0],
        }

    # ===== FULL PDF: should pass complete test, fail partial test =====

    def test_full_pdf_passes_complete_test(self, full_pdf_analysis):
        """Full PDF should be detected as COMPLETE (missing_cotas ≈ 0)."""
        assert abs(full_pdf_analysis['missing_cotas']) < self.PARTIAL_THRESHOLD

    def test_full_pdf_fails_partial_test(self, full_pdf_analysis):
        """Full PDF should NOT be detected as partial."""
        is_partial = full_pdf_analysis['missing_cotas'] > self.PARTIAL_THRESHOLD
        assert not is_partial

    # ===== PARTIAL YEAR PDF: should fail complete test, pass partial test =====

    def test_partial_year_fails_complete_test(self, partial_year_pdf_analysis):
        """Single-year partial PDF should NOT be detected as complete."""
        is_complete = abs(partial_year_pdf_analysis['missing_cotas']) < self.PARTIAL_THRESHOLD
        assert not is_complete

    def test_partial_year_passes_partial_test(self, partial_year_pdf_analysis):
        """Single-year partial PDF should be detected as PARTIAL."""
        assert partial_year_pdf_analysis['missing_cotas'] > self.PARTIAL_THRESHOLD

    # ===== PARTIAL HALF-YEAR PDF: should fail complete test, pass partial test =====

    def test_partial_half_year_fails_complete_test(self, partial_half_year_pdf_analysis):
        """Half-year partial PDF should NOT be detected as complete."""
        is_complete = abs(partial_half_year_pdf_analysis['missing_cotas']) < self.PARTIAL_THRESHOLD
        assert not is_complete

    def test_partial_half_year_passes_partial_test(self, partial_half_year_pdf_analysis):
        """Half-year partial PDF should be detected as PARTIAL."""
        assert partial_half_year_pdf_analysis['missing_cotas'] > self.PARTIAL_THRESHOLD

    # ===== STARTING POSITION CALCULATION =====

    def test_starting_position_from_partial_pdf(self, partial_half_year_pdf_analysis):
        """Verify starting_position = missing_cotas × first_cota."""
        a = partial_half_year_pdf_analysis
        starting_position = a['missing_cotas'] * a['first_cota_value']

        assert starting_position > 0, "Starting position should be positive"
        assert starting_position < a['saldo_total'], \
            "Starting position should be less than final SALDO"


class TestDetectPartialHistory:
    """Tests for detect_partial_history() function.

    This function should be the single entry point for detecting partial PDFs
    and calculating starting_position. It returns a metadata dict with all
    necessary info for UI display.
    """

    PARTIAL_THRESHOLD = 0.1

    def test_full_pdf_returns_not_partial(self):
        """Full PDF should return is_partial=False."""
        from extractor import detect_partial_history

        assert PDF_2023_TO_2025.exists(), f"REQUIRED fixture: {PDF_2023_TO_2025}"
        df_raw, _ = extract_data_from_pdf(str(PDF_2023_TO_2025))
        result = detect_partial_history(str(PDF_2023_TO_2025), df_raw)

        assert result is not None
        assert result['is_partial'] is False

    def test_partial_pdf_returns_is_partial(self):
        """Partial PDF should return is_partial=True."""
        from extractor import detect_partial_history

        assert SAMPLE_PDF.exists(), f"REQUIRED fixture: {SAMPLE_PDF}"
        df_raw, _ = extract_data_from_pdf(str(SAMPLE_PDF))
        result = detect_partial_history(str(SAMPLE_PDF), df_raw)

        assert result is not None
        assert result['is_partial'] is True

    def test_returns_required_keys(self):
        """Result dict should contain all required keys."""
        from extractor import detect_partial_history

        assert SAMPLE_PDF.exists(), f"REQUIRED fixture: {SAMPLE_PDF}"
        df_raw, _ = extract_data_from_pdf(str(SAMPLE_PDF))
        result = detect_partial_history(str(SAMPLE_PDF), df_raw)

        required_keys = ['is_partial', 'missing_cotas', 'starting_position', 'first_month']
        for key in required_keys:
            assert key in result, f"Missing required key: {key}"

    def test_full_pdf_starting_position_near_zero(self):
        """Full PDF should have starting_position ≈ 0."""
        from extractor import detect_partial_history

        assert PDF_2023_TO_2025.exists(), f"REQUIRED fixture: {PDF_2023_TO_2025}"
        df_raw, _ = extract_data_from_pdf(str(PDF_2023_TO_2025))
        result = detect_partial_history(str(PDF_2023_TO_2025), df_raw)

        assert abs(result['starting_position']) < 1.0, \
            f"Full PDF starting_position should be ~0, got {result['starting_position']}"

    def test_partial_pdf_starting_position_positive(self):
        """Partial PDF should have positive starting_position."""
        from extractor import detect_partial_history

        assert PDF_PARTIAL_2024.exists(), f"REQUIRED fixture: {PDF_PARTIAL_2024}"
        df_raw, _ = extract_data_from_pdf(str(PDF_PARTIAL_2024))
        result = detect_partial_history(str(PDF_PARTIAL_2024), df_raw)

        assert result['starting_position'] > 0, \
            "Partial PDF should have positive starting_position"
        # Half-year partial should have significant starting position
        assert result['starting_position'] > 10000, \
            f"Half-year partial should have large starting_position, got {result['starting_position']}"

    def test_first_month_format(self):
        """first_month should be in MM/YYYY format."""
        from extractor import detect_partial_history

        assert SAMPLE_PDF.exists(), f"REQUIRED fixture: {SAMPLE_PDF}"
        df_raw, _ = extract_data_from_pdf(str(SAMPLE_PDF))
        result = detect_partial_history(str(SAMPLE_PDF), df_raw)

        # Should match MM/YYYY pattern
        import re
        assert re.match(r'\d{2}/\d{4}', result['first_month']), \
            f"first_month should be MM/YYYY, got {result['first_month']}"

    def test_returns_none_if_saldo_extraction_fails(self):
        """If SALDO extraction fails, should return None (not crash)."""
        from extractor import detect_partial_history
        import pandas as pd

        # Create empty df to simulate extraction failure scenario
        df_empty = pd.DataFrame({'cotas': [], 'valor_cota': []})

        # Use a non-existent path to trigger extraction failure
        result = detect_partial_history('nonexistent.pdf', df_empty)
        assert result is None

    def test_missing_cotas_matches_manual_calculation(self):
        """missing_cotas should equal total_cotas - sum(df_raw['cotas'])."""
        from extractor import detect_partial_history, _extract_saldo_total

        assert SAMPLE_PDF.exists(), f"REQUIRED fixture: {SAMPLE_PDF}"
        df_raw, _ = extract_data_from_pdf(str(SAMPLE_PDF))
        result = detect_partial_history(str(SAMPLE_PDF), df_raw)

        saldo = _extract_saldo_total(str(SAMPLE_PDF))
        expected_missing = saldo['total_cotas'] - df_raw['cotas'].sum()

        assert abs(result['missing_cotas'] - expected_missing) < 0.01, \
            f"missing_cotas mismatch: {result['missing_cotas']} vs {expected_missing}"
