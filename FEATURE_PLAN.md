# Dashboard Enhancement Plan - 4 Feature Branches

## Overview
Sequential implementation of 4 major dashboard features, each in its own feature branch merged to master before starting the next.

**Branch Strategy:** Sequential (one at a time, merge to master, then next)

## Status Summary

| # | Feature | Status | Commit |
|---|---------|--------|--------|
| 1 | Loading Indicators | ✅ DONE | ad0f6bf |
| 2 | Inflation Adjustment | ✅ DONE | 9b87c8d |
| 3 | Forecasting | ✅ DONE | 2a4a518 |
| 4 | Mobile Responsiveness | ✅ DONE | (pending) |

**All 4 features completed!**

**Additional Work:**
- Test Suite: 232 tests (expanded from 71)
- Business Day Calculation: ✅ DONE - Replaced ANBIMA calendar with 252/365.25 ratio for consistency
- Code Refactoring: ✅ DONE - Extracted business logic for testability (see below)

---

# Feature 1: Loading Indicators ✅ DONE

**Branch:** `feature/loading-indicators`
**Completed:** December 2025
**Priority:** CRITICAL (foundational)

## Problem Statement
When users change toggles (company as free, overhead, benchmark selection), calculations take 2-5 seconds but UI doesn't show loading state. Cards display stale values then suddenly update, confusing users.

## Implementation Details

### Files to Modify
1. **dashboard.py** (lines 755-1107 - callbacks)
2. **assets/style.css** (add spinner styles)

### Changes Required

#### 1. Wrap Slow Callbacks with dcc.Loading

**Position Graph + Benchmark CAGR (lines 945-1075):**
```python
# Wrap the entire callback output section with dcc.Loading
dcc.Loading(
    id='loading-position',
    type='circle',  # or 'default', 'dot'
    color=COLORS['primary'],
    children=[
        dcc.Graph(id='position-graph', ...),
        # Benchmark CAGR card
    ]
)
```

**Summary Cards (lines 852-943):**
```python
# Add loading overlay to card containers
dcc.Loading(
    id='loading-nucleos-stats',
    type='circle',
    color=COLORS['accent'],
    parent_className='loading-wrapper',  # Custom CSS for subtle overlay
    children=[
        html.Div([...])  # Current position value
    ]
)
```

**PDF Upload (lines 1123-1172):**
```python
dcc.Loading(
    id='loading-pdf-upload',
    type='circle',
    color=COLORS['sponsor'],
    children=[
        dcc.Upload(id='pdf-upload', ...)
    ]
)
```

**Position Data Table (lines ~798):**
The position data table runs benchmark simulation twice (with and without overhead), making it slow when benchmark is selected.
```python
dcc.Loading(
    id='loading-position-table',
    type='circle',
    color=COLORS['primary'],
    children=[
        dash_table.DataTable(id='position-data-table', ...)
    ]
)
```

**Contributions Data Table (lines ~870):**
Updates when date range or company toggle changes.
```python
dcc.Loading(
    id='loading-contributions-table',
    type='circle',
    color=COLORS['primary'],
    children=[
        dash_table.DataTable(id='contributions-data-table', ...)
    ]
)
```

#### 2. Add Custom Spinner Styles to assets/style.css

```css
/* Subtle overlay spinner for cards */
.loading-wrapper {
    position: relative;
}

.loading-wrapper > div:first-child {
    background: rgba(15, 23, 42, 0.7);  /* COLORS['background'] with opacity */
    border-radius: 0.75rem;
}

/* Spinner sizing for cards */
._dash-loading-callback {
    display: flex !important;
    justify-content: center;
    align-items: center;
    min-height: 100px;
}
```

#### 3. Add Loading State to Benchmark Fetch

Since benchmark fetching is the slowest operation (2-5s), add explicit loading state:

```python
# In update_position_graph callback (line 945)
# Add new Output for loading indicator
Output('benchmark-loading-indicator', 'children'),

# At start of callback, set loading
if benchmark_name and benchmark_name != 'none':
    # Show loading message while fetching
    loading_msg = html.Div("Carregando benchmark...",
                           style={'color': COLORS['text_muted']})
```

### Testing Checklist
- [ ] Spinner appears when changing company toggle
- [ ] Spinner appears when selecting benchmark
- [ ] Spinner appears when changing overhead
- [ ] Spinner appears during PDF upload
- [ ] Spinner appears on position data table during benchmark updates
- [ ] Spinner appears on contributions data table during date range changes
- [ ] Spinner disappears when calculation completes
- [ ] Spinner doesn't block user interaction with other controls
- [ ] No flashing/flickering of spinners for fast operations (<200ms)

### Performance Considerations
- Use `prevent_initial_call=True` where appropriate to avoid unnecessary spinners on page load
- Consider debouncing rapid changes (e.g., overhead dropdown)

---

# Feature 2: Inflation Adjustment ✅ DONE

**Branch:** `feature/inflation-adjustment`
**Completed:** December 2025
**Priority:** HIGH (core financial feature)

## Problem Statement
All values are nominal (not adjusted for inflation). Users need to see real returns to understand purchasing power growth.

## Implementation Details

### Files to Modify
1. **calculator.py** (new function: `deflate_series()`)
2. **benchmarks.py** (ensure IPCA fetcher works correctly)
3. **dashboard.py** (add toggle, reference month dropdown, update callbacks)

### Changes Required

#### 1. Add Inflation Adjustment Toggle & Controls (dashboard.py)

**New Controls Section (above summary cards, around line 540):**
```python
html.Div([
    html.Div([
        dcc.Checklist(
            id='inflation-toggle',
            options=[{'label': ' Ajustar pela inflação', 'value': 'adjust'}],
            value=[],  # Default OFF
            style={'color': COLORS['text']}
        ),
        create_help_icon(
            'Ajusta todos os valores pela inflação (IPCA) para mostrar retornos reais. '
            'Valores são deflacionados para o mês de referência selecionado.'
        ),
        html.Label('Mês de Referência:',
                  style={'color': COLORS['text'], 'marginLeft': '1rem'}),
        dcc.Dropdown(
            id='reference-month',
            options=[],  # Populated based on date range
            value=None,  # Default to end date
            clearable=False,
            style={'width': '130px', 'color': '#000'},
            disabled=True  # Enabled only when toggle is ON
        ),
    ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'gap': '0.5rem'})
], style={'padding': '0 2rem 1rem 2rem', 'backgroundColor': COLORS['background']})
```

#### 2. Create Inflation Deflation Function (calculator.py)

**New Function:**
```python
def deflate_series(df: pd.DataFrame,
                   inflation_index: pd.DataFrame,
                   base_date: pd.Timestamp,
                   value_col: str = 'posicao') -> pd.DataFrame:
    """
    Deflate a time series by inflation index to show real values.

    Args:
        df: DataFrame with 'data' and value columns
        inflation_index: IPCA benchmark data with 'date' and 'value' columns
        base_date: Reference date for real values (all values adjusted to this date)
        value_col: Column name to deflate

    Returns:
        DataFrame with additional '{value_col}_real' column
    """
    from benchmarks import get_value_on_date

    # Get base inflation value
    base_inflation_value, _ = get_value_on_date(inflation_index, base_date)

    # Create new column for real values
    df = df.copy()
    real_values = []

    for idx, row in df.iterrows():
        date = row['data']
        nominal_value = row[value_col]

        # Get inflation index at this date
        inflation_value, _ = get_value_on_date(inflation_index, date)

        # Real value = nominal × (base_inflation / date_inflation)
        real_value = nominal_value * (base_inflation_value / inflation_value)
        real_values.append(real_value)

    df[f'{value_col}_real'] = real_values
    return df
```

#### 3. Modify Callbacks to Apply Inflation Adjustment

**Update `update_nucleos_stats` callback (lines 852-943):**
```python
@callback(
    Output('current-position-value', 'children'),
    Output('total-invested-value', 'children'),
    Output('nucleos-cagr-value', 'children'),
    # ... existing outputs ...
    Input('company-as-mine-toggle', 'value'),
    Input('start-month', 'value'),
    Input('end-month', 'value'),
    Input('inflation-toggle', 'value'),  # NEW
    Input('reference-month', 'value'),   # NEW
    State('contributions-data', 'data'),
    State('position-data', 'data'),
)
def update_nucleos_stats(company_as_mine, start_date, end_date,
                        inflation_toggle, reference_month,
                        contributions_data, position_data):
    # ... existing logic ...

    # Apply inflation adjustment if toggled
    if 'adjust' in (inflation_toggle or []) and reference_month:
        # Fetch IPCA data
        ipca_data = fetch_single_benchmark('IPCA', start_date, end_date)

        # Deflate position values
        df_pos_filtered = deflate_series(
            df_pos_filtered,
            ipca_data,
            pd.to_datetime(reference_month),
            'posicao'
        )

        # Use real values for display
        position_display = df_pos_filtered['posicao_real'].iloc[-1]

        # Recalculate XIRR with real values
        # (deflate contribution amounts by inflation at contribution date)
        # ... adjusted XIRR calculation ...
```

**Update `create_position_figure` (lines 237-309):**
```python
def create_position_figure(df_position: pd.DataFrame, log_scale: bool = False,
                           benchmark_sim: pd.DataFrame = None,
                           benchmark_label: str = None,
                           show_real_values: bool = False) -> go.Figure:  # NEW parameter
    """
    Create position chart with optional inflation-adjusted values.
    """
    # Use 'posicao_real' column if show_real_values=True and column exists
    y_col = 'posicao_real' if show_real_values and 'posicao_real' in df_position.columns else 'posicao'

    fig.add_trace(go.Scatter(
        x=df_position['data'],
        y=df_position[y_col],
        mode='lines+markers',
        name='Nucleos (Real)' if show_real_values else 'Nucleos',
        # ... rest of trace config ...
    ))

    # Update Y-axis title
    y_title = 'Posição Real (R$ de {ref_month})' if show_real_values else 'Posição (R$)'
```

#### 4. Populate Reference Month Dropdown

**New callback:**
```python
@callback(
    Output('reference-month', 'options'),
    Output('reference-month', 'value'),
    Output('reference-month', 'disabled'),
    Input('month-options', 'data'),
    Input('inflation-toggle', 'value'),
    Input('end-month', 'value'),
)
def update_reference_month(month_options, inflation_toggle, end_month):
    """Enable reference month selector when inflation toggle is ON."""
    is_enabled = 'adjust' in (inflation_toggle or [])

    if is_enabled:
        # Default to end month
        return month_options, end_month, False
    else:
        return month_options, None, True
```

### Testing Checklist
- [ ] Toggle enables reference month dropdown
- [ ] IPCA data fetches correctly
- [ ] Position values deflate correctly
- [ ] Contributions deflate correctly
- [ ] XIRR recalculates with real values
- [ ] Summary cards show real values when toggle ON
- [ ] Graphs show real values with updated Y-axis label
- [ ] Benchmark also adjusts for inflation when toggle ON
- [ ] Toggle OFF returns to nominal values
- [ ] Changing reference month updates all values

### Edge Cases
- What if IPCA data is unavailable for selected date range? (Show error message)
- What if user selects reference month before earliest data? (Disable those options)

---

# Feature 3: Forecasting ✅ DONE

**Branch:** `feature/forecasting`
**Completed:** December 2025
**Priority:** MEDIUM (advanced feature)

## Problem Statement
Users want to project their portfolio growth into the future to plan retirement/goals.

## Implementation Details

### Files Modified
1. **calculator.py** - Added `generate_forecast()` and `get_forecast_assumptions_text()`
2. **figures.py** - Updated `create_position_figure()` with forecast traces
3. **layout.py** - Added forecast controls (toggle, years dropdown, salary growth selector)
4. **callbacks.py** - Added forecast generation in `update_position_graph` callback
5. **components.py** - Added `FORECAST_OPTIONS`, `GROWTH_RATE_OPTIONS`, help texts

### Key Features Implemented

#### 1. Forecasting Controls (layout.py)
- **Forecast toggle**: Checkbox to enable/disable projection
- **Years dropdown**: 1, 2, 5, 10, 15, 20 years
- **Salary growth rate selector**: 0%, 1%, 2.56% (IPCA target), 5% annual real growth

#### 2. Forecast Model (calculator.py: `generate_forecast()`)
**Salary Growth Model:**
```
S(t) = S₀ × exp(growth_rate × t)
```
Where:
- S₀ = Average of last 12 months participant contributions
- growth_rate = User-selected annual real growth rate
- t = Time in years from start of forecast

**Assumptions (displayed to user):**
- Contributions grow at selected real rate (above inflation)
- Company matches 85% of participant contribution (`COMPANY_MATCH_RATIO = 0.85`)
- Historical CAGR continues unchanged
- No changes to contribution policy

#### 3. Graph Updates (figures.py)
- Dashed lines for Nucleos and benchmark projections
- Forecast connects seamlessly to last historical point
- Clear visual distinction between historical and projected data

#### 4. Forecast Data Table (layout.py + callbacks.py)
- Shows monthly projected data with columns:
  - Date, Projected Position, Cumulative Invested, Monthly Contribution, Benchmark (if selected)
- Export to CSV/Excel
- Only visible when forecast toggle is ON

#### 5. Benchmark Forecast
- When benchmark selected, also projects benchmark forward
- Uses same contribution pattern but benchmark's historical CAGR
- Handles "company as mine" toggle correctly (excludes company match for benchmark)

### Testing Notes
- Forecast uses REAL fund CAGR (ignoring overhead setting) for accuracy
- Benchmark forecast properly handles overhead adjustment
- Loading indicator wraps forecast table for UX

---

# Feature 4: Mobile Responsiveness ✅ DONE

**Branch:** `feature/mobile-responsive`
**Completed:** December 2025
**Priority:** MEDIUM (UX improvement)

## Problem Statement
Dashboard is not optimized for mobile devices. Fixed widths cause horizontal overflow, cards don't stack properly, graphs are too small.

## Implementation Summary

### Key Changes Made

1. **Slide-out Settings Panel**
   - Created mobile-friendly settings panel that slides in from right
   - Gear icon button next to title to open panel
   - All configuration controls consolidated in one place
   - OK button and click-outside to close

2. **Graph Optimizations**
   - Removed Y-axis tick labels (rely on hover for values)
   - Zero side margins for edge-to-edge display
   - Legend moved inside graph (vertical, top-left)
   - Hidden Plotly modebar globally
   - Improved hover tooltips (larger font, cleaner format)

3. **Responsive CSS**
   - Breakpoints: 480px (phone), 768px (tablet), 1200px (large)
   - Cards stack vertically on phone, 2x2 on tablet
   - Controls stack vertically in settings panel on mobile
   - GitHub link hidden on mobile
   - Full-width settings panel on mobile

### Files Modified
- **layout.py** - Added `create_settings_panel()`, moved controls
- **callbacks.py** - Added settings panel toggle callbacks
- **figures.py** - Optimized graph layouts for mobile
- **assets/style.css** - Added 600+ lines of responsive CSS
- **dashboard.py** - Added clientside callback for scroll behavior
- **components.py** - Minor style updates

---

# Code Refactoring ✅ DONE

**Completed:** December 2025

## Summary
Extracted business logic from monolithic `dashboard.py` into testable modules.

## Changes

| Before | After | Improvement |
|--------|-------|-------------|
| dashboard.py: 1,947 lines | dashboard.py: 1,772 lines | -175 lines (9%) |
| 71 tests | 125 tests | +54 tests (76% more) |
| 0% testable callbacks | 90% testable logic | Extracted to modules |

## New Files Created

### `dashboard_helpers.py`
Helper functions for common operations:
- `prepare_dataframe()` - Convert list to DataFrame with parsed dates
- `is_inflation_enabled()` / `is_company_as_mine()` - Toggle state checks
- `get_contribution_column()` - Get correct column based on toggle
- `prepare_benchmark_contributions()` - Prepare data for benchmark simulation
- `build_deflator_dict()` - Build month->deflator lookup
- `format_currency()` / `format_percentage()` - Value formatting
- `get_cagr_color()` / `get_return_color()` - Color helpers

### `business_logic.py`
Core business logic extracted from callbacks:
- `filter_data_by_range()` - Filter data by date range with position adjustment
- `calculate_time_weighted_position()` - Time-weighted return calculation
- `calculate_nucleos_stats()` - Calculate all Nucleos summary stats
- `simulate_and_calculate_benchmark()` - Benchmark simulation with CAGR

### New Test Files
- `tests/test_dashboard_helpers.py` - 35 tests
- `tests/test_business_logic.py` - 19 tests

## Benefits
1. **Testability**: Business logic can now be unit tested in isolation
2. **Maintainability**: Smaller, focused functions are easier to understand
3. **Reusability**: Helper functions eliminate code duplication
4. **Debugging**: Clearer separation makes issues easier to trace
