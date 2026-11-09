# ACLED validation (DR Congo, export of 2026-11-09)

## Internal consistency
| Check | Result |
|---|---|
| `year` = year of `event_date` | all 43,275 rows |
| Event IDs | all `DRC…`, no duplicate IDs |
| Months with zero events, 1997–2025 | none |
| Negative fatalities | none |
| Province names | the 26 post-2015 provinces, applied to all years, including 1997 |
| Coordinates against province | 7 Rusankuku events with the wrong latitude sign → fixed (`geo_fix`) |
| Exact content duplicates | 41 pairs, mostly 1997–2002 → flagged (`dup_flag`) |
| `geo_precision` 1 / 2 / 3 | 29,591 / 13,004 / 680 |
| Largest fatality value | 1,037 (Bukavu, 2009, precision 3, so excluded from buffers) |
| Export end date | **2025-11-09**. Rows were edited up to 2026-11-07, so the export probably stops one year early (because of the account tier or the selected date range). |

## External comparison with UCDP GED v26.1
Run with `09_validate_acled_ucdp.py`. To compare like with like:
- **ACLED:** battles, violence against civilians and explosions with fatalities > 0 and `geo_precision` ≤ 2.
- **UCDP:** `where_prec` ≤ 3. UCDP records only lethal organised violence above 25 deaths per conflict-year.

### Event matching (counterpart within 25 km and ±7 days)
| Period | UCDP events | ACLED events | UCDP found in ACLED | ACLED found in UCDP |
|---|---|---|---|---|
| 1997–2009 | 1,689 | 1,220 | **22.6 %** | 36.2 % |
| 2010–2017 | 1,553 | 2,048 | 43.9 % | 35.8 % |
| 2018–2025 | 6,207 | 11,807 | **87.7 %** | 69.7 % |
| 1997–2025 | 9,449 | 15,075 | 68.9 % | 62.4 % |

### Other measures
- **Annual events:** Pearson 0.90, Spearman 0.81. **Annual deaths:** 0.52.
- **0.5° grid:** log totals per cell correlate at 0.82, and log counts per cell-year at 0.59. 253 of the 322 cells with UCDP events also have ACLED events.
- **1997–2003:** ACLED's death totals are 17–50% of UCDP's in most years, so ACLED badly undercounts the Second Congo War.
- **2018 onwards:** ACLED has about twice as many lethal events as UCDP, as expected given UCDP's 25-death threshold, and death ratios are 1.0–2.0.

### Implications
- **From 2010, especially 2018:** ACLED exposure is reliable for these years.
- **Before 2010:** treat ACLED exposure with caution. Report UCDP-based exposure as a robustness check, or control for year.
- **Comparisons:** prefer within-year comparisons across clusters, for example with year fixed effects, to raw comparisons over time, because ACLED's number of sources rose from about 150 to about 2,460.
