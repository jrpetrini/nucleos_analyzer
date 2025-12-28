# Test Suite Audit Plan

Related: GitHub Issue #2

## User Decisions

1. **API calls**: Hardcode responses, keep 1-2 smoke tests
2. **Code duplication**: Keep as-is (acceptable for test isolation)
3. **Tolerances**: Tighten where possible, document inherent ones

---

## Phase 1: Critical Tolerance Fixes (from Issue #2)

### 1.1 test_extractor.py

| Line | Current | Problem | Fix |
|------|---------|---------|-----|
| 66-67 | `1.0 < cota < 2.0` | 100% range accepts anything | Tighten to known range ±0.15 |
| 126 | `< 1.0` (R$1.00) | Misses cents errors | `< 0.01` (1 cent) |

### 1.2 test_integration.py

| Line | Current | Problem | Fix |
|------|---------|---------|-----|
| 135 | `< 0.01` (1% relative) | R$600 diff allowed | `< 1.0` absolute |
| 295 | `< 0.7` (70% check) | Meaningless validation | Exact difference check |
| 659-660 | `40000 < pos < 60000` | 50% variance | `abs(pos - 55461.66) < 1.0` |

### 1.3 test_calculator.py

| Line | Current | Problem | Fix |
|------|---------|---------|-----|
| 224 | `< 0.02` (2%) | Deflation too loose | `< 0.001` (0.1%) |
| 367 | `-50 < cagr < 100` | 150% range | `8.0 < cagr < 12.0` |

---

## Phase 2: Hardcode API Responses

**File**: `tests/test_data_sources.py`

**Create fixtures**:
```
tests/fixtures/api_responses/
├── bcb_ipca_2024.json      # BCB series 433
├── bcb_inpc_2024.json      # BCB series 188
├── bcb_cdi_2024.json       # BCB series 4391
├── ipea_ipca_2024.json     # PRECOS12_IPCAG12
├── ipea_inpc_2024.json     # PRECOS12_INPCBR12
└── ipea_cdi_2024.json      # BM12_TJCDI12
```

**Tests to convert**:
- `TestBCBLibraryVsDirectAPI` (lines 106-181)
- `TestBCBvsIPEACrossValidation` (lines 184-272)
- `TestDataIntegrity` (lines 275-311)

**Tests to keep live** (with `@pytest.mark.slow`):
- `test_bcb_api_responds` (line 319)
- `test_ipea_api_responds` (line 324)

---

## Phase 3: Tolerance Investigation & Fixes

**5% tolerance (test_equivalence.py:409) - FIXED**:
- Root cause: was using varying `missing_cotas × current_valor_cota` per month
- Fix: use constant `missing_cotas × first_valor_cota` to match full PDF behavior
- Result: difference is now constant ~R$ 188.90 (not growing 2.6% → 4.7%)
- Changed from 5% relative tolerance to R$ 200 absolute tolerance

**3% tolerance (test_integration.py:834) - INHERENT**:
- Partition boundary crosses cota value change
- position_A_end = cotas_A × last_valor_cota_A
- starting_position_B = cotas_A × first_valor_cota_B
- Cannot know A's ending cota if only have B's data
- 3% covers typical monthly cota change (~1%) with margin

---

## Checklist

### Phase 1 - Tighten Tolerances (COMPLETED)
- [x] test_extractor.py:93-94 - Cota range (exact: 1.23418293 to 1.3493461878)
- [x] test_extractor.py:153 - Contribution tolerance (< 0.01 = 1 cent)
- [x] test_integration.py:135 - Contribution comparison (< 0.01 absolute)
- [x] test_integration.py:291-300 - Company toggle validation (exact match)
- [x] test_integration.py:664 - Final position (exact: 48813.06)
- [x] test_calculator.py:268 - Deflation tolerance (< 0.001 = 0.1%)
- [x] test_calculator.py:412 - CAGR (exact: 14.69%)
- [x] test_business_logic.py:256 - CAGR format validation (exact: +14.69% a.a.)

### Phase 2 - API Hardcoding (COMPLETED)
- [x] Create tests/fixtures/api_responses/ (6 JSON files)
- [x] Save BCB responses (IPCA, INPC, CDI for 2024)
- [x] Save IPEA responses (IPCA, INPC, CDI for 2024)
- [x] Removed TestBCBLibraryVsDirectAPI (tested external library)
- [x] Refactored TestBCBvsIPEACrossValidation (uses cached data)
- [x] Refactored TestDataIntegrity (uses cached data)
- [x] Added @pytest.mark.slow to TestAPIAvailability
- [x] Registered slow marker in pytest.ini

### Phase 3 - Tolerance Investigation (COMPLETED)
- [x] Fixed 5% tolerance bug → R$ 200 absolute (test_equivalence.py)
- [x] Documented 3% as inherent (test_integration.py:834)

---

## Test Count After Changes

- Before: 226 passed, 10 skipped, 1 flaky
- After: 232 passed, 0 skipped, 0 flaky
