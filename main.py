#!/usr/bin/env python3
"""
Nucleos Analyzer - Extracts and analyzes pension fund data from PDF statements.
"""

import re
import subprocess
import sys

import pandas as pd
import pypdf

# Try to import tkinter, but don't fail if it's not available
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
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
            [
                "zenity", "--file-selection",
                "--title=Selecione o arquivo extratoIndividual.pdf",
                "--file-filter=PDF files | *.pdf",
                "--file-filter=All files | *"
            ],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def select_pdf_file() -> str | None:
    """Opens a file dialog to select the PDF file, with fallbacks."""
    # Try tkinter first
    if HAS_TKINTER:
        try:
            return select_pdf_file_tkinter()
        except Exception:
            pass

    # Try zenity (common on Linux/GNOME)
    file_path = select_pdf_file_zenity()
    if file_path:
        return file_path

    # Fallback to command line input
    print("GUI não disponível. Digite o caminho do arquivo:")
    file_path = input("> ").strip()
    return file_path if file_path else None


def extract_data_from_pdf(file_path: str) -> pd.DataFrame:
    """
    Extracts contribution and fee data from the Nucleos PDF statement.

    Args:
        file_path: Path to the extratoIndividual.pdf file

    Returns:
        DataFrame with mes_ano, valor_cota, and cotas columns
    """
    reader = pypdf.PdfReader(file_path)

    row_map = {}
    pat_date = re.compile(r'\d{2}/\d{4}')

    for page_num, page in enumerate(reader.pages, start=1):
        print(f"Processando página {page_num}...")

        page_text_raw = page.extract_text()
        rows = page_text_raw.split('\n')
        rows = [row for row in rows if ('CONTRIB' in row) or ('TAXA' in row)]

        for row_num, row in enumerate(rows):
            row_split = row.split(" ")

            # Date pattern: MM/YYYY
            date_match = pat_date.findall(row)
            if not date_match:
                continue
            mes_ano = pd.to_datetime(date_match[0].strip(), format='%m/%Y')

            # Quotas: last position, excluding MM/YYYY at the end
            quotas = float(row_split[-1][:-8].replace('.', '').replace(',', '.'))

            # Quota value: second to last position
            val_quota = float(row_split[-2].replace('.', '').replace(',', '.'))

            row_map[f'{page_num}-{row_num}'] = {
                'mes_ano': mes_ano,
                'valor_cota': val_quota,
                'cotas': quotas
            }

    return pd.DataFrame.from_dict(row_map, orient='index')


def process_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Processes the raw extracted data to calculate cumulative quotas and positions.

    Args:
        df_raw: Raw DataFrame from extract_data_from_pdf

    Returns:
        Processed DataFrame with monthly aggregated data
    """
    df = df_raw.copy(deep=True)
    df['cotas_cumsum'] = df['cotas'].cumsum()
    df['posicao'] = df['cotas_cumsum'] * df['valor_cota']

    df = (
        df.groupby('mes_ano')
        .last()[['cotas_cumsum', 'posicao']]
        .rename(columns={'cotas_cumsum': 'cotas'})
    )

    df.index = df.index.to_period('M').to_timestamp(how='end').date

    return df


def show_completion_message(df_raw_len: int, df_nucleos_len: int):
    """Shows a completion message, using GUI if available."""
    msg = (
        f"Arquivo processado com sucesso!\n\n"
        f"Registros extraídos: {df_raw_len}\n"
        f"Meses processados: {df_nucleos_len}\n\n"
        f"Verifique o terminal para os resultados detalhados."
    )

    if HAS_TKINTER:
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Processamento Concluído", msg)
            root.destroy()
            return
        except Exception:
            pass

    # Fallback to terminal
    print("\n" + "=" * 40)
    print("PROCESSAMENTO CONCLUÍDO")
    print("=" * 40)
    print(msg)


def show_error_message(error: str):
    """Shows an error message, using GUI if available."""
    if HAS_TKINTER:
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Erro", error)
            root.destroy()
            return
        except Exception:
            pass

    print(f"\nERRO: {error}")


def main():
    """Main entry point for the application."""
    print("Nucleos Analyzer")
    print("=" * 40)

    # Check for command line argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = select_pdf_file()

    if not file_path:
        print("Nenhum arquivo selecionado. Encerrando.")
        sys.exit(0)

    print(f"Arquivo selecionado: {file_path}")
    print()

    try:
        # Extract data from PDF
        df_raw = extract_data_from_pdf(file_path)
        print(f"\nRegistros extraídos: {len(df_raw)}")
        print()

        # Process data
        df_nucleos = process_data(df_raw)

        # Display results
        print("Resultado Final:")
        print("=" * 40)
        print(df_nucleos.to_string())
        print()

        # Summary
        if len(df_nucleos) > 0:
            last_row = df_nucleos.iloc[-1]
            print(f"Última posição ({df_nucleos.index[-1]}):")
            print(f"  Cotas: {last_row['cotas']:,.2f}")
            print(f"  Posição: R$ {last_row['posicao']:,.2f}")

        show_completion_message(len(df_raw), len(df_nucleos))

    except Exception as e:
        error_msg = f"Erro ao processar o arquivo: {e}"
        print(error_msg)
        show_error_message(error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
