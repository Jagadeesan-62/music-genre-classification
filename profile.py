from flask import Blueprint, render_template, request, redirect, url_for, session
from models import db, User, Prediction, AudioFile, PredictionResult

profile_bp = Blueprint("profile", __name__)

@profile_bp.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

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

@profile_bp.route("/profile/country", methods=["POST"])
def update_country():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    country = request.form.get(
        "country",
        ""
    ).strip().upper()

    user = User.query.get(
        session["user_id"]
    )

    if not user:
        return redirect(url_for("auth.login"))

    user.country = country if country else None

    db.session.commit()

    return redirect(url_for("profile.profile"))