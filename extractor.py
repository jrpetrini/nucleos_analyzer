#!/usr/bin/env python3
"""
PDF extraction and file selection utilities for Nucleos Analyzer.
"""

import re
import subprocess

import pandas as pd
import pypdf

# Try to import tkinter for file dialog
try:
    import tkinter as tk
    from tkinter import filedialog
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


def select_pdf_file_tkinter() -> str | None:
    """Opens a tkinter file dialog to select the PDF file."""
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Selecione o arquivo extratoIndividual.pdf",
        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
    )
    root.destroy()
    return file_path if file_path else None


def select_pdf_file_zenity() -> str | None:
    """Opens a zenity file dialog to select the PDF file."""
    try:
        result = subprocess.run(
            ["zenity", "--file-selection",
             "--title=Selecione o arquivo extratoIndividual.pdf",
             "--file-filter=PDF files | *.pdf"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def select_pdf_file() -> str | None:
    """Opens a file dialog to select the PDF file."""
    if HAS_TKINTER:
        try:
            return select_pdf_file_tkinter()
        except Exception:
            pass
    file_path = select_pdf_file_zenity()
    if file_path:
        return file_path
    print("GUI não disponível. Digite o caminho do arquivo:")
    return input("> ").strip() or None


def _parse_pdf_rows(file_path: str) -> list[dict]:
    """
    Parse all transaction rows from Nucleos PDF into a unified list.

    Single-pass extraction that captures all fields needed for both
    position tracking and contribution analysis.

    Args:
        file_path: Path to the extratoIndividual.pdf file

    Returns:
        List of transaction dicts with keys:
        - mes_ano: Month/year period (for position grouping)
        - data_exata: Exact transaction date
        - valor_cota: Quota value at transaction time
        - cotas: Number of quotas (positive or negative)
        - is_contribution: True if this is a contribution (not fee/tax)
        - tipo: 'participante' or 'patrocinador' (only meaningful for contributions)
    """
    reader = pypdf.PdfReader(file_path)
    transactions = []
    pat_date_month = re.compile(r'\d{2}/\d{4}')
    pat_date_full = re.compile(r'(\d{2}/\d{2}/\d{4})$')  # DD/MM/YYYY at end of line

    for page in reader.pages:
        page_text_raw = page.extract_text()
        rows = page_text_raw.split('\n')
        rows = [row for row in rows if ('CONTRIB' in row) or ('TAXA' in row)]

        for row in rows:
            row_split = row.split(" ")

            # Extract month/year for grouping position data
            date_match = pat_date_month.findall(row)
            if not date_match:
                continue
            mes_ano = pd.to_datetime(date_match[0].strip(), format='%m/%Y')

            # Extract exact date (DD/MM/YYYY) from end of row
            full_date_match = pat_date_full.search(row)
            if full_date_match:
                data_exata = pd.to_datetime(full_date_match.group(1), format='%d/%m/%Y')
            else:
                # Fallback to month/year (first day of month)
                data_exata = mes_ano

            # Parse numeric values
            cotas = float(row_split[-1][:-8].replace('.', '').replace(',', '.'))
            valor_cota = float(row_split[-2].replace('.', '').replace(',', '.'))

            # Determine transaction type
            is_contribution = 'CONTRIB' in row and cotas > 0
            # Match both full ("PARTICIPANTE") and abbreviated ("PARTICIP") forms
            is_participant = 'PARTICIPANTE' in row or ('PARTICIP' in row and 'PATROC' not in row)

            transactions.append({
                'mes_ano': mes_ano,
                'data_exata': data_exata,
                'valor_cota': valor_cota,
                'cotas': cotas,
                'is_contribution': is_contribution,
                'tipo': 'participante' if is_participant else 'patrocinador',
            })

    return transactions


def _build_raw_dataframe(transactions: list[dict]) -> pd.DataFrame:
    """Build the raw transactions DataFrame for position calculation."""
    if not transactions:
        return pd.DataFrame(columns=['mes_ano', 'valor_cota', 'cotas'])

    return pd.DataFrame([
        {
            'mes_ano': t['mes_ano'],
            'valor_cota': t['valor_cota'],
            'cotas': t['cotas'],
        }
        for t in transactions
    ])


def _build_contributions_dataframe(transactions: list[dict]) -> pd.DataFrame:
    """Build the contributions DataFrame with participant/patrocinador split."""
    # Filter to only actual contributions
    contributions = [t for t in transactions if t['is_contribution']]

    if not contributions:
        return pd.DataFrame()

    # Calculate contribution value for each transaction
    contrib_records = [
        {
            'data_exata': t['data_exata'],
            'mes_ano': t['mes_ano'],
            'tipo': t['tipo'],
            'valor': t['cotas'] * t['valor_cota'],
        }
        for t in contributions
    ]

    df_contrib_raw = pd.DataFrame(contrib_records)

    # Group by exact date and type, then pivot to get participant/patrocinador columns
    df_by_type = df_contrib_raw.groupby(['data_exata', 'tipo']).agg({
        'mes_ano': 'first',
        'valor': 'sum'
    }).reset_index()

    # Pivot to get separate columns
    df_pivot = df_by_type.pivot_table(
        index=['data_exata', 'mes_ano'],
        columns='tipo',
        values='valor',
        fill_value=0
    ).reset_index()

    df_contributions = df_pivot.rename(columns={
        'data_exata': 'data',
        'participante': 'contrib_participante',
        'patrocinador': 'contrib_patrocinador'
    })

    # Ensure columns exist
    if 'contrib_participante' not in df_contributions.columns:
        df_contributions['contrib_participante'] = 0
    if 'contrib_patrocinador' not in df_contributions.columns:
        df_contributions['contrib_patrocinador'] = 0

    df_contributions['contribuicao_total'] = (
        df_contributions['contrib_participante'] +
        df_contributions['contrib_patrocinador']
    )
    df_contributions = df_contributions.sort_values('data').reset_index(drop=True)
    df_contributions['contribuicao_acumulada'] = df_contributions['contribuicao_total'].cumsum()
    df_contributions['contrib_participante_acum'] = df_contributions['contrib_participante'].cumsum()
    df_contributions['contrib_patrocinador_acum'] = df_contributions['contrib_patrocinador'].cumsum()

    return df_contributions


def extract_data_from_pdf(file_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extracts data from Nucleos PDF statement.

    Uses single-pass parsing: PDF is read once, then both output DataFrames
    are derived from the unified transaction list.

    Args:
        file_path: Path to the extratoIndividual.pdf file

    Returns:
        Tuple of (raw_df, contributions_df) where:
        - raw_df: All transactions with mes_ano, valor_cota, cotas
        - contributions_df: Contributions with exact dates and amounts
    """
    transactions = _parse_pdf_rows(file_path)
    df_raw = _build_raw_dataframe(transactions)
    df_contributions = _build_contributions_dataframe(transactions)
    return df_raw, df_contributions
