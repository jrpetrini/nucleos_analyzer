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

## Phase 3: Document Inherent Tolerances

These **cannot be reduced** - document why:

**5% tolerance (test_equivalence.py:409)**:
- Valor_cota changes month-to-month
- Partial PDFs use first available cota, not historical
- Example: 50,000 cotas × 1.348 (Dec) vs × 1.385 (Jan) = 2.7% diff

**3% tolerance (test_integration.py:828)**:
- Partition boundary crosses cota value change
- Position = cotas × valor_cota at month-end
- Adjacent months differ ~1-2%

---

## Checklist

### Phase 1 - Tighten Tolerances
- [ ] test_extractor.py:66-67 - Cota range
- [ ] test_extractor.py:126 - Contribution tolerance
- [ ] test_integration.py:135 - Contribution comparison
- [ ] test_integration.py:295 - Company toggle validation
- [ ] test_integration.py:659-660 - Final position bounds
- [ ] test_calculator.py:224 - Deflation tolerance
- [ ] test_calculator.py:367 - CAGR range

### Phase 2 - API Hardcoding
- [ ] Create tests/fixtures/api_responses/
- [ ] Save BCB responses (IPCA, INPC, CDI)
- [ ] Save IPEA responses (IPCA, INPC, CDI)
- [ ] Refactor TestBCBLibraryVsDirectAPI
- [ ] Refactor TestBCBvsIPEACrossValidation
- [ ] Refactor TestDataIntegrity
- [ ] Add @pytest.mark.slow to smoke tests

### Phase 3 - Documentation
- [ ] Document 5% tolerance in test_equivalence.py
- [ ] Document 3% tolerance in test_integration.py

---

## Test Count After Changes

- Current: 226 passed, 10 skipped, 1 flaky
- After: 226+ passed, ~2 skipped (smoke tests), 0 flaky
