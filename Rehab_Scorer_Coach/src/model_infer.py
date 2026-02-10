import numpy as np
import joblib
import tensorflow as tf
from tensorflow.keras import layers, Sequential

# Must match your training definition exactly
class TransformerBlock(layers.Layer):
    def __init__(self, d_model=128, num_heads=4, ff_dim=256, dropout=0.1, **kwargs):
        super().__init__(**kwargs)
        self.att = layers.MultiHeadAttention(num_heads=num_heads, key_dim=d_model // num_heads)
        self.ffn = Sequential([
            layers.Dense(ff_dim, activation="relu"),
            layers.Dense(d_model),
        ])
        self.layernorm1 = layers.LayerNormalization(epsilon=1e-6)
        self.layernorm2 = layers.LayerNormalization(epsilon=1e-6)
        self.drop1 = layers.Dropout(dropout)
        self.drop2 = layers.Dropout(dropout)

    def call(self, x, training=False):
        attn = self.att(x, x, training=training)
        x = self.layernorm1(x + self.drop1(attn, training=training))
        ffn = self.ffn(x, training=training)
        return self.layernorm2(x + self.drop2(ffn, training=training))

class ScoreModel:
    """
    Workaround loader:
      - model outputs internal scalar pred_z (whatever it learned)
      - x_scaler.pkl is recreated and saved
      - y_map.pkl contains {"a":..., "b":...} where y = a*pred_z + b
    Returns score clamped to [0,50].
    """
    def __init__(self, keras_path: str, x_scaler_path: str, y_map_path: str):
        self.model = tf.keras.models.load_model(
            keras_path,
            custom_objects={"TransformerBlock": TransformerBlock}
        )
        self.x_scaler = joblib.load(x_scaler_path)

        y_map = joblib.load(y_map_path)
        self.a = float(y_map["a"])
        self.b = float(y_map["b"])

    def predict_score_0_50(self, X_seq_1: np.ndarray) -> float:
        """
        X_seq_1: (1, T, F) raw feature sequence (NOT scaled).
        """
        assert X_seq_1.ndim == 3 and X_seq_1.shape[0] == 1, "Expected (1,T,F)"
        T = X_seq_1.shape[1]
        F = X_seq_1.shape[2]

        X_scaled = self.x_scaler.transform(X_seq_1.reshape(-1, F)).reshape(1, T, F)
        pred_z = self.model.predict(X_scaled, verbose=0).reshape(-1)[0]

        y_hat = self.a * float(pred_z) + self.b # +  15.0
        return float(np.clip(y_hat, 0.0, 50.0))