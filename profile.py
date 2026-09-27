from flask import Blueprint, render_template, request, redirect, url_for, session
from models import db, User, UserPreference, Prediction, AudioFile, PredictionResult


profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]

    user = User.query.get(user_id)

    if not user:
        return redirect(url_for("auth.login"))

    preferences = UserPreference.query.filter_by(
        user_id=user_id
    ).first()

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
            Prediction.user_id == user_id
        )
        .order_by(
            Prediction.created_at.desc()
        )
        .all()
    )

    return render_template(
        "profile.html",
        user=user,
        preferences=preferences,
        predictions=predictions
    )


@profile_bp.route("/profile/preferences", methods=["POST"])
def update_preferences():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]

    country = request.form.get(
        "country",
        ""
    ).strip().upper()

    languages = request.form.getlist("preferred_languages")

    languages = [
        language.strip()
        for language in languages
        if language.strip()
    ]

    preferences = UserPreference.query.filter_by(
        user_id=user_id
    ).first()

    if not preferences:
        preferences = UserPreference(
            user_id=user_id
        )
        db.session.add(preferences)

    preferences.country = country if country else None
    preferences.preferred_languages = (
        ",".join(languages) if languages else None
    )

    db.session.commit()

    return redirect(url_for("profile.profile"))