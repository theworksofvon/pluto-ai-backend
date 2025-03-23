import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    mean_squared_error,
    mean_absolute_error,
    r2_score,
    log_loss,
    accuracy_score,
)

# import matplotlib.pyplot as plt
from sklearn.preprocessing import OneHotEncoder
import joblib

# --- STEP 1: Load the PLUTO TRAINING Dataset ---

pluto_training_data = pd.read_csv("shared/data/pluto_training_dataset_v1.csv")

# --- STEP 2: Inspect and Clean Data ---
print(pluto_training_data.info())
print(pluto_training_data.describe())
print(pluto_training_data.isnull().sum())

# Drop irrelevant columns
pluto_training_data = pluto_training_data.drop(
    columns=["Game_ID", "GAME_DATE", "MATCHUP", "WL"], errors="ignore"
)

# Fill missing values with 0
pluto_training_data = pluto_training_data.fillna(0)

# --- STEP 3: Select Features and Target ---

# Features are input variables that the model use to make predictions
# They provide the context or evidence for the model to learn patterns and relationships

X = pluto_training_data.drop(columns=["PTS"])
y = pluto_training_data["PTS"]


numeric_cols = [
    "home_away_flag",
    "rolling_pts_5",
    "rolling_min_5",
    "rolling_fga_5",
    "rolling_fg_pct_5",
    "days_since_last_game",
    "back_to_back_flag",
]
categorical_cols = ["player_name", "opponent", "game_date_parsed"]

ohe = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
ohe_data = ohe.fit_transform(X[categorical_cols])

cat_df = pd.DataFrame(
    ohe_data, columns=ohe.get_feature_names_out(categorical_cols), index=X.index
)


X_enc = pd.concat([X[numeric_cols], cat_df], axis=1)

# --- STEP 4: Preprocess Features ---
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_enc)

# --- STEP 5: Split Data ---
# 80/20 split, 80% training 20% testing
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42
)

# --- STEP 6: Train Linear Regression Model ---
model = LinearRegression()
model.fit(X_train, y_train)

# --- STEP 7: Make Predictions ---
# Predicted values of target variable based on features
predictions = model.predict(X_test)

# --- STEP 8: Evaluate Performance of Model ---
# Regression Metrics
mse = mean_squared_error(y_test, predictions)
mae = mean_absolute_error(y_test, predictions)
r2 = r2_score(y_test, predictions)
intercept = model.intercept_
print(
    f"MSE: {mse}"
)  # averaged squared distance between the predicted and actual values. lower is better
print(f"MAE: {mae}")  # averaged absolute distance "" ""  """ """" "
print(f"R^2 SCORE: {r2}")  # how well the model fits the data, Higher is better
print(
    f"Model Intercept: {intercept}"
)  # Starting point of regression line on y-axis. Value of (target) when (features) are 0
# if positive target increases as features increase, if negative then the opposite

# # --- STEP 9: Visualize Predictions ---
# plt.scatter(y_test, predictions, alpha=0.5)
# plt.plot([y.min(), y.max()], [y.min(), y.max()], color="red")
# plt.xlabel("Actual Points")
# plt.ylabel("Predicted Points")
# plt.title("Actual vs Predicted Points")
# plt.savefig("actual_vs_predicted_pts.png")
# plt.show()

## --- STEP 10: Plot Residuals
# residuals = y_test - predictions

# Plot residuals vs. predicted values:
# plt.scatter(predictions, residuals, alpha=0.5)
# plt.axhline(y=0, color='red', linestyle='--')  # horizontal line at residual=0
# plt.xlabel("Predicted Points")
# plt.ylabel("Residual (Actual - Predicted)")
# plt.title("Residuals vs. Predicted Points")
# plt.savefig("residuals_vs_predicted_pts.png")
# plt.show()

# # --- STEP 11: Save Model and Scaler ---
joblib.dump(model, "ai_models/pluto_linear_model.pkl")
joblib.dump(scaler, "ai_models/pluto_scaler.pkl")
joblib.dump(ohe, "ai_models/pluto_points_encoder.pkl")
