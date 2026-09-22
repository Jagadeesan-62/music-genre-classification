from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    auth_provider = db.Column(db.String(20), nullable=False)
    provider_user_id = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)


class AudioObject(db.Model):
    __tablename__ = "audio_objects"

    id = db.Column(db.BigInteger, primary_key=True)
    content_hash = db.Column(db.String(64), unique=True, nullable=False)
    object_key = db.Column(db.Text, unique=True, nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)


class AudioFile(db.Model):
    __tablename__ = "audio_files"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id"),
        nullable=False
    )
    audio_object_id = db.Column(
        db.BigInteger,
        db.ForeignKey("audio_objects.id"),
        nullable=False
    )
    original_filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=False)


class PredictionResult(db.Model):
    __tablename__ = "prediction_results"

    id = db.Column(db.BigInteger, primary_key=True)
    audio_object_id = db.Column(
        db.BigInteger,
        db.ForeignKey("audio_objects.id"),
        nullable=False
    )
    predicted_genre = db.Column(db.String(50), nullable=False)
    winning_votes = db.Column(db.Integer, nullable=False)
    total_segments = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)


class Prediction(db.Model):
    __tablename__ = "predictions"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id"),
        nullable=False
    )
    audio_file_id = db.Column(
        db.BigInteger,
        db.ForeignKey("audio_files.id"),
        nullable=False
    )
    prediction_result_id = db.Column(
        db.BigInteger,
        db.ForeignKey("prediction_results.id"),
        nullable=False
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)