"""
Tests for macroeconomic data sources cross-validation.

These tests verify:
1. BCB library returns same data as direct BCB API
2. BCB API returns same data as IPEA API
3. Data integrity across sources

Note: These tests make live API calls and may be slow.
Run with: pytest tests/test_data_sources.py -v

To skip external API tests:
    pytest tests/ -m "not external_api"

To run only external API tests:
    pytest tests/ -m external_api

Test outcomes:
- PASS: API was reachable AND data matches
- FAIL: API was reachable AND data doesn't match (real failure!)
- SKIP: API was NOT reachable (couldn't verify)
"""

import pytest
import pandas as pd
import requests
from datetime import datetime

# Custom marker for external API tests
pytestmark = pytest.mark.external_api


def check_api_available(url: str, timeout: int = 5) -> bool:
    """Check if an API endpoint is reachable."""
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        return resp.status_code < 500
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        return False


@pytest.fixture(scope='module')
def require_bcb_api():
    """Skip tests if BCB API is not available."""
    test_url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2024&dataFinal=31/01/2024"
    if not check_api_available(test_url):
        pytest.skip("BCB API is not available")


@pytest.fixture(scope='module')
def require_ipea_api():
    """Skip tests if IPEA API is not available."""
    test_url = "http://www.ipeadata.gov.br/api/odata4/Metadados"
    if not check_api_available(test_url, timeout=10):
        pytest.skip("IPEA API is not available")


# ============================================================================
# API Endpoints
# ============================================================================

BCB_API_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
IPEA_API_BASE = "http://www.ipeadata.gov.br/api/odata4/Metadados('{code}')/Valores"

# Series mapping: BCB code -> IPEA code
SERIES_MAPPING = {
    'IPCA': {'bcb': 433, 'ipea': 'PRECOS12_IPCAG12', 'freq': 'monthly'},
    'INPC': {'bcb': 188, 'ipea': 'PRECOS12_INPCBR12', 'freq': 'monthly'},
    # CDI daily has too many records, using monthly accumulated instead
    'CDI_monthly': {'bcb': 4391, 'ipea': 'BM12_TJCDI12', 'freq': 'monthly'},
}


# ============================================================================
# Helper Functions
# ============================================================================

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


def normalize_to_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize dates to monthly periods for comparison."""
    df = df.copy()
    df['month'] = df['date'].dt.to_period('M')
    return df.groupby('month')['value'].last().reset_index()


# ============================================================================
# Test: BCB Library vs Direct BCB API
# ============================================================================

class TestBCBLibraryVsDirectAPI:
    """Verify the bcb library returns same data as direct API calls."""

    @pytest.fixture(scope='class')
    def test_period(self):
        """Use 2024 data for testing."""
        return {
            'start': '01/01/2024',
            'end': '31/12/2024',
            'start_iso': '2024-01-01',
            'end_iso': '2024-12-31',
        }

    def test_ipca_library_matches_direct(self, test_period, require_bcb_api):
        """IPCA: bcb library should match direct API."""
        from bcb import sgs

        # Via library
        lib_data = sgs.get({'ipca': 433},
                          start=test_period['start_iso'],
                          end=test_period['end_iso'])
        lib_df = lib_data.reset_index()
        lib_df.columns = ['date', 'lib_value']
        lib_df['month'] = lib_df['date'].dt.to_period('M')

        # Direct API
        api_df = fetch_bcb_direct(433, test_period['start'], test_period['end'])
        api_df['month'] = api_df['date'].dt.to_period('M')
        api_df = api_df.rename(columns={'value': 'api_value'})

        # Compare
        merged = lib_df[['month', 'lib_value']].merge(
            api_df[['month', 'api_value']], on='month'
        )

        assert len(merged) == 12, f"Expected 12 months, got {len(merged)}"
        diff = (merged['lib_value'] - merged['api_value']).abs().max()
        assert diff < 0.0001, f"Max difference {diff} exceeds tolerance"

    def test_inpc_library_matches_direct(self, test_period, require_bcb_api):
        """INPC: bcb library should match direct API."""
        from bcb import sgs

        # Via library
        lib_data = sgs.get({'inpc': 188},
                          start=test_period['start_iso'],
                          end=test_period['end_iso'])
        lib_df = lib_data.reset_index()
        lib_df.columns = ['date', 'lib_value']
        lib_df['month'] = lib_df['date'].dt.to_period('M')

        # Direct API
        api_df = fetch_bcb_direct(188, test_period['start'], test_period['end'])
        api_df['month'] = api_df['date'].dt.to_period('M')
        api_df = api_df.rename(columns={'value': 'api_value'})

        # Compare
        merged = lib_df[['month', 'lib_value']].merge(
            api_df[['month', 'api_value']], on='month'
        )

        assert len(merged) == 12, f"Expected 12 months, got {len(merged)}"
        diff = (merged['lib_value'] - merged['api_value']).abs().max()
        assert diff < 0.0001, f"Max difference {diff} exceeds tolerance"


# ============================================================================
# Test: BCB vs IPEA Cross-Validation
# ============================================================================

class TestBCBvsIPEACrossValidation:
    """Verify BCB and IPEA return identical data for same indicators."""

    @pytest.fixture(scope='class')
    def test_year(self):
        return 2024

    def test_ipca_bcb_matches_ipea(self, test_year, require_bcb_api, require_ipea_api):
        """IPCA: BCB data should exactly match IPEA data."""
        # BCB
        bcb_df = fetch_bcb_direct(433, f'01/01/{test_year}', f'31/12/{test_year}')
        bcb_df['month'] = bcb_df['date'].dt.to_period('M')
        bcb_df = bcb_df.rename(columns={'value': 'bcb'})

        # IPEA
        ipea_df = fetch_ipea_direct('PRECOS12_IPCAG12')
        ipea_df = ipea_df[ipea_df['date'].dt.year == test_year]
        ipea_df['month'] = ipea_df['date'].dt.to_period('M')
        ipea_df = ipea_df.rename(columns={'value': 'ipea'})

        # Compare
        merged = bcb_df[['month', 'bcb']].merge(
            ipea_df[['month', 'ipea']], on='month'
        )

        assert len(merged) >= 12, f"Expected 12+ months, got {len(merged)}"

        merged['diff'] = (merged['bcb'] - merged['ipea']).abs()
        max_diff = merged['diff'].max()

        assert max_diff < 0.001, \
            f"IPCA mismatch between BCB and IPEA. Max diff: {max_diff}\n{merged}"

    def test_inpc_bcb_matches_ipea(self, test_year, require_bcb_api, require_ipea_api):
        """INPC: BCB data should exactly match IPEA data."""
        # BCB
        bcb_df = fetch_bcb_direct(188, f'01/01/{test_year}', f'31/12/{test_year}')
        bcb_df['month'] = bcb_df['date'].dt.to_period('M')
        bcb_df = bcb_df.rename(columns={'value': 'bcb'})

        # IPEA
        ipea_df = fetch_ipea_direct('PRECOS12_INPCBR12')
        ipea_df = ipea_df[ipea_df['date'].dt.year == test_year]
        ipea_df['month'] = ipea_df['date'].dt.to_period('M')
        ipea_df = ipea_df.rename(columns={'value': 'ipea'})

        # Compare
        merged = bcb_df[['month', 'bcb']].merge(
            ipea_df[['month', 'ipea']], on='month'
        )

        assert len(merged) >= 12, f"Expected 12+ months, got {len(merged)}"

        merged['diff'] = (merged['bcb'] - merged['ipea']).abs()
        max_diff = merged['diff'].max()

        assert max_diff < 0.001, \
            f"INPC mismatch between BCB and IPEA. Max diff: {max_diff}\n{merged}"

    def test_cdi_monthly_bcb_matches_ipea(self, test_year, require_bcb_api, require_ipea_api):
        """CDI Monthly: BCB data should exactly match IPEA data."""
        # BCB CDI monthly accumulated (series 4391)
        bcb_df = fetch_bcb_direct(4391, f'01/01/{test_year}', f'31/12/{test_year}')
        bcb_df['month'] = bcb_df['date'].dt.to_period('M')
        bcb_df = bcb_df.rename(columns={'value': 'bcb'})

        # IPEA CDI monthly accumulated (BM12_TJCDI12)
        ipea_df = fetch_ipea_direct('BM12_TJCDI12')
        ipea_df = ipea_df[ipea_df['date'].dt.year == test_year]
        ipea_df['month'] = ipea_df['date'].dt.to_period('M')
        ipea_df = ipea_df.rename(columns={'value': 'ipea'})

        # Compare
        merged = bcb_df[['month', 'bcb']].merge(
            ipea_df[['month', 'ipea']], on='month'
        )

        assert len(merged) >= 12, f"Expected 12+ months, got {len(merged)}"

        merged['diff'] = (merged['bcb'] - merged['ipea']).abs()
        max_diff = merged['diff'].max()

        assert max_diff < 0.01, \
            f"CDI mismatch between BCB and IPEA. Max diff: {max_diff}\n{merged}"


# ============================================================================
# Test: Data Integrity
# ============================================================================

class TestDataIntegrity:
    """Verify data quality and consistency."""

    def test_ipca_values_reasonable(self, require_bcb_api):
        """IPCA monthly variation should be in reasonable range."""
        df = fetch_bcb_direct(433, '01/01/2024', '31/12/2024')

        # Monthly IPCA should typically be between -1% and 3%
        assert df['value'].min() > -2.0, "IPCA too negative"
        assert df['value'].max() < 5.0, "IPCA too high"

    def test_inpc_values_reasonable(self, require_bcb_api):
        """INPC monthly variation should be in reasonable range."""
        df = fetch_bcb_direct(188, '01/01/2024', '31/12/2024')

        # Monthly INPC should typically be between -1% and 3%
        assert df['value'].min() > -2.0, "INPC too negative"
        assert df['value'].max() < 5.0, "INPC too high"

    def test_no_missing_months(self, require_bcb_api):
        """Monthly series should have no gaps."""
        df = fetch_bcb_direct(433, '01/01/2024', '31/12/2024')
        df['month'] = df['date'].dt.to_period('M')

        months = df['month'].unique()
        assert len(months) == 12, f"Expected 12 months, got {len(months)}"

        # Check continuity
        expected = pd.period_range('2024-01', '2024-12', freq='M')
        for m in expected:
            assert m in months, f"Missing month: {m}"


# ============================================================================
# Test: API Availability (smoke tests)
# ============================================================================

class TestAPIAvailability:
    """Verify APIs are accessible."""

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


# ============================================================================
# Test: Fallback Mechanism
# ============================================================================

class TestFallbackMechanism:
    """Test that IPEA fallback works when BCB fails."""

    def test_ipea_fetch_returns_valid_data(self, require_ipea_api):
        """Direct IPEA fetch should return valid data."""
        from benchmarks import fetch_ipea_series

        data = fetch_ipea_series('PRECOS12_IPCAG12', '2024-01-01', '2024-06-30')

        assert len(data) >= 6  # At least 6 months
        assert data.min() > -5.0  # Reasonable IPCA range
        assert data.max() < 5.0

    def test_ipea_data_matches_bcb_format(self, require_bcb_api, require_ipea_api):
        """IPEA data should be in same format as BCB for seamless fallback."""
        from benchmarks import fetch_bcb_series, fetch_ipea_series, BCB_SERIES, IPEA_SERIES

        # Fetch IPCA from both sources
        bcb_data = fetch_bcb_series(BCB_SERIES['IPCA'], '2024-01-01', '2024-06-30')
        ipea_data = fetch_ipea_series(IPEA_SERIES['IPCA'], '2024-01-01', '2024-06-30')

        # Both should be pandas Series
        assert isinstance(bcb_data, pd.Series)
        assert isinstance(ipea_data, pd.Series)

        # Both should have datetime index
        assert pd.api.types.is_datetime64_any_dtype(bcb_data.index)
        assert pd.api.types.is_datetime64_any_dtype(ipea_data.index)

        # Values should match (within tolerance for any date normalization)
        bcb_monthly = bcb_data.groupby(bcb_data.index.to_period('M')).last()
        ipea_monthly = ipea_data.groupby(ipea_data.index.to_period('M')).last()

        merged = pd.DataFrame({'bcb': bcb_monthly, 'ipea': ipea_monthly}).dropna()
        diff = (merged['bcb'] - merged['ipea']).abs().max()
        assert diff < 0.001, f"Data mismatch: max diff = {diff}"

    def test_fetch_bcb_series_with_fallback_param(self, require_bcb_api):
        """fetch_bcb_series should work with series_name parameter."""
        from benchmarks import fetch_bcb_series, BCB_SERIES

        # This should work normally (BCB is available)
        data = fetch_bcb_series(
            BCB_SERIES['IPCA'],
            '2024-01-01',
            '2024-06-30',
            series_name='IPCA'
        )

        assert len(data) >= 6
        assert isinstance(data, pd.Series)
