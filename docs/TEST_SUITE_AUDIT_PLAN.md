# Test Suite Audit Plan

## User Decisions

1. **API calls**: Hardcode responses, keep 1-2 smoke tests
2. **Code duplication**: Keep as-is (acceptable for test isolation)
3. **Tolerances**: Investigated - both are inherent, accept with documentation

---

## Actions to Execute

### 1. Hardcode API Responses in test_data_sources.py

**File**: `tests/test_data_sources.py`

**What to do**:
- Create `tests/fixtures/api_responses/` directory
- Save sample BCB and IPEA responses as JSON files
- Refactor tests to use hardcoded data for cross-validation
- Keep only 2 smoke tests with `@pytest.mark.slow` for actual connectivity

**Tests to convert to hardcoded**:
- `TestBCBLibraryVsDirectAPI` (lines 106-181) - Use cached responses
- `TestBCBvsIPEACrossValidation` (lines 184-272) - Use cached responses
- `TestDataIntegrity` (lines 275-311) - Use cached responses

**Tests to keep live (with @pytest.mark.slow)**:
- `TestAPIAvailability.test_bcb_api_responds` (line 319)
- `TestAPIAvailability.test_ipea_api_responds` (line 324)

### 2. Document Tolerances (No Code Changes)

**5% tolerance (test_equivalence.py:409)**:
- Root cause: Valor_cota changes month-to-month
- Partial PDFs use first available cota value, not historical
- Example: 50,000 cotas × 1.348 (Dec) vs × 1.385 (Jan) = 2.7% diff
- **Inherent mathematical limitation - cannot be reduced**

**3% tolerance (test_integration.py:828)**:
- Same root cause: partition boundary crosses cota value change
- Position = cotas × valor_cota at that month's end
- Adjacent months have different cota values (~1-2% growth)
- **Inherent mathematical limitation - cannot be reduced**

**Action**: Add docstring comments explaining why these tolerances exist

---

## Files to Modify

1. `tests/test_data_sources.py` - Refactor to use hardcoded responses
2. `tests/fixtures/api_responses/` - New directory with JSON fixtures
3. `tests/test_equivalence.py` - Add tolerance documentation
4. `tests/test_integration.py` - Add tolerance documentation

---

## Hardcoded Data to Create

```
tests/fixtures/api_responses/
├── bcb_ipca_2024.json      # BCB series 433 for 2024
├── bcb_inpc_2024.json      # BCB series 188 for 2024
├── bcb_cdi_2024.json       # BCB series 4391 for 2024
├── ipea_ipca_2024.json     # IPEA PRECOS12_IPCAG12 for 2024
├── ipea_inpc_2024.json     # IPEA PRECOS12_INPCBR12 for 2024
└── ipea_cdi_2024.json      # IPEA BM12_TJCDI12 for 2024
```

---

## Test Count After Changes

- Current: 226 passed, 10 skipped, 1 flaky (API timeout)
- After: 226+ passed, ~8 skipped (smoke tests when offline), 0 flaky
