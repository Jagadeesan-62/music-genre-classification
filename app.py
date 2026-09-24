from flask import Flask, render_template, redirect, url_for, session
from models import db
import os
from minio import Minio
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth
from auth import auth_bp
from profile import profile_bp
from dashboard import dashboard_bp
from prediction import prediction_bp

load_dotenv()

app = Flask(__name__)
oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.environ["GOOGLE_CLIENT_ID"],
    client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)

app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MINIO_BUCKET"] = "data"

db.init_app(app)

app.register_blueprint(auth_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(prediction_bp)

minio_client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False
)

app.minio_client = minio_client


@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)