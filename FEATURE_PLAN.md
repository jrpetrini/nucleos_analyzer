# Dashboard Enhancement Plan - 4 Feature Branches

## Overview
Sequential implementation of 4 major dashboard features, each in its own feature branch merged to master before starting the next.

**Branch Strategy:** Sequential (one at a time, merge to master, then next)

## Status Summary

| # | Feature | Status | Commit |
|---|---------|--------|--------|
| 1 | Loading Indicators | ✅ DONE | ad0f6bf |
| 2 | Inflation Adjustment | ✅ DONE | 9b87c8d |
| 3 | Forecasting | 🔲 TODO | - |
| 4 | Mobile Responsiveness | 🔲 TODO | - |

**Additional Work:**
- Test Suite: 47 tests (commit e9e8a5f)
- Business Day Calculation: Under investigation (see .claude/plans/vivid-napping-rainbow.md)

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

# Feature 3: Forecasting

**Branch:** `feature/forecasting`
**Estimated Duration:** 2-3 days
**Priority:** MEDIUM (advanced feature)

## Problem Statement
Users want to project their portfolio growth into the future to plan retirement/goals.

## Implementation Details

### Files to Modify
1. **calculator.py** (new function: `forecast_contributions()`)
2. **benchmarks.py** (extend `get_value_on_date` extrapolation)
3. **dashboard.py** (add forecast toggle, years dropdown, update graphs)
4. **requirements.txt** (add `statsmodels>=0.14.0` for ARIMA)

### Changes Required

#### 1. Add Forecasting Controls (dashboard.py)

**New Controls Section (within Position tab, near benchmark controls):**
```python
html.Div([
    dcc.Checklist(
        id='forecast-toggle',
        options=[{'label': ' Projetar no futuro', 'value': 'enabled'}],
        value=[],  # Default OFF
        style={'color': COLORS['text']}
    ),
    create_help_icon(
        'Projeta a posição no futuro usando CAGR histórico e padrão de contribuições. '
        'Área sombreada indica projeção (não garantida).'
    ),
    html.Label('Anos:', style={'color': COLORS['text'], 'marginLeft': '1rem'}),
    dcc.Dropdown(
        id='forecast-years',
        options=[
            {'label': '1 ano', 'value': 1},
            {'label': '2 anos', 'value': 2},
            {'label': '5 anos', 'value': 5},
            {'label': '10 anos', 'value': 10},
            {'label': '15 anos', 'value': 15},
            {'label': '20 anos', 'value': 20},
        ],
        value=5,  # Default 5 years
        clearable=False,
        style={'width': '100px', 'color': '#000'},
        disabled=True  # Enabled only when forecast toggle ON
    ),
], style={'display': 'flex', 'alignItems': 'center', 'gap': '0.5rem', 'marginTop': '0.5rem'})
```

#### 2. Create Contribution Forecasting Function (calculator.py)

**New Function:**
```python
def forecast_contributions(df_contributions: pd.DataFrame,
                          months_ahead: int,
                          method: str = 'mean') -> pd.DataFrame:
    """
    Forecast future monthly contributions.

    Args:
        df_contributions: Historical contribution data
        months_ahead: Number of months to forecast
        method: 'mean' (simple average) or 'arima' (statistical model)

    Returns:
        DataFrame with forecasted contributions
    """
    if method == 'mean':
        # Simple approach: average of last 12 months
        recent_12 = df_contributions.tail(12)
        avg_contribution = recent_12['contribuicao_total'].mean()

        # Generate future dates
        last_date = df_contributions['data'].max()
        future_dates = pd.date_range(
            start=last_date + pd.DateOffset(months=1),
            periods=months_ahead,
            freq='M'
        )

        return pd.DataFrame({
            'data': future_dates,
            'contribuicao_total': [avg_contribution] * months_ahead,
            'is_forecast': [True] * months_ahead
        })

    elif method == 'arima':
        # Statistical approach using ARIMA(1,1,1)
        from statsmodels.tsa.arima.model import ARIMA

        # Fit ARIMA model on contribution amounts
        model = ARIMA(df_contributions['contribuicao_total'], order=(1, 1, 1))
        fitted = model.fit()

        # Forecast
        forecast = fitted.forecast(steps=months_ahead)

        # Generate future dates
        last_date = df_contributions['data'].max()
        future_dates = pd.date_range(
            start=last_date + pd.DateOffset(months=1),
            periods=months_ahead,
            freq='M'
        )

        return pd.DataFrame({
            'data': future_dates,
            'contribuicao_total': forecast.values,
            'is_forecast': [True] * months_ahead
        })
```

#### 3. Update Graph to Show Forecast with Shading

**Modify `create_position_figure` (lines 237-309):**
```python
def create_position_figure(df_position: pd.DataFrame, log_scale: bool = False,
                           benchmark_sim: pd.DataFrame = None,
                           benchmark_label: str = None,
                           forecast_data: pd.DataFrame = None) -> go.Figure:  # NEW
    """
    Create position chart with optional forecast projection.
    """
    # ... existing traces ...

    # Add forecast trace if provided
    if forecast_data is not None and not forecast_data.empty:
        # Dashed line for forecast
        fig.add_trace(go.Scatter(
            x=forecast_data['data'],
            y=forecast_data['posicao'],
            mode='lines',
            name='Projeção Nucleos',
            line=dict(color=COLORS['primary'], width=2, dash='dash'),
            hovertemplate='<b>%{x|%b %Y}</b><br>Projeção: R$ %{y:,.2f}<extra></extra>'
        ))

        # Shaded region for uncertainty
        # Create confidence interval (e.g., ±10% around forecast)
        upper_bound = forecast_data['posicao'] * 1.1
        lower_bound = forecast_data['posicao'] * 0.9

        fig.add_trace(go.Scatter(
            x=forecast_data['data'].tolist() + forecast_data['data'].tolist()[::-1],
            y=upper_bound.tolist() + lower_bound.tolist()[::-1],
            fill='toself',
            fillcolor='rgba(99, 102, 241, 0.1)',  # COLORS['primary'] with low opacity
            line=dict(color='rgba(255,255,255,0)'),
            showlegend=False,
            hoverinfo='skip'
        ))
```

#### 4. Generate Forecast in Callback

**Update `update_position_graph` callback:**
```python
@callback(
    # ... existing outputs ...
    Input('forecast-toggle', 'value'),  # NEW
    Input('forecast-years', 'value'),   # NEW
    # ... existing inputs ...
)
def update_position_graph(scale, start_date, end_date, benchmark_name, overhead,
                          company_as_mine, forecast_toggle, forecast_years,
                          position_data, contributions_data, date_range, cache):
    # ... existing logic ...

    # Generate forecast if enabled
    forecast_data = None
    if 'enabled' in (forecast_toggle or []):
        months_ahead = forecast_years * 12

        # Forecast contributions
        forecasted_contributions = forecast_contributions(
            df_contrib_filtered,
            months_ahead,
            method='mean'  # Or allow user to choose
        )

        # Calculate future position using CAGR
        last_position = df_pos_filtered['posicao'].iloc[-1]
        last_date = df_pos_filtered['data'].iloc[-1]

        # Use historical CAGR to project forward
        cagr = xirr_bizdays(dates, amounts)  # From earlier calculation

        future_positions = []
        cumulative_position = last_position

        for idx, row in forecasted_contributions.iterrows():
            # Add contribution
            cumulative_position += row['contribuicao_total']
            # Apply monthly growth
            monthly_rate = (1 + cagr) ** (1/12) - 1
            cumulative_position *= (1 + monthly_rate)
            future_positions.append(cumulative_position)

        forecast_data = pd.DataFrame({
            'data': forecasted_contributions['data'],
            'posicao': future_positions
        })

    # Pass forecast_data to create_position_figure
    fig = create_position_figure(
        df_pos_filtered,
        log_scale=(scale == 'log'),
        benchmark_sim=benchmark_sim,
        benchmark_label=benchmark_label,
        forecast_data=forecast_data  # NEW
    )
```

### Testing Checklist
- [ ] Forecast toggle enables years dropdown
- [ ] Forecast generates reasonable future dates
- [ ] Contribution forecast uses appropriate method (mean vs ARIMA)
- [ ] Position projection uses historical CAGR
- [ ] Dashed line appears for forecast
- [ ] Shaded region appears for uncertainty
- [ ] Forecast works with inflation adjustment toggle
- [ ] Benchmark also forecasts when selected
- [ ] Forecast updates when changing date range
- [ ] Disabling forecast removes projection

### Performance Considerations
- ARIMA model fitting can be slow (1-2s) - wrap in loading indicator
- Consider caching ARIMA models per contribution pattern

---

# Feature 4: Mobile Responsiveness

**Branch:** `feature/mobile-responsive`
**Estimated Duration:** 1-2 days
**Priority:** MEDIUM (UX improvement)

## Problem Statement
Dashboard is not optimized for mobile devices. Fixed widths cause horizontal overflow, cards don't stack properly, graphs are too small.

## Implementation Details

### Files to Modify
1. **dashboard.py** (remove fixed widths, add responsive styles)
2. **assets/style.css** (add media queries)
3. **assets/custom-mobile.css** (new file - mobile-specific styles)

### Changes Required

#### 1. Remove Fixed Widths from Dropdowns (dashboard.py)

**Date Dropdowns (lines 638, 646):**
```python
# BEFORE:
style={'width': '130px', 'color': '#000'}

# AFTER:
style={'minWidth': '130px', 'maxWidth': '200px', 'width': '100%', 'color': '#000'}
```

**Benchmark/Overhead Dropdowns (lines 735, 744):**
```python
# BEFORE:
style={'width': '150px', 'color': '#000'}

# AFTER:
style={'minWidth': '100px', 'maxWidth': '150px', 'width': '100%', 'color': '#000'}
```

#### 2. Make Summary Cards Stack on Mobile

**Update Cards Container (line 622-627):**
```python
style={
    'display': 'flex',
    'flexDirection': 'row',  # Desktop
    'flexWrap': 'wrap',      # Allow wrapping
    'gap': '1rem',
    'padding': '0 2rem',
    'marginBottom': '2rem',
    'backgroundColor': COLORS['background']
}

# Add CSS class for responsive behavior
className='summary-cards-container'
```

#### 3. Add Mobile CSS (assets/custom-mobile.css)

**New File:**
```css
/* Mobile Breakpoints */

/* Tablet (portrait) and below - 768px */
@media (max-width: 768px) {
    /* Stack summary cards 2x2 */
    .summary-cards-container {
        flex-direction: row !important;
    }

    .summary-cards-container > div {
        flex: 1 1 calc(50% - 0.5rem) !important;
        min-width: 150px;
    }

    /* Reduce padding */
    body > div > div {
        padding: 1rem !important;
    }

    /* Date controls stack */
    #date-controls > div {
        flex-wrap: wrap !important;
        justify-content: center !important;
    }

    /* Dropdown widths */
    .Select {
        min-width: 100px !important;
        max-width: 150px !important;
    }
}

/* Phone (portrait) - 480px and below */
@media (max-width: 480px) {
    /* Stack all cards vertically */
    .summary-cards-container {
        flex-direction: column !important;
    }

    .summary-cards-container > div {
        flex: 1 1 100% !important;
    }

    /* Reduce title size */
    h1 {
        font-size: 1.75rem !important;
    }

    /* Smaller padding everywhere */
    body > div > div {
        padding: 0.5rem !important;
    }

    /* Help tooltips narrower */
    .help-tooltip {
        min-width: 200px !important;
        max-width: 90vw !important;
    }

    /* Graph height */
    #position-graph, #contributions-graph {
        height: 400px !important;
    }
}

/* Landscape orientation - prioritize graphs */
@media (max-width: 768px) and (orientation: landscape) {
    /* Graphs take more height */
    #position-graph, #contributions-graph {
        height: 60vh !important;
    }

    /* Cards in single row */
    .summary-cards-container {
        flex-direction: row !important;
        overflow-x: auto;
    }
}
```

#### 4. Add Viewport Meta Tag Check

**Verify in dashboard layout** that Dash includes viewport meta tag (it should by default):
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0">
```

If not present, add to `app.index_string`.

#### 5. Make Graphs Responsive

**Update graph height in create_position_figure/create_contributions_figure:**
```python
fig.update_layout(
    height=500,  # Default desktop
    autosize=True,  # Allow responsive sizing
    # ... other layout options ...
)
```

**Add config for better mobile interaction:**
```python
dcc.Graph(
    id='position-graph',
    config={
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d'],
        'toImageButtonOptions': {
            'format': 'png',
            'filename': 'nucleos_position',
            'height': 800,
            'width': 1200,
        }
    }
)
```

### Testing Checklist
- [ ] Test on iPhone SE (375px width)
- [ ] Test on iPhone 12 Pro (390px width)
- [ ] Test on iPad (768px width)
- [ ] Test on iPad Pro landscape (1024px width)
- [ ] Cards stack properly at each breakpoint
- [ ] Dropdowns don't overflow horizontally
- [ ] Graphs are readable (not too small)
- [ ] Touch interactions work (pinch-zoom, pan)
- [ ] Tooltips don't go off-screen
- [ ] Help icons work on touch devices
- [ ] PDF upload button accessible on mobile

### Browser Testing
- [ ] Safari iOS
- [ ] Chrome Android
- [ ] Samsung Internet
- [ ] Firefox Mobile

---

# Implementation Timeline

## Week 1
- **Days 1-2:** Feature 1 (Loading Indicators)
  - Implement all dcc.Loading wrappers
  - Add spinner styles
  - Test all slow operations
  - Merge to master

## Week 2
- **Days 3-6:** Feature 2 (Inflation Adjustment)
  - Implement deflate_series()
  - Add toggle and reference month controls
  - Update all callbacks
  - Update graphs with real/nominal toggle
  - Comprehensive testing
  - Merge to master

## Week 3
- **Days 7-9:** Feature 3 (Forecasting)
  - Implement forecast_contributions()
  - Add forecast toggle and years dropdown
  - Update graphs with dashed lines and shading
  - Test ARIMA vs mean forecasting
  - Merge to master

## Week 4
- **Days 10-11:** Feature 4 (Mobile Responsiveness)
  - Remove fixed widths
  - Add CSS media queries
  - Test on multiple devices
  - Merge to master

---

# Git Workflow

For each feature:

1. **Create feature branch from master:**
   ```bash
   git checkout master
   git pull origin master
   git checkout -b feature/[name]
   ```

2. **Implement feature with incremental commits:**
   ```bash
   git add [files]
   git commit -m "[feature]: [description]"
   ```

3. **Test thoroughly before merge**

4. **Merge to master:**
   ```bash
   git checkout master
   git merge feature/[name]
   git push origin master
   ```

5. **Push to Hugging Face:**
   ```bash
   git push hf master:main
   ```

---

# Critical Files Reference

- **dashboard.py:** Main UI and callbacks (lines 1-1172)
- **calculator.py:** XIRR and data processing (lines 1-164)
- **benchmarks.py:** Benchmark fetching and simulation (lines 1-407)
- **assets/style.css:** Current styles (lines 1-11)
- **requirements.txt:** Dependencies

---

# Risk Mitigation

1. **Loading Indicators:** Low risk - purely additive, doesn't change calculations
2. **Inflation Adjustment:** Medium risk - changes financial calculations, needs thorough testing
3. **Forecasting:** Medium risk - complex calculations, ARIMA dependency, performance impact
4. **Mobile Responsiveness:** Low risk - CSS-only changes, doesn't affect logic

**Rollback Strategy:** Each feature is in its own branch. If issues arise, can revert the merge commit to master and debug separately.
- Give multiple options for different user skill levels
- Link to free tools users already trust
