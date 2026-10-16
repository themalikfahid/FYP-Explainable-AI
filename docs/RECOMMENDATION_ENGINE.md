# Recommendation engine, BMI and lifestyle score

Code: `backend/app/services/recommend.py` (rules) and `backend/app/services/scoring.py` (BMI, lifestyle score).
Tests: `tests/unit/test_scoring_and_recommend.py`.

## Principles

* Rule-based and fully listed below, so every suggestion can be traced to an input and a guideline.
* General lifestyle and follow-up guidance only. **No medicines, doses, or diagnostic statements.** A test
  checks that no recommendation text mentions medication or dosing terms.
* Every recommendation carries `category`, `priority` (high/medium/low), `text`, the `rule` that fired, and a
  `source`. Items are sorted high -> low priority.
* The same disclaimer is attached to every result and PDF: educational screening and decision-support
  prototype, not a diagnosis or substitute for a professional.

## Scoring

### BMI (`bmi()`)
BMI = weight (kg) / height (m)^2, rounded to one decimal, and the category is taken from the rounded value
(so a value shown as 30.0 is never labelled "Overweight").

| Cut-offs | Underweight | Healthy | Overweight / increased risk | Obesity / high risk |
|---|---|---|---|---|
| WHO adult (default) | < 18.5 | 18.5-24.9 | 25.0-29.9 | >= 30 |
| WHO Expert Consultation for Asian populations (Lancet 2004), optional | < 18.5 | 18.5-22.9 | 23.0-27.4 | >= 27.5 |

The response also gives the healthy-weight range for the person's height and a note that BMI is an adult
screening measure, does not measure body fat, and is not a complete health assessment.

### Lifestyle score (`lifestyle_score()`), 0-100

| Component (max) | Points | Guideline basis |
|---|---|---|
| Physical activity (25) | >= 150 min/week: 25; 75-149: 15; 1-74: 7; 0: 0 | WHO 2020: 150-300 min/week moderate activity |
| Sleep (20) | 7-9 h: 20; 6-<7 or >9-10 h: 12; otherwise 5 | AASM/SRS consensus 2015: adults >= 7 h |
| Fruit and vegetables (20) | >= 5 servings/day: 20; 3-4.9: 12; 1-2.9: 6; 0: 0 | WHO: >= 400 g/day (about 5 servings) |
| Smoking (20) | never 20; former 14; current 0 | WHO tobacco guidance |
| Alcohol (15) | 0 units: 15; <= 14 units/week: 10; > 14: 0 | UK Chief Medical Officers 2016 low-risk guideline |

Bands: **Good** >= 80, **Fair** 60-79, **Needs improvement** < 60.

The weights (25/20/20/20/15) are a design choice for this prototype. The score is educational, has not been
validated against outcomes, and is **not used by the machine-learning models**.

## Rules

### Diabetes screen
| Rule | Priority | Recommendation (summary) | Source |
|---|---|---|---|
| risk = high | high | See a doctor soon for a blood glucose test (fasting glucose or HbA1c); only a lab test confirms or rules out diabetes | ADA Standards of Care |
| risk = moderate | medium | Consider a routine glucose test, especially if symptoms persist | ADA |
| risk = low | low | No action suggested; repeat or see a doctor if new symptoms appear | ADA |
| polyuria AND polydipsia AND sudden weight loss | high | These together can signal new-onset diabetes including type 1; seek same-day care if with vomiting, abdominal pain, drowsiness, confusion or fast breathing | Diabetes UK "4Ts" |
| visual blurring OR delayed healing | medium | Mention to a doctor | ADA |
| always | medium | Limit sugary drinks; whole grains, pulses, vegetables, fruit; free sugars < 10% energy | WHO healthy diet |
| obesity = yes OR obesity in top positive SHAP features | medium | Gradual weight reduction with activity and portions | WHO physical activity |

### Heart assessment
| Rule | Priority | Recommendation (summary) | Source |
|---|---|---|---|
| risk = high / moderate / low | high / medium / low | Review with doctor or cardiologist soon / discuss at next visit / keep regular check-ups | ACC/AHA 2019 primary prevention |
| cp is typical or atypical angina OR exercise angina | high | Chest pain at rest, lasting minutes, or with breathlessness/sweating/nausea is an emergency: call emergency services | AHA heart attack warning signs |
| resting systolic BP >= 130 | medium | Re-measure on separate days; salt, activity, alcohol | ACC/AHA 2017 BP guideline |
| cholesterol >= 240 | medium | Full lipid profile and medical advice | NCEP ATP III |
| 200 <= cholesterol < 240 | low | Fewer fried/fatty foods, more fibre | NCEP ATP III |
| fasting blood sugar > 120 | medium | Follow up with a doctor | ADA |
| always | medium | Salt < 5 g/day, fewer saturated/trans fats, more plants and whole grains | WHO healthy diet |

### Lifestyle (only when lifestyle details are provided)
| Rule | Priority | Recommendation |
|---|---|---|
| activity < 150 min/week | medium | Build up to 150 min moderate activity + strength on 2 days |
| activity >= 150 | low | Keep it up, limit long sitting |
| sleep < 7 h | medium | Aim for >= 7 h, regular schedule, less late screen/caffeine |
| sleep > 9 h | low | Mention persistent tiredness to a doctor |
| 7-9 h | low | Sleep is in the recommended range |
| fruit/veg < 5 | medium | Add fruit or vegetables to each meal |
| current smoker | high | Stopping smoking; ask about support |
| alcohol > 14 units | medium | Keep to <= 14 units spread over days |
| BMI not "Healthy weight" | medium | BMI value, healthy range for height, discuss goals with a professional |
| no lifestyle given | low | Prompt to add lifestyle details |

## Limitations

* Rules are simple thresholds, not individualised clinical advice, and were not reviewed by a clinician for
  this prototype (recommended before any real use).
* Guideline sources are named but not quoted; thresholds follow commonly published values and may differ by
  country (for example national blood-pressure targets).
* Lifestyle inputs are self-reported and not verified.
