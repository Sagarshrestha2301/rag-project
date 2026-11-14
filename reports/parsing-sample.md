# Step 3 report (generated)

- Documents: **60**, pages: **557**, tables: **169**, OCR pages: **58**, unreadable: **17**
- Parse time: **997.5 s** for 557 pages = **33.5 pages/min**
- Table detection costs **387.1 s** over 499 pages (776 ms/page, run on every page); text extraction without it: 49.0 pages/min
- OCR: 58 pages, 6.7 s/page
- Extrapolation at the measured whole-run rate: **49.7 h for 100k pages**

## Table cell check

- Tables: **169**
- Numeric tokens: **2466**, matched against the page's own words: **2463**

Mismatches:
- 2011_Hendri_Towards_An_Integrated_Fire_Management_Framework_Using_Space_W1850677407.pdf p6 table 1: '3.CO2emission' not in the page's words
- 2000_Global_ice_core_research_Understanding_and_applying_environmental_reco_30757.pdf p2 table 1: '.26' not in the page's words
- 2000_Global_ice_core_research_Understanding_and_applying_environmental_reco_30757.pdf p2 table 1: '000,000,000,000,000,000' not in the page's words

## Per document

| Document | Tables | Numeric tokens | Matched |
|---|---|---|---|
| 1970_Ahasan_Variability_and_Trends_of_Summer | 3 | 119 | 119 |
| 1970_Das_Beliefs_superstitions_and_taboos_as | 6 | 274 | 274 |
| 1970_Bhandary_Flood_of_discoveries_in_Nepal_ | 1 | 6 | 6 |
| 2001_Li_Water_Induced_Disasters_in_The_Hindu | 2 | 38 | 38 |
| 2007_Ghimire_Preparing_for_Flood_Disaster_Ma | 6 | 211 | 211 |
| 1966_ngstr_m_Note_on_solar_radiation_in_moun | 1 | 83 | 83 |
| 1970_Chaulagain_Climate_Change_Impacts_on_Wa | 3 | 227 | 227 |
| 1970_Acharya_Effect_of_Processing_Temperatur | 4 | 29 | 29 |
| 1970_Adhikari_Infraspecific_Variation_of_Bam | 2 | 49 | 49 |
| 1970_Ali_Treatment_Feasibility_of_NSSC_Pulpi | 2 | 5 | 5 |
| 0_untitled_Deforestation_Reforestation_and_C | 6 | 26 | 26 |
| 1959_Unknown_II_General_Review_and_Summary_o | 3 | 27 | 27 |
| 2011_Hendri_Towards_An_Integrated_Fire_Manag | 5 | 71 | 70 |
| 2014_Ghimire_Fire_hazard_zonation_of_Bardia_ | 2 | 51 | 51 |
| 1970_Acharya_Dimension_of_Rural_Development_ | 3 | 1 | 1 |
| 1970_Bhattarai_The_Use_of_Plants_for_Fencing | 1 | 40 | 40 |
| nd_1041631032Citizen_Charter_c8c23c9550.pdf | 1 | 1 | 1 |
| 2012_non_hasl_movement_survey_survey_rusc_20 | 67 | 52 | 52 |
| 2018_in_community_forest_promotion_worksheas | 1 | 0 | 0 |
| 2023_annual_conservation_action_plan_2080_20 | 16 | 844 | 844 |
| 2012_simsus_proberation_2069_7a4f998242.pdf | 8 | 3 | 3 |
| 2019_national_agricultural_forest_policy_207 | 3 | 2 | 2 |
| 2024_Pokharel_and_Thakuri_2024_d92c84a62f.pd | 3 | 48 | 48 |
| nd_Birendra_Tal_En_0_89cf5a4595.pdf | 2 | 11 | 11 |
| nd_Birendra_Tal_Np_e9f8d6c163.pdf | 1 | 2 | 2 |
| nd_Human_Monkey_Conflict_16_march_65ab2e61f6 | 3 | 10 | 10 |
| 1991_Preliminary_report_on_geologic_features | 1 | 3 | 3 |
| 2000_Global_ice_core_research_Understanding_ | 3 | 35 | 33 |
| 2007_Digital_outlines_and_topography_of_the_ | 10 | 198 | 198 |

## Documents that could not be parsed

These files are in `data/corpus/` but produced no pages. They are kept so the gap is visible; delete or replace them only with the owner's approval.

- `2005_Choudhary_Trans_boundary_Floods_Induced_by_Global_Climate_Change_Devel_W210886295.pdf` (cc9c659224a2…): pdfplumber could not open; tables skipped
- `2006_Komori_Scars_of_the_Glacial_Lake_Outburst_Flood_in_Sabai_Tsho_Hinku_W2328682512.pdf` (a91cb6634f33…): pdfplumber could not open; tables skipped

## Pages with no text layer and no OCR

- `2001_Li_Water_Induced_Disasters_in_The_Hindu_Kush_Himalayan_Region_A_W3204701976.pdf`: 1 (1 of 9)
- `2003_Shrestha_Regional_Cooperation_for_Flood_Disaster_Mitigation_in_the_Hi_W3204336300.pdf`: 1 (1 of 12)
- `2005_Choudhary_Trans_boundary_Floods_Induced_by_Global_Climate_Change_Devel_W210886295.pdf`: 1, 2, 3, 4 (4 of 4)
- `2018_in_community_forest_promotion_worksheas_discipline_2075_54a1176a69.pdf`: 3, 6, 8, 27 (4 of 27)
- `2023_annual_conservation_action_plan_2080_2090_0ec3a3f7d9.pdf`: 2, 8, 27 (3 of 28)
- `2012_simsus_proberation_2069_7a4f998242.pdf`: 5, 24 (2 of 24)
- `2018_national_forest_policy_2075_efe9910b55.pdf`: 5, 20 (2 of 21)
