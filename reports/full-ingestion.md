# Full ingestion (Step 8)

Written by `python -m ingest.pipeline status`; every number is read from
`index/manifest.sqlite`, not estimated.

- Documents in the manifest: **97**
- Status counts: `{"pending": 0, "parsed": 0, "chunked": 0, "embedded": 97, "duplicate": 0, "failed": 0}`
- Failures: **0**
- Duplicates flagged and skipped: **0**
- Documents without a valid SHA-256: **0**
- Sum of the measured per-document parse times: **1414 s**

## Index size (bytes on disk)

| Artifact | Bytes |
|---|---|
| `index/pages.json` | 2,411,349 |
| `index/chunks.jsonl` | 6,640,297 |
| `index/parsed/` (pages.jsonl + shards) | 12,549,431 |
| `index/lancedb/` | 17,568,907 |
| `index/manifest.sqlite` | 151,552 |
| **total `index/`** | **41,969,013** |

## Failures with reasons

None.

## Duplicates (kept, not indexed)

None.

## Unreadable pages per document

- `2001_Li_Water_Induced_Disasters_in_The_Hindu_Kush_Himalayan_Region_A_W3204701976.pdf`: pages [1]
- `2003_Shrestha_Regional_Cooperation_for_Flood_Disaster_Mitigation_in_the_Hi_W3204336300.pdf`: pages [1]
- `2005_Choudhary_Trans_boundary_Floods_Induced_by_Global_Climate_Change_Devel_W210886295.pdf`: pages [1, 2, 3, 4]
- `2018_in_community_forest_promotion_worksheas_discipline_2075_54a1176a69.pdf`: pages [3, 6, 8, 27]
- `2023_annual_conservation_action_plan_2080_2090_0ec3a3f7d9.pdf`: pages [2, 8, 27]
- `2012_simsus_proberation_2069_7a4f998242.pdf`: pages [5, 24]
- `2018_national_forest_policy_2075_efe9910b55.pdf`: pages [5, 20]
- `2002_Estimating_the_Endogenously_Determined_Intrahousehold_Balance_of_Power_27cab411_9a31_511c_b5b4.pdf`: pages [4, 20]

## Scale

The corpus this pipeline currently runs on is the 97-document / 851-page set,
so the numbers above are that scale. The 100k-page target is a scope question
for the owner (see `STATUS.md`); nothing here is projected to it.
