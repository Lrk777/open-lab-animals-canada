# Annotation guidelines: ARRIVE 2.0 + primate-welfare items

Label each paper's **methods text** (as stored in `data/raw/corpus/fulltext/<pmcid>.json`, or the
methods section of the published article) independently. Do not look at any model output until
your sheet is complete.

For every item, enter `TRUE` if the text **explicitly** reports it and `FALSE` otherwise. Paste the
shortest verbatim sentence that justifies a `TRUE` into `evidence`. Use `notes` for doubt.

## General rules

1. Only what is written counts. "Standard procedures" or "as described previously" is `FALSE`
   unless the relevant detail is given in this paper.
2. Supplementary material counts only if it is in the stored text.
3. If the paper uses several species, judge only the primate experiments.

## Item rules

| Item | TRUE when... | Not enough |
|---|---|---|
| sample_size | the number of monkeys is stated ("two monkeys", "monkey M and monkey P") | number of neurons or sessions only |
| sample_size_justification | a power analysis or an explicit rationale for the number of animals | "consistent with previous studies" without the number rationale |
| inclusion_exclusion | criteria for excluding animals, sessions, trials or neurons are stated | none |
| randomisation | random assignment/order of animals, conditions or trials | "pseudorandom" counts |
| blinding | experimenters or analysts were blind to condition | "blind spot" mapping |
| statistical_methods | named tests or models | "significance was assessed" with no test |
| animal_sex | sex of each animal or of the group | — |
| animal_age_or_weight | age or body weight | — |
| animal_source | supplier, breeding colony, or prior institution | — |
| housing_type | single, pair or group housing is stated | "housed according to guidelines" |
| enrichment | any enrichment described | — |
| fluid_or_food_control | the fluid/food regime is stated: controlled/restricted, or ad libitum (value records which) | juice reward alone is `FALSE` |
| fluid_control_detail | minimum volume, ml/kg, or weight/hydration monitoring | — |
| implant_described | head post, chamber, eye coil, array or craniotomy | — |
| surgery_count | number of surgeries per animal, or "in a single surgery" | — |
| anaesthesia_analgesia | anaesthetic and/or analgesic agents or regimen | "under anaesthesia" alone is `TRUE` for anaesthesia |
| welfare_monitoring_endpoints | monitoring, adverse events, humane endpoints | — |
| animal_reuse | animals' use in other studies is stated | — |
| animal_fate | euthanasia, perfusion, or retention at end of study | — |
| ethics_approval | approval by an animal care/ethics committee | — |
| ccac_guidelines | CCAC guidelines or an equivalent national guide | — |

## Process

1. `python -m olac.audit.gold sample --n 80` (once; fixed seed).
2. `python -m olac.audit.gold sheet --annotator A` and `--annotator B`.
3. Label independently; target 10-15 minutes per paper.
4. `python -m olac.audit.evaluate` writes kappa and `data/gold/disagreements.csv`.
5. Discuss disagreements, record final labels in `data/gold/labels_adjudicated.csv`
   (same columns), and re-run the evaluation.
