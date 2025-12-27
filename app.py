
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename
from deepface import DeepFace
import os
from dotenv import load_dotenv
import google.generativeai as genai
from textblob import TextBlob
import traceback
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask import flash

load_dotenv()

app = Flask(__name__)
# Database Config
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///blog.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
bcrypt = Bcrypt(app)
db = SQLAlchemy(app)
# Needed for sessions and flash messages
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")


app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Gemini API Key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Change this line
model = genai.GenerativeModel("gemini-2.5-flash") 

# USER MODEL
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    posts = db.relationship("Post", backref="user", lazy=True)

# POST MODEL
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

class MoodEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emotion = db.Column(db.String(50), nullable=False)  
    source = db.Column(db.String(50))  # detect / chatbot
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

@app.route("/")
def home():
    return render_template("home.html")

@app.route('/detect', methods=['GET', 'POST'])
def detect():
    if request.method == 'GET':
        return render_template("detect.html")
      
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    image = request.files['image']
    filename = secure_filename(image.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    image.save(filepath)

    try:
        analysis = DeepFace.analyze(img_path=filepath, actions=['emotion'])
        result = analysis[0]  # DeepFace returns a list

        emotion = result['dominant_emotion']
        confidence = float(result['emotion'][emotion])

# Normalize emotion
        if emotion in ["happy", "surprise"]:
            mood_value = "positive"
        elif emotion in ["sad", "angry", "fear", "disgust"]:
            mood_value = "negative"
        else:
            mood_value = "neutral"

# Save mood  if user is logged in
        if "user_id" in session:
           mood = MoodEntry(
               emotion=mood_value,
               source="detect",
               user_id=session["user_id"]
           )
           db.session.add(mood)
           db.session.commit()

        return jsonify({
            'success': True,
            'emotion': emotion,
            'confidence': confidence
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    if request.method == "GET":
        return render_template("chatbot.html")

    try:
        data = request.get_json(force=True)
        user_msg = data.get("message", "").strip()

        if not user_msg:
            return jsonify({"error": "Message is required"}), 400

        # 1) Local emotion estimate (TextBlob) - will always work offline
        try:
            polarity = TextBlob(user_msg).sentiment.polarity
            if polarity > 0.2:
                emotion = "positive"
                tips = ["Keep doing things that make you happy!", "Enjoy the moment!"]
            elif polarity < -0.2:
                emotion = "negative"
                tips = ["It's okay to feel this way.", "Try talking with a friend."]
            else:
                emotion = "neutral"
                tips = ["I'm here if you want to share more."]
        except Exception as e_em:
            print("TextBlob error:", e_em)
            emotion = "unknown"
            tips = []

        # 2) Ask Gemini (separate try so it can't crash the whole route)
        bot_reply = ""
        try:
            # build a clear, short prompt
            prompt = (
                f"You are a supportive chatbot. The user said: '{user_msg}'. "
                f"Reply in a gentle, empathetic tone (1-2 short paragraphs)."
            )
            ai_response = model.generate_content(prompt)
            bot_reply = getattr(ai_response, "text", "") or str(ai_response)
            bot_reply = bot_reply.strip()
        except Exception as e_gem:
            print("Gemini error (safe):", e_gem)
            traceback.print_exc()
            bot_reply = "⚠️ Chatbot service is temporarily unavailable."
        
        # Save chatbot mood
        if "user_id" in session and emotion in ["positive", "neutral", "negative"]:
            mood = MoodEntry(
        emotion=emotion,
        source="chatbot",
        user_id=session["user_id"]
            )
            db.session.add(mood)
            db.session.commit()

        # final JSON (always)
        return jsonify({
            "bot_reply": bot_reply,
            "emotion": emotion,
            "tips": tips
        }), 200

    except Exception as e:
        # Last-resort catch: log and return JSON so frontend never breaks
        print("Chatbot route failure:", e)
        traceback.print_exc()
        return jsonify({
            "bot_reply": "⚠️ Chatbot route failed. Check server logs.",
            "emotion": "unknown",
            "tips": []
        }), 500

@app.route("/resources")
def resources():
    return render_template("resources.html")

@app.post("/music_recommend")
def music_recommend():
    data = request.get_json()
    emotion = data.get("emotion", "")
    language = data.get("language", "hindi")  # default

    prompt = f"""
    You are a music recommendation assistant.
    Suggest 3 {language} songs for a person feeling '{emotion}'.
    Give each song a one-line reason.
    Format using bullet points.
    """

    try:
        ai_response = model.generate_content(prompt)
        reply = ai_response.text

        return jsonify({
            "recommendation": reply
        })

    except Exception as e:
        print("Music Error:", e)
        return jsonify({"recommendation": "⚠️ Could not generate music suggestions."})

# POSTS

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = bcrypt.generate_password_hash(request.form["password"])

        if User.query.filter_by(username=username).first():
            flash("Username already exists!", "danger")
            return redirect("/signup")

        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()

        flash("Account created successfully! Please log in.", "success")
        return redirect("/login")

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            flash(f"Welcome back, {user.username}!", "success")
            return redirect("/")

        flash("Invalid credentials!", "danger")
        return redirect("/login")

    return render_template("login.html")

@app.route("/mood-tracker")
def mood_tracker():
    if "user_id" not in session:
        flash("Please login to view your mood tracker.", "warning")
        return redirect("/login")

    mood_entries = MoodEntry.query.filter_by(
         user_id=session["user_id"]
        ).order_by(MoodEntry.timestamp.asc()).all()

    moods = [
    {
        "emotion": m.emotion,
        "timestamp": m.timestamp.isoformat()
    }
    for m in mood_entries
    ]

    return render_template("mood_tracker.html", moods=moods)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    if "user_id" not in session:
        flash("Please log in to create a post.", "warning")
        return redirect("/login")

    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        image = request.files.get("image")

        filename = None
        if image:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        post = Post(
            title=title,
            content=content,
            image=filename,
            user_id=session["user_id"]
        )

        db.session.add(post)
        db.session.commit()
        flash("Post created successfully!", "success")
        return redirect(url_for('show_posts'))

    return render_template("create_post.html")

@app.route("/posts")
def show_posts():
    all_posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template("posts.html", posts=all_posts)

@app.route("/edit_post/<int:id>", methods=["GET", "POST"])
def edit_post(id):
    post = Post.query.get(id)

    if not post or post.user_id != session.get("user_id"):
        flash("Not allowed!", "danger")
        return redirect(url_for('show_posts'))

    if request.method == "POST":
        post.title = request.form["title"]
        post.content = request.form["content"]

        image = request.files.get("image")
        if image:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            post.image = filename

        db.session.commit()
        flash("Post updated successfully!", "success")
        return redirect(url_for('show_posts'))

    return render_template("edit_post.html", post=post)

@app.route("/delete_post/<int:id>")
def delete_post(id):
    post = Post.query.get(id)

    if not post or post.user_id != session.get("user_id"):
        flash("Unauthorized!", "danger")
        return redirect(url_for('show_posts'))

    db.session.delete(post)
    db.session.commit()
    flash("Post deleted successfully!", "success")
    return redirect(url_for('show_posts'))


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
