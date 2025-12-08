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


def extract_data_from_pdf(file_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extracts data from Nucleos PDF statement.

    Args:
        file_path: Path to the extratoIndividual.pdf file

    Returns:
        Tuple of (raw_df, contributions_df) where:
        - raw_df: All transactions with mes_ano, valor_cota, cotas
        - contributions_df: Contributions with exact dates and amounts
    """
    reader = pypdf.PdfReader(file_path)
    row_map = {}
    contributions_list = []
    pat_date_month = re.compile(r'\d{2}/\d{4}')
    pat_date_full = re.compile(r'(\d{2}/\d{2}/\d{4})$')  # DD/MM/YYYY at end of line

    for page_num, page in enumerate(reader.pages, start=1):
        page_text_raw = page.extract_text()
        rows = page_text_raw.split('\n')
        rows = [row for row in rows if ('CONTRIB' in row) or ('TAXA' in row)]

        for row_num, row in enumerate(rows):
            row_split = row.split(" ")

            # Extract exact date (DD/MM/YYYY) from end of row
            full_date_match = pat_date_full.search(row)
            if full_date_match:
                data_exata = pd.to_datetime(full_date_match.group(1), format='%d/%m/%Y')
            else:
                # Fallback to month/year
                date_match = pat_date_month.findall(row)
                if not date_match:
                    continue
                data_exata = pd.to_datetime(date_match[0].strip(), format='%m/%Y')

            # Extract month/year for grouping position data
            date_match = pat_date_month.findall(row)
            if not date_match:
                continue
            mes_ano = pd.to_datetime(date_match[0].strip(), format='%m/%Y')

            quotas = float(row_split[-1][:-8].replace('.', '').replace(',', '.'))
            val_quota = float(row_split[-2].replace('.', '').replace(',', '.'))

            # Determine transaction type
            is_contribution = 'CONTRIB' in row and quotas > 0
            is_participant = 'PARTICIPANTE' in row

            row_map[f'{page_num}-{row_num}'] = {
                'mes_ano': mes_ano,
                'valor_cota': val_quota,
                'cotas': quotas
            }

            # Track actual contributions with exact dates
            if is_contribution:
                valor_contribuido = quotas * val_quota
                contributions_list.append({
                    'data_exata': data_exata,
                    'mes_ano': mes_ano,
                    'tipo': 'participante' if is_participant else 'patrocinador',
                    'valor': valor_contribuido
                })

    df_raw = pd.DataFrame.from_dict(row_map, orient='index')

    # Build contributions dataframe with exact dates
    if contributions_list:
        df_contrib_raw = pd.DataFrame(contributions_list)
        # Group by exact date and aggregate
        df_contributions = df_contrib_raw.groupby('data_exata').agg({
            'mes_ano': 'first',
            'valor': 'sum'
        }).reset_index()
        df_contributions = df_contributions.rename(columns={'valor': 'contribuicao_total', 'data_exata': 'data'})
        df_contributions = df_contributions.sort_values('data').reset_index(drop=True)
        df_contributions['contribuicao_acumulada'] = df_contributions['contribuicao_total'].cumsum()
    else:
        df_contributions = pd.DataFrame()

    return df_raw, df_contributions
