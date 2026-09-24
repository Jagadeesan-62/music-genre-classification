from flask import Blueprint, render_template, redirect, url_for, session
from models import db, User, Prediction, AudioFile, PredictionResult
from sqlalchemy import func
from spotify_service import search_tracks

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    user = User.query.get(user_id)

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

    spotify_tracks = []

    if most_predicted:
        market = user.country or "US"

        spotify_tracks = search_tracks(
            most_predicted.predicted_genre.lower(),
            10,
            market=market
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
        recent_predictions=recent_predictions,
        spotify_tracks=spotify_tracks
    )