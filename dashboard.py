#!/usr/bin/env python3
"""
Dashboard UI for Nucleos Analyzer.

This module serves as the main entry point for creating the Dash application.
The actual implementation is split across multiple modules for maintainability:

- components.py: Reusable UI components (help icons, cards, styles)
- figures.py: Chart/figure creation functions
- layout.py: Page layout assembly
- callbacks.py: All callback functions

This file provides backward compatibility by re-exporting commonly used functions.
"""

import pandas as pd
from dash import Dash

from layout import create_layout
from callbacks import register_callbacks

# Re-export for backward compatibility with existing code/tests
from components import COLORS, BENCHMARK_COLORS, OVERHEAD_OPTIONS, HELP_TEXTS, create_help_icon
from figures import create_position_figure, create_contributions_figure, create_empty_figure


def create_app(df_position: pd.DataFrame = None,
               df_contributions_raw: pd.DataFrame = None,
               df_contributions_monthly: pd.DataFrame = None) -> Dash:
    """Create the Dash application.

    Args:
        df_position: Processed position data (optional - can start without data)
        df_contributions_raw: Raw contributions with exact dates (for XIRR)
        df_contributions_monthly: Monthly aggregated contributions (for charts)

    Returns:
        Configured Dash application
    """
    app = Dash(__name__, suppress_callback_exceptions=True)

    # Create the layout
    app.layout = create_layout(df_position, df_contributions_raw, df_contributions_monthly)

    # Register all callbacks
    register_callbacks(app)

    return app
