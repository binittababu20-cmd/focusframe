
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib

# Demo dataset — artificial sample data, not real student data
data = pd.DataFrame({
    "duration_seconds": [
         5,  10,  10, 120,  25,  20,  65,
       150,  90,  45,  30,  20,  45,  15,
        30,  35, 250, 110, 220, 300,  60,
        90, 140, 120,  80,  75, 200, 100
    ],
    "non_educational": [
        1, 1, 0, 0, 1, 1, 1,
        0, 0, 0, 1, 0, 1, 0,
        0, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1
    ],
    # 0 = focused, 1 = potentially distracted
    "label": [
        0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0,
        0, 0, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1
    ]
})

X = data[["duration_seconds", "non_educational"]]
y = data["label"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

model = RandomForestClassifier(
    n_estimators=100,
    random_state=42,
    class_weight="balanced"
)

model.fit(X_train, y_train)
predictions = model.predict(X_test)

print("Demo model trained successfully!")
print("Demo accuracy:", round(accuracy_score(y_test, predictions), 2))
print(classification_report(y_test, predictions, zero_division=0))

joblib.dump(model, "focus_model_demo.joblib")
print("Model saved successfully!")
print("NOTE: This model uses artificial demo data.")

