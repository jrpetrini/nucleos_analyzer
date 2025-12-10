#!/usr/bin/env python3
"""
Nucleos Analyzer - Pension fund analysis dashboard.

A tool for analyzing Brazilian pension fund (previdência privada) statements,
calculating XIRR using Brazilian business days, and visualizing performance.
"""

import argparse

from dashboard import create_app


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(
        description='Nucleos Analyzer - Pension fund analysis dashboard'
    )
    parser.add_argument(
        '--pdf',
        type=str,
        help='Path to the PDF file to load at startup'
    )
    args = parser.parse_args()

    print("Nucleos Analyzer")
    print("=" * 40)

    # Create app - optionally with initial data
    if args.pdf:
        from extractor import extract_data_from_pdf
        from calculator import process_position_data, process_contributions_data

        print(f"Carregando: {args.pdf}")
        df_raw, df_contributions_raw = extract_data_from_pdf(args.pdf)
        print(f"Registros extraídos: {len(df_raw)}")

        df_position = process_position_data(df_raw)
        df_contributions_monthly = process_contributions_data(df_contributions_raw)

        app = create_app(df_position, df_contributions_raw, df_contributions_monthly)
    else:
        print("Iniciando sem dados. Use 'Carregar Demo' ou faça upload de um PDF.")
        app = create_app()

    print()
    print("Iniciando dashboard em http://127.0.0.1:8050")
    print("Pressione Ctrl+C para encerrar")
    print()

    app.run(debug=True)


if __name__ == "__main__":
    main()
