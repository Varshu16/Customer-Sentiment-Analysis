
from flask import Flask, request, jsonify, render_template
import joblib
import pandas as pd
import logging
import re
from pathlib import Path
from io import BytesIO
from nltk.corpus import stopwords


# --------------------------------------------------
# 1. Application Setup
# --------------------------------------------------

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "notebooks" / "sentiment_model.pkl"


# --------------------------------------------------
# 2. Load Trained Model
# --------------------------------------------------

model = joblib.load(MODEL_PATH)


# --------------------------------------------------
# 3. Configure Logging
# --------------------------------------------------

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# 4. Text Preprocessing
# --------------------------------------------------

# Load English stopwords and preserve negation words
stop_words = set(stopwords.words("english"))

negation_words = {"no", "nor", "not", "never"}
stop_words = stop_words - negation_words


def preprocess_review(text):

    # Convert text to lowercase
    text = text.lower()

    # Remove HTML tags
    text = re.sub(r'<.*?>', ' ', text)

    # Remove URLs
    text = re.sub(r'http\S+|www\S+', ' ', text)

    # Remove special characters and numbers
    text = re.sub(r'[^a-zA-Z\s]', ' ', text)

    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()

    # Tokenization
    tokens = text.split()

    # Remove stopwords while preserving negations
    filtered_tokens = [
        word for word in tokens if word not in stop_words
    ]

    # Join tokens into a single string
    processed_review = " ".join(filtered_tokens)

    return processed_review


# --------------------------------------------------
# 5. Home Page
# --------------------------------------------------

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


# --------------------------------------------------
# 6. Health Check
# --------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "model_loaded": model is not None
    })


# --------------------------------------------------
# 7. Single Review Prediction
# --------------------------------------------------

@app.route("/predict", methods=["POST"])
def predict():

    data = request.get_json(silent=True) or {}
    review = data.get("review")

    if not isinstance(review, str) or not review.strip():
        logger.warning("Invalid review received")
        return jsonify({
            "error": "Please provide valid review text"
        }), 400

    try:
        # Preprocess incoming review
        processed_review = preprocess_review(review)

        if not processed_review:
            return jsonify({
                "error": "Review contains no meaningful text"
            }), 400

        # Predict sentiment
        prediction = model.predict([processed_review])[0]

        logger.info(
            "Prediction completed: %s",
            prediction
        )

        return jsonify({
            "review": review,
            "predicted_sentiment": str(prediction)
        })

    except Exception:
        logger.exception("Single review prediction failed")

        return jsonify({
            "error": "Prediction failed"
        }), 500


# --------------------------------------------------
# 8. Upload Dataset and Preview Columns
# --------------------------------------------------

@app.route("/columns", methods=["POST"])
def get_columns():

    if "file" not in request.files:
        return jsonify({
            "error": "Please upload a file"
        }), 400

    file = request.files["file"]
    extension = Path(file.filename).suffix.lower()

    try:
        if extension == ".csv":
            df = pd.read_csv(file, nrows=5)

        elif extension == ".xlsx":
            df = pd.read_excel(
                file,
                engine="openpyxl",
                nrows=5
            )

        else:
            return jsonify({
                "error": "Only CSV and XLSX files are supported"
            }), 400

        if len(df.columns) == 0:
            return jsonify({
                "error": "No columns found"
            }), 400

        return jsonify({
            "columns": [str(c) for c in df.columns]
        })

    except Exception:
        logger.exception("Column preview failed")

        return jsonify({
            "error": "Could not read the uploaded file"
        }), 400


# --------------------------------------------------
# 9. Bulk Dataset Sentiment Analysis
# --------------------------------------------------

@app.route("/analyze", methods=["POST"])
def analyze():

    if "file" not in request.files:
        return jsonify({
            "error": "Please upload a CSV or Excel file"
        }), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({
            "error": "No file selected"
        }), 400

    extension = Path(file.filename).suffix.lower()

    try:
        # Read uploaded dataset
        if extension == ".csv":
            df = pd.read_csv(file)

        elif extension == ".xlsx":
            df = pd.read_excel(
                file,
                engine="openpyxl"
            )

        else:
            return jsonify({
                "error": "Only CSV and XLSX files are supported"
            }), 400

        if df.empty:
            return jsonify({
                "error": "The uploaded dataset is empty"
            }), 400

        # Get selected review column
        review_column = request.form.get("review_column")

        if review_column not in df.columns:
            return jsonify({
                "error": "Please select a valid review column"
            }), 400

        # Get selected analysis options
        options = request.form.getlist("options")

        if not options:
            return jsonify({
                "error": "Select at least one analysis option"
            }), 400

        # Extract reviews
        reviews = (
            df[review_column]
            .fillna("")
            .astype(str)
            .tolist()
        )

        # Identify non-empty reviews
        valid_positions = [
            i for i, review in enumerate(reviews)
            if review.strip()
        ]

        if not valid_positions:
            return jsonify({
                "error": "No non-empty reviews found"
            }), 400

        valid_reviews = [
            reviews[i] for i in valid_positions
        ]

        # Apply the same preprocessing used during training
        processed_reviews = [
            preprocess_review(review)
            for review in valid_reviews
        ]

        # Remove reviews that become empty after preprocessing
        non_empty_indices = [
            i for i, review in enumerate(processed_reviews)
            if review
        ]

        processed_reviews = [
            processed_reviews[i]
            for i in non_empty_indices
        ]

        valid_positions = [
            valid_positions[i]
            for i in non_empty_indices
        ]

        if not processed_reviews:
            return jsonify({
                "error": "No meaningful reviews found"
            }), 400

        # Predict sentiment for all valid reviews
        predictions = model.predict(processed_reviews)

        # Create result DataFrame
        result_df = df.iloc[valid_positions].copy()

        result_df["predicted_sentiment"] = [
            str(prediction) for prediction in predictions
        ]

        # Calculate sentiment counts
        counts = result_df["predicted_sentiment"].value_counts()

        results = {}

        # Total reviews
        if "total" in options:
            results["total"] = len(result_df)

        # Sentiment counts
        if "counts" in options:
            results["counts"] = {
                "Positive": int(counts.get("Positive", 0)),
                "Neutral": int(counts.get("Neutral", 0)),
                "Negative": int(counts.get("Negative", 0))
            }

        # Donut chart data
        if "chart" in options:
            results["chart"] = {
                "Positive": int(counts.get("Positive", 0)),
                "Neutral": int(counts.get("Neutral", 0)),
                "Negative": int(counts.get("Negative", 0))
            }

        # Optional table output (if requested)
        if "table" in options:
            results["table"] = (
                result_df.head(500)
                .fillna("")
                .to_dict(orient="records")
            )

            results["table_note"] = (
                "Showing the first 500 rows."
                if len(result_df) > 500 else ""
            )

        # Optional CSV download (if requested)
        if "download" in options:
            csv_buffer = BytesIO()

            result_df.to_csv(
                csv_buffer,
                index=False,
                encoding="utf-8-sig"
            )

            results["download_csv"] = (
                csv_buffer.getvalue().decode("utf-8-sig")
            )

        # Log dataset analysis
        logger.info(
            "Dataset analyzed: %s reviews, %s predictions",
            len(result_df),
            len(predictions)
        )

        return jsonify(results)

    except Exception:
        logger.exception("Dataset analysis failed")

        return jsonify({
            "error": "Could not process the dataset. Check its format and contents."
        }), 400


# --------------------------------------------------
# 10. Run Application
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
