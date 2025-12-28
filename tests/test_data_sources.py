"""
Tests for macroeconomic data sources cross-validation.

These tests verify:
1. BCB and IPEA return identical data for same indicators (using cached data)
2. Data integrity across sources (using cached data)
3. API availability (smoke tests - live calls)

Most tests use cached JSON responses from tests/fixtures/api_responses/
to avoid network dependencies and flaky tests.

Run all tests:
    pytest tests/test_data_sources.py -v

Run only smoke tests (live API calls):
    pytest tests/test_data_sources.py -v -m slow
"""

import json
import pytest
import pandas as pd
import requests
from pathlib import Path

# Path to cached API responses
FIXTURES_DIR = Path(__file__).parent / 'fixtures' / 'api_responses'


# ============================================================================
# Cached Data Loaders
# ============================================================================

def load_bcb_cached(series_name: str) -> pd.DataFrame:
    """Load cached BCB data from JSON fixture."""
    path = FIXTURES_DIR / f'bcb_{series_name}_2024.json'
    with open(path) as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
    df['value'] = df['valor'].astype(float)
    return df[['date', 'value']]


def load_ipea_cached(series_name: str) -> pd.DataFrame:
    """Load cached IPEA data from JSON fixture."""
    path = FIXTURES_DIR / f'ipea_{series_name}_2024.json'
    with open(path) as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['VALDATA']).dt.tz_localize(None)
    df['value'] = df['VALVALOR'].astype(float)
    return df[['date', 'value']]


# ============================================================================
# API Endpoints (for live smoke tests only)
# ============================================================================

BCB_API_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
IPEA_API_BASE = "http://www.ipeadata.gov.br/api/odata4/Metadados('{code}')/Valores"


def fetch_bcb_direct(series_code: int, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch data directly from BCB API (no library)."""
    url = f"{BCB_API_BASE.format(code=series_code)}?formato=json"
    url += f"&dataInicial={start_date}&dataFinal={end_date}"

    resp = requests.get(url, timeout=15)
    resp.raise_for_status()

    df = pd.DataFrame(resp.json())
    df['date'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
    df['value'] = df['valor'].astype(float)
    return df[['date', 'value']]


def fetch_ipea_direct(series_code: str) -> pd.DataFrame:
    """Fetch data directly from IPEA API."""
    url = IPEA_API_BASE.format(code=series_code)

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    data = resp.json()['value']
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['VALDATA'], utc=True).dt.tz_localize(None)
    df['value'] = df['VALVALOR'].astype(float)
    return df[['date', 'value']]


# ============================================================================
# Test: BCB vs IPEA Cross-Validation (Cached Data)
# ============================================================================

class TestBCBvsIPEACrossValidation:
    """Verify BCB and IPEA return identical data for same indicators.

    Uses cached 2024 data from fixtures to avoid network calls.
    """

    def test_ipca_bcb_matches_ipea(self):
        """IPCA: BCB data should exactly match IPEA data."""
        bcb_df = load_bcb_cached('ipca')
        bcb_df['month'] = bcb_df['date'].dt.to_period('M')
        bcb_df = bcb_df.rename(columns={'value': 'bcb'})

        ipea_df = load_ipea_cached('ipca')
        ipea_df['month'] = ipea_df['date'].dt.to_period('M')
        ipea_df = ipea_df.rename(columns={'value': 'ipea'})

        merged = bcb_df[['month', 'bcb']].merge(
            ipea_df[['month', 'ipea']], on='month'
        )

        assert len(merged) == 12, f"Expected 12 months, got {len(merged)}"

        merged['diff'] = (merged['bcb'] - merged['ipea']).abs()
        max_diff = merged['diff'].max()

        assert max_diff < 0.001, \
            f"IPCA mismatch between BCB and IPEA. Max diff: {max_diff}"

    def test_inpc_bcb_matches_ipea(self):
        """INPC: BCB data should exactly match IPEA data."""
        bcb_df = load_bcb_cached('inpc')
        bcb_df['month'] = bcb_df['date'].dt.to_period('M')
        bcb_df = bcb_df.rename(columns={'value': 'bcb'})

        ipea_df = load_ipea_cached('inpc')
        ipea_df['month'] = ipea_df['date'].dt.to_period('M')
        ipea_df = ipea_df.rename(columns={'value': 'ipea'})

        merged = bcb_df[['month', 'bcb']].merge(
            ipea_df[['month', 'ipea']], on='month'
        )

        assert len(merged) == 12, f"Expected 12 months, got {len(merged)}"

        merged['diff'] = (merged['bcb'] - merged['ipea']).abs()
        max_diff = merged['diff'].max()

        assert max_diff < 0.001, \
            f"INPC mismatch between BCB and IPEA. Max diff: {max_diff}"

    def test_cdi_monthly_bcb_matches_ipea(self):
        """CDI Monthly: BCB data should exactly match IPEA data."""
        bcb_df = load_bcb_cached('cdi')
        bcb_df['month'] = bcb_df['date'].dt.to_period('M')
        bcb_df = bcb_df.rename(columns={'value': 'bcb'})

        ipea_df = load_ipea_cached('cdi')
        ipea_df['month'] = ipea_df['date'].dt.to_period('M')
        ipea_df = ipea_df.rename(columns={'value': 'ipea'})

        merged = bcb_df[['month', 'bcb']].merge(
            ipea_df[['month', 'ipea']], on='month'
        )

        assert len(merged) == 12, f"Expected 12 months, got {len(merged)}"

        merged['diff'] = (merged['bcb'] - merged['ipea']).abs()
        max_diff = merged['diff'].max()

        assert max_diff < 0.01, \
            f"CDI mismatch between BCB and IPEA. Max diff: {max_diff}"


# ============================================================================
# Test: Data Integrity (Cached Data)
# ============================================================================

class TestDataIntegrity:
    """Verify data quality and consistency using cached data."""

    def test_ipca_values_reasonable(self):
        """IPCA monthly variation should be in reasonable range."""
        df = load_bcb_cached('ipca')

        # Monthly IPCA should typically be between -1% and 3%
        assert df['value'].min() > -2.0, f"IPCA too negative: {df['value'].min()}"
        assert df['value'].max() < 5.0, f"IPCA too high: {df['value'].max()}"

    def test_inpc_values_reasonable(self):
        """INPC monthly variation should be in reasonable range."""
        df = load_bcb_cached('inpc')

        # Monthly INPC should typically be between -1% and 3%
        assert df['value'].min() > -2.0, f"INPC too negative: {df['value'].min()}"
        assert df['value'].max() < 5.0, f"INPC too high: {df['value'].max()}"

    def test_no_missing_months(self):
        """Monthly series should have no gaps."""
        df = load_bcb_cached('ipca')
        df['month'] = df['date'].dt.to_period('M')

        months = df['month'].unique()
        assert len(months) == 12, f"Expected 12 months, got {len(months)}"

        # Check continuity
        expected = pd.period_range('2024-01', '2024-12', freq='M')
        for m in expected:
            assert m in months, f"Missing month: {m}"


# ============================================================================
# Test: API Availability (Smoke Tests - Live Calls)
# ============================================================================

@pytest.mark.slow
class TestAPIAvailability:
    """Verify APIs are accessible. These make live network calls."""

    def test_bcb_api_responds(self):
        """BCB API should respond."""
        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2024&dataFinal=31/01/2024"
        resp = requests.get(url, timeout=10)
        assert resp.status_code == 200

    def test_ipea_api_responds(self):
        """IPEA API should respond."""
        url = "http://www.ipeadata.gov.br/api/odata4/Metadados('PRECOS12_IPCAG12')/Valores"
        resp = requests.get(url, timeout=30)
        assert resp.status_code == 200
