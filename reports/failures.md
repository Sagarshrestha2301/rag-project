# Remaining failures, grouped by cause (Step 9 task 1)

Source run: `eval/runs/2026-11-20-step9-retry-guard`. Written by `python eval/failures.py`;
the causes are the rules `eval/score.py` applied, not a reading of the answers.

| Cause | Questions |
|---|---|
| retrieval miss | 3 |
| citation | 9 |
| number | 2 |
| false not found | 1 |
| answered an unanswerable question | 3 |
| **total failing** | **18** |

## retrieval miss (3)

- **q015** (summary, not_found, also: false not found, citation) - What does the paper recommend about where equations (1) to (4) may be applied?
  - answer: Not found in the indexed documents.
- **q045** (number, verified, also: citation, number) - What share of households in the Terai believes in taboos and superstitions about bamboo?
  - answer: In the Terai, 31.67% of nongrower households believe in taboos and superstitions that discourage bamboo planting [3]. Additionally, 48.92% of grower households in the same region hold these beliefs [3]. The study notes that the level of bel
- **q046** (table, verified) - In the Terai, what percentage of households said bamboo reduces the productivity of the land?
  - answer: In the Terai, 91.46% of households believed that bamboo reduces the productivity of the land [6]. This belief was also strongly held by 61.9% of households in the Terai who generally believe in taboos and superstitions associated with bambo

## citation (9)

- **q017** (comparison, verified) - Compare the 24-hour rainfall at Tistung and at Ghantemadi.
  - answer: The 24-hour rainfall depth recorded at Tistung was 540 mm, while the depth at Ghantemadi was 482 mm [1]. These figures were observed during the morning hours of July 20th, 1993 [1]. The data comes from a study on extreme floods in south cen
- **q026** (table, unverified, also: number, verification failed) - In Table 2, how many Midhills households do not believe in the superstitions and taboos against bamboo planting?
  - answer: The provided passages do not contain a Table 2 with specific household counts for beliefs in the Midhills; they only present statistical data in Appendices 1, 2, and 3. [3] 1970_Das_Beliefs_superstitions_and_taboos_associated_with_bamboos_i
- **q027** (table, unverified, also: number, verification failed) - In Table 2, how many Terai households strongly believe in the superstitions and taboos against bamboo planting?
  - answer: The provided passages do not contain a specific figure for the number of Terai households who *strongly* believe in superstitions against bamboo planting; they only provide percentages of households that *believe* (69.85%) or *do not believ
- **q028** (table, unverified, also: verification failed) - In Table 2, how many households in Kerabari strongly disbelieve in the superstitions and taboos?
  - answer: The provided passages do not contain a specific figure or sentence stating the exact number of households in Kerabari who strongly disbelieve in the superstitions and taboos. [3] The text mentions that "There were no households in the Terai
- **q030** (table, verified) - How many households were surveyed in Kerabari, and how many in the Midhills?
  - answer: 41 households were interviewed in Kerabari, while 208 households were interviewed in the Midhills [3].  [3] 1970_Das_Beliefs_superstitions_and_taboos_associated_with_bamboos_in_W1999918290.pdf, p. 2: "Altogether, 199 households in the Terai
- **q039** (exact, unverified, also: verification failed) - What 24-hour and 48-hour rainfall depths does the paper use for the study area (P0)?
  - answer: The paper states that P0 is 54 mm for the study area [1]. However, Passage [2] records a 24-hour rainfall depth of 540 mm at Tistung and a 48-hour rainfall depth of 600 mm at Ghantemadi during July 1993.  [1] 1970_Marahatta_Relating_Hydrolo
- **q048** (fact, verified) - Who may plant bamboo if there are no males over 60 years old in the house?
  - answer: If there are no males over 60 years old in the house, bamboo planting can be carried out by a middle-aged man [1]. In the absence of old age members in the family, it can be carried out by the middle-aged household heads or members aged 40 
- **q049** (fact, verified) - If a household has no elderly members, what age qualifies a member to plant bamboo?
  - answer: If a household lacks elderly members over 60 years of age, a middle-aged man aged 40 or older may carry out bamboo planting [2]. This exception applies when there are no old males present in the house [1]. The belief that only the oldest ma
- **q051** (fact, verified) - According to some households in the Midhills, at what age should males harvest new bamboo shoots?
  - answer: Some households in the Midhills believe that only males over 50 years of age should carry out the harvesting of new bamboo shoots [1]. This belief is part of a broader set of superstitions where older men are preferred for tasks involving b

## number (2)

- **q029** (table, verified) - In the Terai table on belief and growing status, how many growers believe that superstition discourages bamboo planting?
  - answer: In the Terai table, 68.33% of bamboo growers believe in superstitions and taboos that discourage bamboo planting [1]. This figure is derived from the row labeled "Grower" under the column "% of Column Believe" for the Terai region [1]. The 
- **q042** (fact, verified) - How many bamboo species are recorded in Nepal, and in which publication?
  - answer: Fifty species of bamboos are already recorded in Nepal [1]. This information comes from Das (2004) as cited in the 1970 document.  [1] 1970_Das_Beliefs_superstitions_and_taboos_associated_with_bamboos_in_W1999918290.pdf, p. 1: "Fifty specie

## false not found (1)

- **q036** (list, not_found, also: citation, number) - In which years does the paper list floods in the Sunkosi River?
  - answer: Not found in the indexed documents.

## answered an unanswerable question (3)

- **q020** (notfound, verified) - What is the population living in the Bagmati catchment?
  - answer: The provided passages do not contain information about the total population living in the Bagmati catchment. They only mention that the areal coverage of the physiographical feature of the Bagmati River favoring severe flooding is approxima
- **q021** (notfound, unverified, also: verification failed) - What was the total economic loss caused by the July 1993 floods?
  - answer: The provided passages do not state the total economic loss caused specifically by the July 1993 floods. Not found in the indexed documents.
- **q055** (notfound, unverified, also: verification failed) - What is the elevation of the Tistung rainfall station in metres?
  - answer: The provided passages do not state the elevation of the Tistung rainfall station.  Not found in the indexed documents.
