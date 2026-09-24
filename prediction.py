from flask import Blueprint, render_template, request, redirect, url_for, session, current_app
from models import db, User, Prediction, AudioFile, PredictionResult, AudioObject
from ml.predictor import predict_file
from datetime import datetime, timezone
import hashlib
import uuid
import os
from io import BytesIO

prediction_bp = Blueprint("prediction", __name__)


@prediction_bp.route("/prediction")
def prediction():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

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


@prediction_bp.route("/upload", methods=["POST"])
def upload():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

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

        current_app.minio_client.put_object(
            current_app.config["MINIO_BUCKET"],
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

    prediction_record = Prediction(
        user_id=session["user_id"],
        audio_file_id=audio_file.id,
        prediction_result_id=prediction_result.id,
        created_at=datetime.now(timezone.utc)
    )

    db.session.add(prediction_record)
    db.session.commit()

    return redirect(url_for(
        "prediction.prediction",
        prediction_id=prediction_record.id
    ))


@prediction_bp.route("/prediction/<int:prediction_id>/delete", methods=["POST"])
def delete_prediction(prediction_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    prediction_record = Prediction.query.filter_by(
        id=prediction_id,
        user_id=session["user_id"]
    ).first()

    if not prediction_record:
        return "Prediction not found", 404

    audio_file = AudioFile.query.filter_by(
        id=prediction_record.audio_file_id,
        user_id=session["user_id"]
    ).first()

    db.session.delete(prediction_record)
    db.session.commit()

    if audio_file:
        db.session.delete(audio_file)
        db.session.commit()

    return redirect(url_for("profile.profile"))


@prediction_bp.route("/account/delete", methods=["POST"])
def delete_account():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]

    predictions = Prediction.query.filter_by(
        user_id=user_id
    ).all()

    audio_file_ids = [
        prediction.audio_file_id
        for prediction in predictions
    ]

    for prediction in predictions:
        db.session.delete(prediction)

    db.session.commit()

    for audio_file_id in audio_file_ids:
        audio_file = AudioFile.query.filter_by(
            id=audio_file_id,
            user_id=user_id
        ).first()

        if audio_file:
            db.session.delete(audio_file)

    db.session.commit()

    user = User.query.filter_by(id=user_id).first()

    if user:
        db.session.delete(user)
        db.session.commit()

    session.clear()

    return redirect(url_for("auth.login"))