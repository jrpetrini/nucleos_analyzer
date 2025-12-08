#!/usr/bin/env python3
"""
Nucleos Analyzer - Pension fund analysis dashboard.

A tool for analyzing Brazilian pension fund (previdência privada) statements,
calculating XIRR using Brazilian business days, and visualizing performance.
"""

import sys

from extractor import extract_data_from_pdf, select_pdf_file
from calculator import process_position_data, process_contributions_data
from dashboard import create_app


def main():
    """Main entry point for the application."""
    print("Nucleos Analyzer")
    print("=" * 40)

    # Get file path from command line or file picker
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = select_pdf_file()

    if not file_path:
        print("Nenhum arquivo selecionado. Encerrando.")
        sys.exit(0)

    print(f"Carregando: {file_path}")

    # Extract data from PDF
    df_raw, df_contributions_raw = extract_data_from_pdf(file_path)
    print(f"Registros extraídos: {len(df_raw)}")

    # Process data
    df_position = process_position_data(df_raw)
    df_contributions_monthly = process_contributions_data(df_contributions_raw)

    print()
    print("Iniciando dashboard em http://127.0.0.1:8050")
    print("Pressione Ctrl+C para encerrar")
    print()

    # Create and run dashboard
    app = create_app(df_position, df_contributions_raw, df_contributions_monthly)
    app.run(debug=False)


if __name__ == "__main__":
    main()
