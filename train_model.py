from pathlib import Path
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

FEATURES = [
    "water_level", "water_level_6h_ago", "water_level_12h_ago",
    "water_level_24h_ago", "rain_6h", "rain_24h",
    "upstream_level", "upstream_change", "temperature"
]
TARGET = "target_water_level_24h"

df = pd.read_csv("data/training_data.csv").dropna()
X, y = df[FEATURES], df[TARGET]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestRegressor(
    n_estimators=400, max_depth=14, min_samples_leaf=2,
    random_state=42, n_jobs=-1
)
model.fit(X_train, y_train)

pred = model.predict(X_test)
print("MAE:", round(mean_absolute_error(y_test, pred), 4))
print("R2 :", round(r2_score(y_test, pred), 4))

Path("model").mkdir(exist_ok=True)
joblib.dump(model, "model/flood_model.joblib")
print("Saved model/flood_model.joblib")
