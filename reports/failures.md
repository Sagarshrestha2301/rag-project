# Remaining failures, grouped by cause (Step 9 task 1)

Source run: `eval/runs/2026-11-19-step8-full`. Written by `python eval/failures.py`;
the causes are the rules `eval/score.py` applied, not a reading of the answers.

| Cause | Questions |
|---|---|
| retrieval miss | 3 |
| citation | 12 |
| number | 2 |
| false not found | 2 |
| answered an unanswerable question | 3 |
| **total failing** | **22** |

## retrieval miss (3)

- **q015** (summary, not_found, also: false not found, citation) - What does the paper recommend about where equations (1) to (4) may be applied?
  - answer: Not found in the indexed documents.
- **q045** (number, verified, also: citation, number) - What share of households in the Terai believes in taboos and superstitions about bamboo?
  - answer: In the Terai, 31.67% of nongrowers and 68.33% of growers believe in taboos and superstitions that discourage bamboo planting [3]. The overall percentage of households in the Terai holding these beliefs is not explicitly stated as a single c
- **q046** (table, verified, also: citation, number) - In the Terai, what percentage of households said bamboo reduces the productivity of the land?
  - answer: The most commonly held belief against bamboo planting was that it reduces the productivity of the land [4]. This belief is shared by a significant majority of households across different regions including the Terai and Midhills [6]. The sup

## citation (12)

- **q004** (fact, verified) - How large is the area of the Bagmati River basin whose physiography favoured severe flooding?
  - answer: The area of the Bagmati River basin whose physiographical features favored severe flooding is approximately 1845 km² [1]. This region includes active alluvial plains, river fans, and various types of hilly and mountainous terrain with diffe
- **q008** (exact, verified) - Which roughness coefficient was used for the Bagmati River?
  - answer: The roughness coefficient used for the Bagmati River was 0.06 [1]. This value was part of a set of coefficients estimated by various agencies using the slope area method to assess floods in 1993 [5]. The specific discharge for the Bagmati R
- **q012** (exact, verified) - What value of P0 was observed for the 48-hour duration in the study area?
  - answer: The value of P0 observed for the 48-hour duration in the study area was 600 mm [1]. This measurement was recorded at Ghantemadi during the extreme rainfall event in July 1993 [2]. The maximum rainfall depth (P0) serves as a key parameter in
- **q024** (followup, verified) - And what was the peak flood on the East-Rapti?
  - answer: The peak flood on the East-Rapti River was estimated at 6,800 m³/s [1]. This value was determined using the slope area method with a roughness coefficient of 0.07 [1]. Other agencies like ICIMOD and JICA were involved in assessing this and 
- **q027** (table, unverified, also: number, verification failed) - In Table 2, how many Terai households strongly believe in the superstitions and taboos against bamboo planting?
  - answer: The provided passages do not contain Table 2 or specific data on the number of Terai households who "strongly believe" in superstitions. [1] Das 1970, page 6, file 1970_Das_Beliefs_superstitions_and_taboos_associated_with_bamboos_in_W199991
- **q028** (table, unverified, also: number, verification failed) - In Table 2, how many households in Kerabari strongly disbelieve in the superstitions and taboos?
  - answer: The provided text states that there were no households in the Terai who strongly disbelieved in superstitions and taboos against bamboo planting [1]. However, it does not provide a specific count or data point for how many households in Ker
- **q030** (table, verified) - How many households were surveyed in Kerabari, and how many in the Midhills?
  - answer: 41 households were interviewed in Kerabari, while 208 households were interviewed in the Midhills [3].  [3] 1970_Das_Beliefs_superstitions_and_taboos_associated_with_bamboos_in_W1999918290.pdf, p. 2: "Altogether, 199 households in the Terai
- **q038** (comparison, unverified, also: verification failed) - Which river has the lowest coefficient value among those listed by DHM/DPTC (1994)?
  - answer: The river with the lowest coefficient value is the Rapti River at Bhandara [2]. This specific value of 0.033 was reported by DHM/DPTC in their 1994 flood assessment report [2]. The other rivers listed had higher values, including Bagmati at
- **q039** (exact, unverified, also: number, verification failed) - What 24-hour and 48-hour rainfall depths does the paper use for the study area (P0)?
  - answer: The paper states that P0 is 54 [1]. The 24-hour rainfall depth of 540 mm at Tistung and 482 mm at Ghantemadi were recorded in morning hours of 20th July [2]. These specific values differ from the P0 value used in the depth-area-duration equ
- **q044** (fact, unverified, also: verification failed) - What was bamboo planting associated with among some villagers in the Kakani-Kathmandu area?
  - answer: Among some villagers in the Kakani-Kathmandu area, bamboo planting was associated with childlessness [1]. This belief led to an unwillingness to plant bamboo within that specific region [2]. The superstition suggested that if individuals li
- **q048** (fact, unverified, also: verification failed) - Who may plant bamboo if there are no males over 60 years old in the house?
  - answer: If there are no males over 60 years old in the house, bamboo planting can be carried out by a middle-aged man [1]. In the absence of old age members, it may also be performed by middle-aged household heads or members aged 40 years or over [
- **q049** (fact, verified) - If a household has no elderly members, what age qualifies a member to plant bamboo?
  - answer: If there are no old males over 60 years in the house, a middle-aged man aged 40 years or over can carry out bamboo planting [2]. Some households also mentioned that women can plant if they have children, are old, or lack middle-aged or old 

## number (2)

- **q029** (table, verified) - In the Terai table on belief and growing status, how many growers believe that superstition discourages bamboo planting?
  - answer: In the Terai table, 68.33% of bamboo growers believe in superstitions and taboos that discourage bamboo planting [1]. This figure is derived from the row labeled "Grower" under the column "% of Column Believe" for the Terai region [1]. The 
- **q042** (fact, verified) - How many bamboo species are recorded in Nepal, and in which publication?
  - answer: Fifty species of bamboos are already recorded in Nepal [1]. This information comes from Das (2004) as cited in passage [1].  [1] 1970_Das_Beliefs_superstitions_and_taboos_associated_with_bamboos_in_W1999918290.pdf, p. 1: "Fifty species of b

## false not found (2)

- **q026** (table, not_found, also: citation, number) - In Table 2, how many Midhills households do not believe in the superstitions and taboos against bamboo planting?
  - answer: Not found in the indexed documents.
- **q036** (list, not_found, also: citation, number) - In which years does the paper list floods in the Sunkosi River?
  - answer: Not found in the indexed documents.

## answered an unanswerable question (3)

- **q020** (notfound, verified) - What is the population living in the Bagmati catchment?
  - answer: The provided passages do not state the total population living in the Bagmati catchment. They mention that data collection started in the sixties [1] and describe the physiographical features of the 1845 km² area [1], but no specific popula
- **q021** (notfound, unverified, also: verification failed) - What was the total economic loss caused by the July 1993 floods?
  - answer: The provided passages do not state the total economic loss caused by the July 1993 floods. Not found in the indexed documents.
- **q055** (notfound, verified) - What is the elevation of the Tistung rainfall station in metres?
  - answer: The provided passages do not state the specific elevation of the Tistung rainfall station in metres. Passage [1] mentions hourly rainfall intensities at Tistung but does not include its altitude. Passage [2] notes a station at 3920 masl but
