# Known limitations

## Scientific and dataset
1. **No Type-1-specific detection.** The diabetes model is trained on labels that do not state the diabetes type,
   in an adult population. It is a general diabetes symptom screen. On 85 known T1D children (exploratory check)
   it flagged only 41-60% as positive.
2. **Not early detection.** Both datasets are retrospective and cross-sectional. The models classify the
   present profile; they do not forecast future disease.
3. **Small data.** 251 unique diabetes records (51 for testing) and 918 heart records (184 for testing). Test
   metrics have wide confidence intervals.
4. **Duplicates.** Half of the public diabetes file is exact duplicates. Results published elsewhere on this
   dataset without de-duplication are not comparable to ours.
5. **Sampling bias.** In the diabetes data 90% of women but 45% of men are positive, so the model scores women
   higher for the same symptoms.
6. **Heart grades are hard to separate.** Macro F1 about 0.39 over five grades; grade 4 is rarely recognised. The
   binary "any disease" view is much more reliable (ROC-AUC 0.90 on the test set).
7. **Site effects.** Missing values and disease prevalence differ by hospital; leave-one-site-out performance is
   clearly lower than the random-split figures.
8. **Old, specific populations.** The heart data was collected in 1980s USA/Hungary/Switzerland; the diabetes data
   in Bangladesh. Neither represents Pakistani adults or children specifically.
9. **Inputs need clinical tests.** The heart model needs exercise-test results most users won't have.

## Modelling
10. **The hybrid is not better than the Random Forest** on these data (CV results are equivalent; single test
    splits slightly favour the RF). It is deployed because the proposal specifies it.
11. ANN implemented with scikit-learn's MLP rather than TensorFlow/Keras.
12. Probabilities are not post-hoc calibrated; calibration was only measured on small test sets.
13. Risk bands (30% / 70%) are design choices, not clinically derived thresholds.

## Explainability
14. SHAP explains model behaviour, not causes; the Independent masker can create unrealistic feature
    combinations; results depend on the 50-row background sample.

## Technical
15. SQLite, single process; in-memory rate limiting; no migrations.
16. SHAP adds about 0.5 s per prediction; heavy concurrent use would need a worker queue.
17. PDF uses a Latin-1 font.
18. Built and tested on Linux. Your Windows/macOS machine could not be reached during the build, so the
    installation instructions for it were not executed there.

## Security and operations
19. No HTTPS, MFA, email verification, password reset or audit log. Token in sessionStorage. Database not
    encrypted at rest. (SECURITY_AND_PRIVACY.md)
20. Real SMTP delivery not tested (no credentials available); simulated server and failure paths tested.

## Clinical
21. **Not clinically validated, not a medical device.** No clinician reviewed the recommendation rules. The
    app must only be used for education and demonstration.
