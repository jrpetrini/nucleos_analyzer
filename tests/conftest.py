"""
Shared fixtures for Nucleos Analyzer tests.
"""

import sys
from pathlib import Path

# Add project root to path so tests can import modules
# This makes the tests portable (works regardless of where the repo is cloned)
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
from datetime import datetime


@pytest.fixture
def sample_contributions():
    """Sample contribution data for testing."""
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
def sample_position_data():
    """Sample position data for testing."""
    return pd.DataFrame({
        'data': pd.to_datetime([
            '2020-01-31', '2020-02-29', '2020-03-31',
            '2020-04-30', '2020-05-31', '2020-06-30'
        ]),
        'posicao': [1010.0, 2030.0, 3060.0, 4100.0, 5150.0, 6210.0],
        'cotas': [100.0, 200.0, 300.0, 400.0, 500.0, 600.0],
        'valor_cota': [10.1, 10.15, 10.2, 10.25, 10.3, 10.35],
    })


@pytest.fixture
def sample_inflation_index():
    """Sample inflation index (IPCA-like) for testing."""
    # Simulates ~0.5% monthly inflation
    return pd.DataFrame({
        'date': pd.to_datetime([
            '2020-01-01', '2020-02-01', '2020-03-01',
            '2020-04-01', '2020-05-01', '2020-06-01', '2020-07-01'
        ]),
        'value': [1.0, 1.005, 1.010025, 1.015075, 1.020150, 1.025251, 1.030378]
    })


@pytest.fixture
def sample_benchmark_data():
    """Sample benchmark data (CDI-like) for testing - starts at 1.0."""
    # Simulates ~0.4% monthly return
    return pd.DataFrame({
        'date': pd.to_datetime([
            '2020-01-01', '2020-02-01', '2020-03-01',
            '2020-04-01', '2020-05-01', '2020-06-01', '2020-07-01'
        ]),
        'value': [1.0, 1.004, 1.008016, 1.012048, 1.016096, 1.020161, 1.024241]
    })


@pytest.fixture
def sample_raw_transactions():
    """Sample raw transaction data for testing process_position_data."""
    return pd.DataFrame({
        'data': pd.to_datetime([
            '2020-01-15', '2020-01-20',
            '2020-02-15', '2020-02-20',
            '2020-03-15'
        ]),
        'mes_ano': pd.to_datetime([
            '2020-01-01', '2020-01-01',
            '2020-02-01', '2020-02-01',
            '2020-03-01'
        ]),
        'cotas': [50.0, 50.0, 50.0, 50.0, 100.0],
        'valor_cota': [10.0, 10.1, 10.15, 10.2, 10.25],
    })
