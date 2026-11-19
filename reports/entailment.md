# Sentence-level entailment check (prototype, D-067)

Written by `scripts/measure-entailment.py`. This is a **secondary signal**, not a
gate: the judge is `qwen3.5:4b` at temperature 0, and D-010/D-058 keep the
page-checked quotation as the arbiter. A failure here means the sentence goes
beyond the words it quotes; it does not mean the fact is wrong.

## Summary

- Answers in the run: **41**; sentences judged: **96**
- SUPPORTED: **55**
- PARTIAL: **3**
- UNSUPPORTED: **34**
- No verdict (judge error or unparseable): **0**
- Sentences whose marker has no citation line: **4**
- Every judged row is in `reports/entailment.jsonl` with the quote, the file and
  page, and the numbers the sentence states that the quote does not.

37 of 92 judged sentences are not fully supported by the quote they cite (40.2%). Of those 37, 15 state a number that the quotation lacks but the cited page prints (a weak quotation, not an invented fact) and 0 state a number that appears neither in the quotation nor on the page.

## Sentences that are not fully supported

- `q002` [4] **UNSUPPORTED** — "This discharge was estimated using the slope area method with an appropriate roughness coefficient of 0.06 for the Bagmati River [4]."
  - reason: The quote provides flood values but does not mention the estimation method or roughness coefficient.
  - quote: "The peak floods in Bagmati and in East- Rapti River were found to be 12,000 m3 s-1 and 6800 m3s -1 respectively."
- `q002` [4] **UNSUPPORTED** — "These floods were accompanied by eroded and displaced earth masses that turned into debris torrents [4]."
  - reason: The quote mentions flood volumes but not debris torrents.
  - quote: "The peak floods in Bagmati and in East- Rapti River were found to be 12,000 m3 s-1 and 6800 m3s -1 respectively."
- `q004` [1] **UNSUPPORTED** — "This region includes active alluvial plains, river fans, and various types of hilly and mountainous terrain with differing slopes [1]."
  - reason: The quote mentions area size but not terrain types.
  - quote: "The areal coverage of the physiographical feature of Bagmati River that had favored severe flooding is only about 1845 km2."
- `q004` [2] **UNSUPPORTED** — "These floods occurred within a drainage area of 2720 km² near Nunthar, resulting in a surge of 16,000 m³ s⁻¹ [2]."
  - reason: The sentence claims a 16,000 m³/s surge, but the quote states 12,000 m³/s.
  - quote: "A 1993-flood peak of 12,000 m3 s-1 (MOWR, 1993) was the highest flood assessed in Bagmati River at Nunthar having drainage area of 2720 km2."
- `q006` [1] **UNSUPPORTED** — "These smaller catchments are particularly prone to severe flooding with debris torrents [1]."
  - reason: The quote mentions flow ranges but does not mention flooding or debris torrents.
  - quote: "The specific flows range from 4 to 15 m3s-1 km-2 in streams having drainage areas of different sizes (100 to 3000 km2)."
- `q006` [1] **UNSUPPORTED** — "The study recommends applying these equations only for areas between 90 to 700 km² and 90 to 2700 km² respectively [1]."
  - reason: The quote does not mention recommendations or specific equation ranges.
  - quote: "The specific flows range from 4 to 15 m3s-1 km-2 in streams having drainage areas of different sizes (100 to 3000 km2)."
- `q006` [1] **UNSUPPORTED** — "Specific discharges have been found relatively high for smaller catchments in this region [1]."
  - reason: The quote does not mention relative discharge levels or specific regions.
  - quote: "The specific flows range from 4 to 15 m3s-1 km-2 in streams having drainage areas of different sizes (100 to 3000 km2)."
- `q008` [5] **UNSUPPORTED** — "This value was part of a set of coefficients estimated by various agencies using the slope area method to assess floods in 1993 [5]."
  - reason: The quote only mentions the report title, not the specific coefficient or estimation methods.
  - quote: "DHM/DPTC, 1994. Report on 1993 Flood Assessment of Bagmati and East-Rapti River."
- `q008` [1] **UNSUPPORTED** — "The specific discharge for the Bagmati River during this event was found to be 12,000 m³ s⁻¹ [1]."
  - reason: The quote mentions roughness coefficients but not specific discharge values.
  - quote: "The coefficient values (DHM/DPTC, 1994) varied from 0.033 for Rapti River at Bhandara, 0.06 for Bagmati, 0.07 for Kyankhola, and 0.07 for Agrakhola."
- `q010` [1] **UNSUPPORTED** — "The correlation coefficient found for equation (2) is 0.78 [1]."
  - reason: The quote does not mention equation (2).
  - quote: "The correlation coefficient is found to be 0.78"
- `q011` [1] **UNSUPPORTED** — "This specific range was determined because specific discharges found relatively high for smaller catchments below this threshold [1]."
  - reason: The quote does not mention discharge levels or the reason for the range.
  - quote: "The equation (3) and the equation (4) can be recommended to apply only for areas between 90 to 700 Km2 and 90 to 2700 km2 respectively."
- `q011` [1] **PARTIAL** — "The study also notes that streams with drainage areas larger than 700 km² should use equation (4) instead [1]."
  - reason: The quote specifies ranges but does not mention streams or explicitly recommend equation (4).
  - quote: "The equation (3) and the equation (4) can be recommended to apply only for areas between 90 to 700 Km2 and 90 to 2700 km2 respectively."
- `q012` [2] **UNSUPPORTED** — "This measurement was recorded at Ghantemadi during the extreme rainfall event in July 1993 [2]."
  - reason: The quote does not mention the date or event type.
  - quote: "The 48-hour rainfall depth at Ghantemadi was 600 mm."
- `q012` [5] **UNSUPPORTED** — "The maximum rainfall depth (P0) serves as a key parameter in the depth-area-duration equation derived for the region [5]."
  - reason: The quote mentions relations but does not specify P0 or duration.
  - quote: "A relation for rainfall depth and other relation for specific flood are presented in this paper."
- `q013` [1] **UNSUPPORTED** — "This equation relates rainfall depth P to catchment area A through a specific exponential formula involving P0, which is the maximum rainfall at the center of the storm [1]."
  - reason: The quote mentions an equation but does not specify it is exponential or define P0.
  - quote: "et contours for 24-hour and 48-hour rainfall depths were drawn; and an equation (1) for depth area duration curves of the storm was determined"
- `q013` [1] **UNSUPPORTED** — "In the study area, P0 values were observed as 540 mm for 24-hour duration and 600 mm for 48-hour duration in 1993 [1]."
  - reason: The quote mentions drawing contours but does not provide specific rainfall depth values.
  - quote: "et contours for 24-hour and 48-hour rainfall depths were drawn; and an equation (1) for depth area duration curves of the storm was determined"
- `q017` [1] **UNSUPPORTED** — "These measurements were taken during the morning hours of July 20th, 1993 [1]."
  - reason: The quote does not mention the year 1993.
  - quote: "The 24-hour rainfall depth of 540 mm at Tistung and 482 mm at Ghantemadi were recorded in morning hours of 20th July."
- `q020` [1] **UNSUPPORTED** — "They mention that data collection started in the sixties [1] and describe the physiographical features of the 1845 km² area [1], but no specific population figure is given for this region."
  - reason: The quote mentions data collection, not population or geography.
  - quote: "Hydrological and meteorological data collection at the organizational level had started during the sixties in Nepal."
- `q024` [1] **UNSUPPORTED** — "This value was determined using the slope area method with a roughness coefficient of 0.07 [1]."
  - reason: The quote provides flood values but does not mention the calculation method or coefficients.
  - quote: "The peak floods in Bagmati and in East- Rapti River were found to be 12,000 m3 s-1 and 6800 m3s -1 respectively."
- `q024` [1] **UNSUPPORTED** — "Other agencies like ICIMOD and JICA were involved in assessing this and other floods from 1993 [1]."
  - reason: The quote mentions flood levels but not the agencies or year.
  - quote: "The peak floods in Bagmati and in East- Rapti River were found to be 12,000 m3 s-1 and 6800 m3s -1 respectively."
- `q025` [2] **UNSUPPORTED** — "According to Table 1, 139 households in the Terai believe in taboos and superstitions associated with bamboos [2]."
  - reason: The quote shows 139 is a percentage, not a count of households.
  - quote: "Believe in taboos and superstitions 139 69.85"
- `q029` [1] **UNSUPPORTED** — "In the Terai table, 68.33% of bamboo growers believe in superstitions and taboos that discourage bamboo planting [1]."
  - reason: The quote only lists numbers without stating they represent percentages or beliefs.
  - quote: "Grower 41 36.61 68.33"
- `q029` [1] **UNSUPPORTED** — "This figure is derived from the row labeled "Grower" under the column "% of Column Believe" for the Terai region [1]."
  - reason: The quote contains no reference to a table, regions, or specific labels.
  - quote: "Grower 41 36.61 68.33"
- `q029` [1] **UNSUPPORTED** — "The corresponding count for these growers who hold these beliefs is 41 out of a total sample size of 68 [1]."
  - reason: The quote only lists numbers, not the sample size or belief details.
  - quote: "Grower 41 36.61 68.33"
- `q034` [1] **UNSUPPORTED** — "This value was derived from data covering all ranges of study areas up to 2700 km² [1]."
  - reason: The quote does not mention the specific range of 2700 km² or how the value was derived.
  - quote: "The correlation coefficient is found to be 0.78"
- `q034` [1] **UNSUPPORTED** — "The authors note that this correlation is satisfactory for the entire dataset used in their analysis [1]."
  - reason: The quote does not mention the authors' assessment of the correlation's quality.
  - quote: "The correlation coefficient is found to be 0.78"
- `q043` [1] **UNSUPPORTED** — "This practice contrasts with other regions where bamboo is associated with youth and love rather than sadness or magic [1]."
  - reason: The quote does not mention other regions or bamboo's associations elsewhere.
  - quote: "In Bangladesh, when a villager is buried a small piece of bamboo is hung above the grave in order to scare away evil spirits"
- `q043` [1] **UNSUPPORTED** — "The belief system surrounding bamboo varies significantly across different cultures in South and South-East Asia [1]."
  - reason: The quote only mentions Bangladesh, not other cultures or regions.
  - quote: "In Bangladesh, when a villager is buried a small piece of bamboo is hung above the grave in order to scare away evil spirits"
- `q045` [3] **PARTIAL** — "In the Terai, 31.67% of nongrowers and 68.33% of growers believe in taboos and superstitions that discourage bamboo planting [3]."
  - reason: The quote lists numbers but does not explicitly link them to beliefs about taboos or discourage planting.
  - quote: "Do not Believe Believe Nongrowers 19 21.84 31.67 68 78.16 48.92 Grower 41 36.61 68.33 71 63.39 51.08"
- `q045` [2] **UNSUPPORTED** — "The study found a statistically significant association where those who believe are less likely to grow bamboo compared to those who do not [2]."
  - reason: The quote lacks specific data on households, location, or statistical significance.
  - quote: "Those who believe in superstitions and/ or taboos are less likely to grow than those who do not believe."
- `q046` [4] **UNSUPPORTED** — "The superstition suggests that nothing grows under bamboos and crop productivity declines considerably in adjacent areas [4]."
  - reason: The quote mentions reduced productivity but does not claim nothing grows or specify "adjacent" areas.
  - quote: "The most common belief associated with bamboos was that it reduces the productivity of the land where it grows."
- `q049` [2] **PARTIAL** — "If there are no old males over 60 years in the house, a middle-aged man aged 40 years or over can carry out bamboo planting [2]."
  - reason: The sentence adds an unsupported requirement of "old males" and "over 60".
  - quote: "In the absence of old age members in the family it can be carried out by the middle aged household heads or members (40 years or over)."
- `q049` [3] **UNSUPPORTED** — "The belief that only the oldest household male members should do it is common among older age groups [3]."
  - reason: The quote mentions gender restrictions but not age or specific roles.
  - quote: "It was found that there is a general belief among the households that bamboos should not be felled on Tuesday and that the women must not cut bamboo culms."
- `q049` [1] **UNSUPPORTED** — "However, younger families generally do not believe in this superstition but hesitate to plant themselves [1]."
  - reason: The quote does not mention younger families or their beliefs.
  - quote: "If there are no old males (over 60 years) in the house then it can be carried out by a middle-aged man."
- `q051` [1] **UNSUPPORTED** — "This belief is part of a broader set of superstitions where women are also considered unable to propagate bamboo successfully [1]."
  - reason: The quote mentions male age limits but says nothing about women or propagation.
  - quote: "Some households in the Midhills mentioned that only males over 50 years of age should carry out harvesting of new shoots."
- `q051` [1] **UNSUPPORTED** — "The study notes that while these taboos were prevalent among older generations, they were less strong among the younger generation in both the Terai and Midhills [1]."
  - reason: The quote mentions only the Midhills and does not discuss the Terai or generational differences.
  - quote: "Some households in the Midhills mentioned that only males over 50 years of age should carry out harvesting of new shoots."
- `q052` [2] **UNSUPPORTED** — "Kerabari is exposed to elephant damage because bamboo clumps are a favored species for wild elephants [2]."
  - reason: The quote mentions elephants roaming but does not specify bamboo as their favorite food.
  - quote: "Kerabari lies on the migratory route of wild elephants and every 2-3 years wild elephants roam around Kerabari and damage crops of the households and sometimes even attack men."

## Method

- Source run: `eval/runs/2026-11-19-step8-full/run.jsonl` (55 questions).
- A sentence joins the check when it has four or more words, carries `[n]`,
  and is not a refusal.
- The quote is the one the answer printed for that `[n]`, which the verifier
  already matched against the cited page.
- One judge call per sentence; temperature 0, seed 0; the verdict is the
  first word of the reply.
