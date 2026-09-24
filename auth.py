from flask import Blueprint, render_template, request, redirect, url_for, session
from models import db, User
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from datetime import datetime, timezone

auth_bp = Blueprint("auth", __name__)

password_hasher = PasswordHasher()

@auth_bp.route("/")
def login_page():
    return render_template("login.html")

@auth_bp.route("/auth/google")
def google_login():
    from app import google

    redirect_uri = url_for(
        "auth.google_callback",
        _external=True
    )

    return google.authorize_redirect(redirect_uri)

@auth_bp.route("/auth/google/callback")
def google_callback():
    from app import google

    token = google.authorize_access_token()
    userinfo = token["userinfo"]

    google_id = userinfo["sub"]
    email = userinfo["email"]
    name = userinfo.get("name", email)

    user = User.query.filter_by(
        auth_provider="google",
        provider_user_id=google_id
    ).first()

    if not user:
        user = User.query.filter_by(
            email=email
        ).first()

    if not user:
        user = User(
            name=name,
            email=email,
            password_hash=None,
            auth_provider="google",
            provider_user_id=google_id,
            created_at=datetime.now(timezone.utc)
        )

        db.session.add(user)
        db.session.commit()

    session["user_id"] = user.id

    return redirect(url_for("home"))

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(
            email=email
        ).first()

        if not user:
            return render_template(
                "login.html",
                error="Invalid email or password"
            )

        if user.auth_provider != "email" or not user.password_hash:
            return render_template(
                "login.html",
                error="This account uses Google Sign-In"
            )

        try:
            password_hasher.verify(
                user.password_hash,
                password
            )
        except VerifyMismatchError:
            return render_template(
                "login.html",
                error="Invalid email or password"
            )

        session["user_id"] = user.id

        return redirect(url_for("home"))

    return render_template("login.html")

@auth_bp.route("/signup", methods=["GET", "POST"])
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

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:
            if existing_user.auth_provider == "google":
                return render_template(
                    "signup.html",
                    error="This email uses Google Sign-In"
                )

            return render_template(
                "signup.html",
                error="Email already exists. Please log in."
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

        session["user_id"] = user.id

        return redirect(url_for("home"))

    return render_template("signup.html")