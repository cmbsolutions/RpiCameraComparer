import tensorflow as tf
from tensorflow.keras import layers, models
import os
from pathlib import Path

BASE = Path(__file__).parent.resolve()
DATA_DIR = BASE / "TrainingSet7/"
print(f"Using data directory: {DATA_DIR}")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 1) Create a tf.data.Dataset from your folder structure
dataset = tf.keras.preprocessing.image_dataset_from_directory(
    DATA_DIR,
    labels="inferred",
    label_mode="int",
    color_mode="grayscale",
    batch_size=64,
    image_size=(64,64),
    shuffle=True,
    seed=32,
)

# 2) Normalize & cache/prefetch
dataset = dataset.map(lambda x,y: ((x/255.0), y)).cache().prefetch(1)

# 3) Split train/val
val_batches = dataset.take(200//64)   # ~200 images
train_batches = dataset.skip(200//64)

# 4) Define a small CNN
model = models.Sequential([
    layers.Input((64,64,1)),
    layers.Conv2D(64, 3, activation="relu"),
    layers.MaxPool2D(),
    layers.Conv2D(64, 3, activation="relu"),
    layers.MaxPool2D(),
    layers.Flatten(),
    layers.Dense(128, activation="relu"),
    layers.Dense(10, activation="softmax"),
])

model.compile(
    optimizer="adam",
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"]
)

# 5) Train
history = model.fit(
    train_batches,
    epochs=10,
    validation_data=val_batches
)

# 6) Save your model
model.save(BASE / "digit_cnn_model7.keras")