#!/usr/bin/env python3
"""
Debug script to calculate benchmark CAGR by hand with high precision.
"""

import pandas as pd
import sys
from decimal import Decimal, getcontext

# Set high precision
getcontext().prec = 50

# Add the project root to path
sys.path.insert(0, '.')

from extractor import extract_data_from_pdf, detect_partial_history
from calculator import process_position_data, process_contributions_data, xirr_bizdays, apply_deflation
from benchmarks import fetch_single_benchmark, apply_overhead_to_benchmark, simulate_benchmark


def debug_benchmark_cagr(pdf_path: str, start_date: str = None, end_date: str = None):
    """Calculate benchmark CAGR with full debug output."""

    print("=" * 80)
    print("BENCHMARK CAGR DEBUG ANALYSIS")
    print("=" * 80)

    # 1. Load PDF data
    print("\n1. LOADING PDF DATA...")
    df_raw, df_contributions_raw = extract_data_from_pdf(pdf_path)
    pdf_metadata = detect_partial_history(pdf_path, df_raw)

    print(f"   PDF is partial: {pdf_metadata.get('is_partial', False)}")
    if pdf_metadata.get('is_partial'):
        print(f"   Missing cotas: {pdf_metadata.get('missing_cotas', 0):.10f}")
        print(f"   Starting position: {pdf_metadata.get('starting_position', 0):.10f}")

    # Process data
    starting_cotas = pdf_metadata.get('missing_cotas', 0) if pdf_metadata.get('is_partial') else 0
    df_position = process_position_data(df_raw, starting_cotas=starting_cotas)
    df_contributions_monthly = process_contributions_data(df_contributions_raw)

    # 2. Set date range
    if not start_date:
        start_date = df_position['data'].min().isoformat()
    if not end_date:
        end_date = df_position['data'].max().isoformat()

    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date)

    print(f"\n2. DATE RANGE: {start_dt.date()} to {end_dt.date()}")

    # 3. Filter data by date range
    df_pos_filtered = df_position[
        (df_position['data'] >= start_dt) & (df_position['data'] <= end_dt)
    ].copy()

    df_contrib_filtered = df_contributions_raw[
        (df_contributions_raw['data'] >= start_dt) & (df_contributions_raw['data'] <= end_dt)
    ].copy()

    print(f"   Filtered positions: {len(df_pos_filtered)} rows")
    print(f"   Filtered contributions: {len(df_contrib_filtered)} rows")

    # 4. Fetch benchmark data (CDI)
    print("\n3. FETCHING BENCHMARK DATA (CDI)...")
    benchmark_name = 'CDI'
    benchmark_raw = fetch_single_benchmark(
        benchmark_name,
        (start_dt - pd.DateOffset(months=1)).strftime('%Y-%m-%d'),
        end_date
    )
    print(f"   Benchmark data points: {len(benchmark_raw)}")

    # Apply 0% overhead (no change)
    benchmark_with_overhead = apply_overhead_to_benchmark(benchmark_raw, 0)

    # 5. Fetch inflation data (IPCA)
    print("\n4. FETCHING INFLATION DATA (IPCA)...")
    extended_start = (start_dt - pd.DateOffset(months=1)).replace(day=1)
    inflation_data = fetch_single_benchmark('IPCA', extended_start.strftime('%Y-%m-%d'), end_date)
    print(f"   Inflation data points: {len(inflation_data)}")

    # Reference month for deflation (use most recent)
    inflation_ref_month = df_position['data'].max().isoformat()
    print(f"   Inflation reference: {inflation_ref_month}")

    # 6. Apply deflation to contributions
    print("\n5. APPLYING DEFLATION TO CONTRIBUTIONS...")
    _, df_contrib_deflated = apply_deflation(
        df_pos_filtered.copy(), df_contrib_filtered.copy(), inflation_data, inflation_ref_month
    )

    print("   Contributions (nominal vs deflated):")
    for _, row in df_contrib_deflated.iterrows():
        orig_row = df_contrib_filtered[df_contrib_filtered['data'] == row['data']].iloc[0]
        print(f"      {row['data'].date()}: R$ {orig_row['contribuicao_total']:.10f} -> R$ {row['contribuicao_total']:.10f}")

    # 7. Simulate benchmark
    print("\n6. SIMULATING BENCHMARK...")

    # === LOCAL PATH (with partial PDF handling) ===
    print("\n   --- LOCAL PATH (with starting_position) ---")
    df_contrib_sim_local = df_contrib_filtered[['data']].copy()
    df_contrib_sim_local['contribuicao_total'] = df_contrib_filtered['contribuicao_total']

    # Prepend starting_position like local does
    if pdf_metadata.get('is_partial'):
        starting_pos = pdf_metadata.get('starting_position', 0)
        first_pos_date = df_pos_filtered['data'].min()
        starting_contrib = pd.DataFrame({
            'data': [first_pos_date],
            'contribuicao_total': [starting_pos]
        })
        df_contrib_sim_local = pd.concat([starting_contrib, df_contrib_sim_local], ignore_index=True)
        print(f"   Prepended starting_position: R$ {starting_pos:.10f} on {first_pos_date.date()}")

    if not df_contrib_sim_local.empty:
        first_contrib_month_local = df_contrib_sim_local['data'].min().to_period('M')
        position_dates_local = df_pos_filtered[
            df_pos_filtered['data'].dt.to_period('M') >= first_contrib_month_local
        ][['data']].copy()
    else:
        position_dates_local = df_pos_filtered[['data']].copy()

    print(f"   First contrib month (local): {first_contrib_month_local}")
    print(f"   Position dates (local): {len(position_dates_local)} dates")
    print(f"   Dates: {[d.date() for d in position_dates_local['data']]}")

    # === LIVE PATH (without starting_position) ===
    print("\n   --- LIVE PATH (without starting_position) ---")
    df_contrib_sim = df_contrib_filtered[['data']].copy()
    df_contrib_sim['contribuicao_total'] = df_contrib_filtered['contribuicao_total']

    if not df_contrib_sim.empty:
        first_contrib_month = df_contrib_sim['data'].min().to_period('M')
        position_dates_for_bench = df_pos_filtered[
            df_pos_filtered['data'].dt.to_period('M') >= first_contrib_month
        ][['data']].copy()
    else:
        position_dates_for_bench = df_pos_filtered[['data']].copy()

    print(f"   First contrib month (live): {first_contrib_month}")
    print(f"   Position dates (live): {len(position_dates_for_bench)} dates")
    print(f"   Dates: {[d.date() for d in position_dates_for_bench['data']]}")

    # Check if they differ
    dates_differ = len(position_dates_local) != len(position_dates_for_bench)
    print(f"\n   POSITION DATES DIFFER: {dates_differ}")

    # === RUN BOTH SIMULATIONS ===
    print("\n7. RUNNING SIMULATIONS FOR CAGR...")
    from calculator import deflate_series
    last_date = df_pos_filtered['data'].iloc[-1]

    # LOCAL: uses bench_sim_for_cagr (separate sim without starting_position)
    # But the position_dates might differ!
    bench_sim_local = simulate_benchmark(
        df_contrib_sim,  # Without starting_position (same as what's used for CAGR)
        benchmark_with_overhead,
        position_dates_local  # LOCAL uses dates from df_contrib_sim_local (with starting)
    )
    bench_sim_local_deflated = deflate_series(bench_sim_local, inflation_data, inflation_ref_month, 'posicao')
    bench_sim_local_deflated['posicao'] = bench_sim_local_deflated['posicao_real']
    cagr_final_local = bench_sim_local_deflated['posicao'].iloc[-1] if not bench_sim_local_deflated.empty else 0

    print(f"\n   LOCAL simulation:")
    print(f"      Dates used: {len(position_dates_local)}")
    print(f"      Final value (deflated): R$ {cagr_final_local:.10f}")

    # LIVE: uses benchmark_sim directly
    bench_sim_live = simulate_benchmark(
        df_contrib_sim,
        benchmark_with_overhead,
        position_dates_for_bench  # LIVE uses dates from df_contrib_sim (no starting)
    )
    bench_sim_live_deflated = deflate_series(bench_sim_live, inflation_data, inflation_ref_month, 'posicao')
    bench_sim_live_deflated['posicao'] = bench_sim_live_deflated['posicao_real']
    cagr_final_live = bench_sim_live_deflated['posicao'].iloc[-1] if not bench_sim_live_deflated.empty else 0

    print(f"\n   LIVE simulation:")
    print(f"      Dates used: {len(position_dates_for_bench)}")
    print(f"      Final value (deflated): R$ {cagr_final_live:.10f}")

    print(f"\n   FINAL VALUE DIFFERENCE: R$ {cagr_final_local - cagr_final_live:.10f}")

    # 8. Calculate CAGR for both
    print("\n8. CALCULATING CAGR FOR BOTH...")

    dates = df_contrib_deflated['data'].tolist() + [last_date]
    contrib_amounts = df_contrib_deflated['contribuicao_total'].tolist()

    # LOCAL CAGR
    amounts_local = [-amt for amt in contrib_amounts] + [cagr_final_local]
    bench_cagr_local = xirr_bizdays(dates, amounts_local)

    # LIVE CAGR
    amounts_live = [-amt for amt in contrib_amounts] + [cagr_final_live]
    bench_cagr_live = xirr_bizdays(dates, amounts_live)

    print(f"\n   LOCAL CAGR: {bench_cagr_local * 100:.10f}%" if bench_cagr_local else "   LOCAL CAGR: N/A")
    print(f"   LIVE CAGR:  {bench_cagr_live * 100:.10f}%" if bench_cagr_live else "   LIVE CAGR: N/A")

    if bench_cagr_local and bench_cagr_live:
        cagr_diff = (bench_cagr_local - bench_cagr_live) * 100
        print(f"\n   CAGR DIFFERENCE: {cagr_diff:.10f}%")

    print("\n   Cash flows (for reference):")
    for d, a in zip(dates[:-1], [-amt for amt in contrib_amounts]):
        print(f"      {d.date()}: R$ {a:.10f}")
    print(f"      {last_date.date()}: R$ {cagr_final_live:.10f} (LIVE)")
    print(f"      {last_date.date()}: R$ {cagr_final_local:.10f} (LOCAL)")

    # 9. Compare with standard pyxirr
    print("\n9. COMPARISON WITH STANDARD XIRR (365 days)...")
    from pyxirr import xirr as pyxirr_standard
    standard_cagr_local = pyxirr_standard([d.date() for d in dates], amounts_local)
    standard_cagr_live = pyxirr_standard([d.date() for d in dates], amounts_live)
    print(f"   LOCAL (365d): {standard_cagr_local * 100:.10f}%" if standard_cagr_local else "   LOCAL: N/A")
    print(f"   LIVE (365d):  {standard_cagr_live * 100:.10f}%" if standard_cagr_live else "   LIVE: N/A")

    benchmark_final_value = cagr_final_live  # Use live for return value
    bench_cagr = bench_cagr_live

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

    return bench_cagr, benchmark_final_value, dates, amounts


if __name__ == '__main__':
    # Use test fixture if available, or prompt for path
    import os

    test_pdf = 'tests/fixtures/extrato_nucleos_2024.pdf'
    if os.path.exists(test_pdf):
        debug_benchmark_cagr(test_pdf)
    else:
        print("Please provide a PDF path as argument")
        if len(sys.argv) > 1:
            debug_benchmark_cagr(sys.argv[1])
