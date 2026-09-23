from datetime import datetime, timedelta, timezone

from app import app, minio_client
from models import db, AudioObject, AudioFile, Prediction, PredictionResult

GRACE_PERIOD_DAYS = 7

with app.app_context():
    now = datetime.now(timezone.utc)

    audio_objects = AudioObject.query.all()

    for audio_object in audio_objects:
        audio_file = AudioFile.query.filter_by(
            audio_object_id=audio_object.id
        ).first()

        prediction_results = PredictionResult.query.filter_by(
            audio_object_id=audio_object.id
        ).all()

        has_prediction = False

        for prediction_result in prediction_results:
            prediction = Prediction.query.filter_by(
                prediction_result_id=prediction_result.id
            ).first()

            if prediction:
                has_prediction = True
                break

        if audio_file or has_prediction:
            if audio_object.garbage_marked_at is not None:
                audio_object.garbage_marked_at = None

                print(
                    f"UNMARK | AudioObject {audio_object.id} | "
                    f"{audio_object.object_key}"
                )
            else:
                print(
                    f"KEEP | AudioObject {audio_object.id} | "
                    f"{audio_object.object_key}"
                )

            continue

        if audio_object.garbage_marked_at is None:
            audio_object.garbage_marked_at = now

            print(
                f"MARK | AudioObject {audio_object.id} | "
                f"{audio_object.object_key}"
            )

            continue

        marked_age = now - audio_object.garbage_marked_at

        if marked_age < timedelta(days=GRACE_PERIOD_DAYS):
            remaining = timedelta(days=GRACE_PERIOD_DAYS) - marked_age

            print(
                f"WAIT | AudioObject {audio_object.id} | "
                f"Grace period remaining: {remaining}"
            )

            continue

        final_audio_file = AudioFile.query.filter_by(
            audio_object_id=audio_object.id
        ).first()

        final_prediction_results = PredictionResult.query.filter_by(
            audio_object_id=audio_object.id
        ).all()

        final_has_prediction = False

        for prediction_result in final_prediction_results:
            prediction = Prediction.query.filter_by(
                prediction_result_id=prediction_result.id
            ).first()

            if prediction:
                final_has_prediction = True
                break

        if final_audio_file or final_has_prediction:
            audio_object.garbage_marked_at = None

            print(
                f"UNMARK | AudioObject {audio_object.id} | "
                f"Reference appeared during grace period"
            )

            continue

        try:
            minio_client.remove_object(
                "data",
                audio_object.object_key
            )

            print(
                f"DELETED FROM MINIO | AudioObject {audio_object.id} | "
                f"{audio_object.object_key}"
            )

        except Exception as e:
            print(
                f"MINIO DELETE FAILED | AudioObject {audio_object.id} | "
                f"{e}"
            )

            continue

        try:
            prediction_results = PredictionResult.query.filter_by(
                audio_object_id=audio_object.id
            ).all()

            for prediction_result in prediction_results:
                db.session.delete(prediction_result)

            db.session.flush()

            db.session.delete(audio_object)

            db.session.commit()

            print(
                f"DELETED FROM DATABASE | AudioObject {audio_object.id}"
            )

        except Exception as e:
            db.session.rollback()

            print(
                f"DATABASE DELETE FAILED | AudioObject {audio_object.id} | "
                f"{e}"
            )

    db.session.commit()