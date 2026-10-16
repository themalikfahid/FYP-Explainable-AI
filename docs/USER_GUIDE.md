# User guide

Clarity Screen is a learning and screening tool. It estimates, from your answers, how similar your profile is
to people with diabetes or heart disease in two public research datasets, and it shows why. **It does not
diagnose anything.** If you feel unwell, contact a doctor. For chest pain at rest, or severe symptoms, call
emergency services.

## 1. Create an account and log in
1. Open the app (usually http://127.0.0.1:8000) and choose **Create account**.
2. Enter your name, email and a password of at least 8 characters with a letter and a number.
3. Log in. Your session lasts 60 minutes and ends when you close the browser tab or press **Log out**.

## 2. Dashboard
Start either assessment, see your last results and a small chart of your risk scores over time (dashed lines mark
the 30% and 70% bands), or open the BMI and lifestyle calculator.

## 3. Diabetes symptom screen
* Enter age and sex, then answer each symptom with **Yes** or **No**. "Set all symptoms to No" is a shortcut;
  then switch on the ones you have.
* This screen was trained on adults (16-90) and **does not tell type 1 from type 2 diabetes**. Only a blood test
  can confirm diabetes.

## 4. Heart assessment
Uses results from a clinical exam and an exercise stress test (resting blood pressure, cholesterol, ECG, maximum
heart rate, ST depression). Cholesterol, ST slope, fluoroscopy vessels and thallium test are optional: choose
"Not known" if you don't have them. The result will then warn that it is less reliable. If you don't have
exercise-test results, this assessment is not meaningful for you.

## 5. Lifestyle details (optional)
Height, weight, sleep, weekly activity, fruit and vegetables, smoking and alcohol. They are **not** used by the
prediction. They give you a BMI, a 0-100 lifestyle score and more specific suggestions.

## 6. Reading your result
* **Risk level and score.** Diabetes: the estimated probability of a positive screen. Heart: the estimated
  probability of any heart disease (grades 1-4). Low is below 30%, moderate 30-70%, high 70% and above.
* **Most likely class.** For heart, the grade (0-4) with the highest probability. Grades often have similar
  probabilities; the page warns you when none is clearly favoured. Focus on the overall score.
* **Warnings.** Shown when inputs were missing, outside the data the model learned from, or when the two
  component models disagree.
* **Probabilities table.** The final (hybrid) estimate and the two models it combines (Random Forest and
  neural network). These are model estimates, not your personal medical risk.

## 7. Understanding "Why the model said this" (SHAP)
The list starts from the **average** probability across a reference group and shows how each of your answers
moved it, ending at **your** probability. Red bars pushed the probability up; green bars pushed it down; the
number is the change in percentage points. Use the **Explain** menu to look at another class (for heart, "Any
heart disease" or a specific grade).
This shows how the model used your answers. It does **not** prove that a factor causes disease. For example, the
diabetes model gives women a higher score for the same symptoms because of how its dataset was collected.

## 8. Recommendations
Grouped into follow-up, lowering your risk, diet, activity and sleep, most important first. Each one names the
guideline it is based on. They are general advice; no medicines or doses are suggested.

## 9. BMI and lifestyle calculator
Menu: **BMI & lifestyle**. Works without an account and saves nothing. You can use the WHO cut-offs for Asian
populations (23 and 27.5), which flag risk at a lower BMI. BMI is a rough adult measure and does not account for
muscle mass.

## 10. History
Menu: **History**. Filter by assessment type, open a result, download its PDF or delete it. Deleting cannot be
undone.

## 11. PDF report
On a result press **Download PDF report**. It contains your inputs, the result, probabilities, the SHAP chart,
recommendations, BMI/lifestyle score, model information and the disclaimer. You can take it to a doctor.

## 12. Email alerts
If an assessment is high risk, the app can email you a short note asking you to sign in. The email contains no
results. Turn it on or off under **Account**. Whether emails are actually sent depends on how the app's owner set
it up; the result page tells you what happened.

## 13. Account settings
Change your name, password (you'll be logged out), alert preference, or permanently delete your account and all
saved assessments.
