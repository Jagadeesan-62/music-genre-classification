from flask import Flask, render_template, redirect, url_for, session
from models import db
import os
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth
from auth import auth_bp
from profile import profile_bp
from dashboard import dashboard_bp
import boto3
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
app.config["S3_BUCKET"] = "music-genre-audio-396465333763-ap-south-1-an"
app.config["S3_REGION"] = "ap-south-1"

s3_client = boto3.client(
    "s3",
    region_name=app.config["S3_REGION"]
)

app.s3_client = s3_client
db.init_app(app)

app.register_blueprint(auth_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(prediction_bp)




@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)