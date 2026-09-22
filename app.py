from flask import Flask, render_template, request, redirect, url_for, session
from models import db, User, Prediction, AudioFile, PredictionResult, AudioObject
from sqlalchemy import func
import os
from argon2 import PasswordHasher
from minio import Minio
import hashlib
import uuid
from ml.predictor import predict_file
from argon2.exceptions import VerifyMismatchError
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

minio_client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False
)


@app.route("/")
def login_page():
    return render_template("login.html")
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("index.html")
@app.route("/prediction")
def prediction():
    if "user_id" not in session:
        return redirect(url_for("login"))

    prediction_id = request.args.get("prediction_id", type=int)

    if not prediction_id:
        return redirect(url_for("home"))

    result = (
        db.session.query(
            Prediction,
            AudioFile,
            PredictionResult
        )
        .join(
            AudioFile,
            Prediction.audio_file_id == AudioFile.id
        )
        .join(
            PredictionResult,
            Prediction.prediction_result_id == PredictionResult.id
        )
        .filter(
            Prediction.id == prediction_id,
            Prediction.user_id == session["user_id"]
        )
        .first()
    )

    if not result:
        return "Prediction not found", 404

    prediction_record, audio_file, prediction_result = result

    return render_template(
        "prediction.html",
        prediction=prediction_record,
        audio_file=audio_file,
        prediction_result=prediction_result
    )
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    predictions = (
        db.session.query(Prediction, AudioFile, PredictionResult)
        .join(
            AudioFile,
            Prediction.audio_file_id == AudioFile.id
        )
        .join(
            PredictionResult,
            Prediction.prediction_result_id == PredictionResult.id
        )
        .filter(
            Prediction.user_id == session["user_id"]
        )
        .order_by(
            Prediction.created_at.desc()
        )
        .all()
    )

    return render_template(
        "profile.html",
        user=user,
        predictions=predictions
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if not user:
            return render_template(
                "login.html",
                error="Invalid email or password"
            )

        try:
            password_hasher.verify(user.password_hash, password)
        except VerifyMismatchError:
            return render_template(
                "login.html",
                error="Invalid email or password"
            )

        session["user_id"] = user.id

        return redirect(url_for("home"))

    return render_template("login.html")

password_hasher = PasswordHasher()
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            return render_template(
                "signup.html",
                error="Passwords do not match"
                )

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
             return render_template(
                "signup.html",
                error="Email already registered"
                )

        password_hash = password_hasher.hash(password)

        user = User(
            name=name,
            email=email,
            password_hash=password_hash,
            auth_provider="email",
            provider_user_id=None,
            created_at=datetime.now(timezone.utc)
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for("home"))

    return render_template("signup.html")
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    total_predictions = (
        db.session.query(func.count(Prediction.id))
        .filter(Prediction.user_id == user_id)
        .scalar()
    )

    most_predicted = (
        db.session.query(
            PredictionResult.predicted_genre,
            func.count(Prediction.id).label("count")
        )
        .join(
            Prediction,
            Prediction.prediction_result_id == PredictionResult.id
        )
        .filter(Prediction.user_id == user_id)
        .group_by(PredictionResult.predicted_genre)
        .order_by(func.count(Prediction.id).desc())
        .first()
    )

    most_predicted_genre = (
        most_predicted.predicted_genre
        if most_predicted
        else "—"
    )

    avg_agreement = (
        db.session.query(
            func.avg(
                PredictionResult.winning_votes * 100.0
                / PredictionResult.total_segments
            )
        )
        .join(
            Prediction,
            Prediction.prediction_result_id == PredictionResult.id
        )
        .filter(Prediction.user_id == user_id)
        .scalar()
    )

    avg_agreement = round(avg_agreement, 1) if avg_agreement else 0

    genre_distribution = (
        db.session.query(
            PredictionResult.predicted_genre,
            func.count(Prediction.id)
        )
        .join(
            Prediction,
            Prediction.prediction_result_id == PredictionResult.id
        )
        .filter(Prediction.user_id == user_id)
        .group_by(PredictionResult.predicted_genre)
        .order_by(func.count(Prediction.id).desc())
        .all()
    )

    activity = (
        db.session.query(
            func.date(Prediction.created_at),
            func.count(Prediction.id)
        )
        .filter(Prediction.user_id == user_id)
        .group_by(func.date(Prediction.created_at))
        .order_by(func.date(Prediction.created_at))
        .all()
    )

    recent_predictions = (
        db.session.query(
            Prediction,
            AudioFile,
            PredictionResult
        )
        .join(
            AudioFile,
            Prediction.audio_file_id == AudioFile.id
        )
        .join(
            PredictionResult,
            Prediction.prediction_result_id == PredictionResult.id
        )
        .filter(Prediction.user_id == user_id)
        .order_by(Prediction.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard.html",
        total_predictions=total_predictions,
        most_predicted_genre=most_predicted_genre,
        avg_agreement=avg_agreement,
        genre_distribution=genre_distribution,
        activity=activity,
        recent_predictions=recent_predictions
    )

@app.route("/upload", methods=["POST"])
def upload():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if "audio" not in request.files:
        return "No audio file uploaded", 400

    file = request.files["audio"]

    if file.filename == "":
        return "No audio file selected", 400

    file_data = file.read()

    content_hash = hashlib.sha256(file_data).hexdigest()

    existing_object = AudioObject.query.filter_by(
        content_hash=content_hash
    ).first()

    if existing_object:
        audio_object = existing_object
    else:
        object_key = f"audio/{uuid.uuid4()}_{file.filename}"

        from io import BytesIO

        minio_client.put_object(
            "data",
            object_key,
            BytesIO(file_data),
            length=len(file_data),
            content_type=file.content_type or "audio/mpeg"
        )

        audio_object = AudioObject(
            content_hash=content_hash,
            object_key=object_key,
            file_type=file.content_type or "audio/mpeg",
            file_size=len(file_data),
            created_at=datetime.now(timezone.utc)
        )

        db.session.add(audio_object)
        db.session.commit()

    audio_file = AudioFile(
        user_id=session["user_id"],
        audio_object_id=audio_object.id,
        original_filename=file.filename,
        uploaded_at=datetime.now(timezone.utc)
    )

    db.session.add(audio_file)
    db.session.commit()

    prediction_result = PredictionResult.query.filter_by(
        audio_object_id=audio_object.id
    ).first()

    if not prediction_result:
        temp_filename = f"temp_{uuid.uuid4()}_{file.filename}"

        with open(temp_filename, "wb") as temp_file:
            temp_file.write(file_data)

        try:
            result = predict_file(temp_filename)
        finally:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

        prediction_result = PredictionResult(
            audio_object_id=audio_object.id,
            predicted_genre=result["genre"],
            winning_votes=result["winning_votes"],
            total_segments=result["total_segments"],
            created_at=datetime.now(timezone.utc)
        )

        db.session.add(prediction_result)
        db.session.commit()

    prediction = Prediction(
        user_id=session["user_id"],
        audio_file_id=audio_file.id,
        prediction_result_id=prediction_result.id,
        created_at=datetime.now(timezone.utc)
    )

    db.session.add(prediction)
    db.session.commit()

    return redirect(url_for(
        "prediction",
        prediction_id=prediction.id
    ))
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)