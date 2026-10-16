# Final recommendations

Ordered by priority within each area. "P1" items matter most for the project's credibility at evaluation.

## Scope and data (P1)
1. **Agree the Type-1 reframing with the supervisor now.** The proposal title promises T1D early detection; the
   available data cannot support it. Either retitle to "diabetes symptom screening", or obtain data with
   confirmed T1D cases *and* non-diabetic controls of similar age (for example a case-control set from a
   paediatric clinic, with ethics approval and consent).
2. **Handle the local T1D spreadsheet properly.** It contains names, phone numbers and addresses of children.
   Store the original securely, confirm consent/ethics approval, and only work with the de-identified version.
3. If more data is collected, record the 14 screening symptoms in the same form so the cohort can be used as a
   proper external test set.
4. Heart: consider presenting the binary "any disease" model as the main result and the grade as secondary
   (the app already does this), or merging grades 2-4, which would be easier to defend.

## Model reliability
5. Report CV results as the primary comparison (less noisy than one small test split) and state clearly that
   the hybrid does not outperform the RF on these data. A negative result, honestly explained, is a valid finding.
6. Try nested cross-validation for the whole pipeline to get unbiased estimates without a separate test split.
7. Add post-hoc calibration (isotonic or Platt) inside a CV loop and compare Brier/ECE.
8. Remove or test the effect of the `sex` feature in the diabetes model (fairness analysis) and report it.
9. Add a Keras ANN as an optional component if the proposal's TensorFlow requirement must be met literally,
   keeping it inside a scikit-learn-compatible wrapper so stacking stays leakage-safe.
10. Use site-aware validation (grouped CV by hospital) for the heart model.

## Explainability
11. Compare SHAP results across two or three background samples and report stability.
12. Add a "what if" panel (change one input and see the new probability), which users usually find clearer than
    attribution bars.
13. Run a small user study (proposal section 6) on whether people understand the ledger view.

## Usability
14. Add plain-language help for clinical heart inputs, or a simplified heart screen based on questionnaire data
    for the general public.
15. Add Urdu translations of the interface and the PDF.

## Privacy and security (before any real users)
16. Serve over HTTPS behind a reverse proxy; move the token to an HttpOnly, SameSite cookie with CSRF protection.
17. Email verification and password reset; optional MFA.
18. Encrypt the database at rest; add an access audit log.
19. Shared rate limiting (Redis) if running more than one process.
20. Clinical review of every recommendation rule.

## Maintainability and testing
21. Add Alembic migrations.
22. Run `scripts/run_all_tests` in CI on every change (the project has no version control by request; if that
    changes, CI becomes easy to add).
23. Add load testing for concurrent predictions; move SHAP to a background worker if needed.
24. Pin and periodically re-run `pip-audit` and `npm audit`.

## Future research
25. Longitudinal data for genuine early detection (predicting onset), e.g. islet autoantibody cohorts for T1D.
26. CGM data (e.g. DiaData) for a different, T1D-specific task such as hypoglycaemia prediction.
27. External validation on a local Pakistani cohort for the heart model.
