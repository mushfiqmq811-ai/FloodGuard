from pathlib import Path
import joblib
import numpy as np

MODEL_PATH = Path("model/flood_model.joblib")

def _fallback_prediction(hyd, weather, danger):
    current = hyd["water_level"]
    slope_24h = current - hyd["water_level_24h_ago"]
    rain_effect = min(weather["rain_next_24h_mm"] / 500.0, 0.35)
    upstream_effect = min(max(hyd["upstream_change"], 0) * 0.5, 0.25)
    predicted = current + slope_24h + rain_effect + upstream_effect
    probability = 1 / (1 + np.exp(-(predicted - danger) * 3.0))
    return predicted, float(np.clip(probability, 0.02, 0.98)), "Trend + rainfall fallback"

def predict_flood(hyd, weather, danger):
    x = np.array([[
        hyd["water_level"], hyd["water_level_6h_ago"],
        hyd["water_level_12h_ago"], hyd["water_level_24h_ago"],
        weather["rain_now_mm"], weather["rain_next_24h_mm"],
        hyd["upstream_level"], hyd["upstream_change"],
        weather["temperature_c"] if weather["temperature_c"] is not None else 28.0
    ]], dtype=float)

    if MODEL_PATH.exists():
        try:
            model = joblib.load(MODEL_PATH)
            predicted = float(model.predict(x)[0])
            probability = float(np.clip(1 / (1 + np.exp(-(predicted-danger)*3)), 0.01, 0.99))
            method = "Trained Random Forest"
        except Exception:
            predicted, probability, method = _fallback_prediction(hyd, weather, danger)
    else:
        predicted, probability, method = _fallback_prediction(hyd, weather, danger)

    if predicted >= danger + 1.0:
        risk = "SEVERE"
    elif predicted >= danger:
        risk = "FLOOD"
    elif predicted >= danger - 0.5:
        risk = "WARNING"
    else:
        risk = "NORMAL"

    from datetime import datetime, timezone
    return {
        "predicted_water_level_24h": round(predicted, 2),
        "flood_probability": round(probability * 100, 1),
        "risk": risk,
        "model": method,
        "danger_level": danger,
        "generated_at_utc": datetime.now(timezone.utc).isoformat()
    }
