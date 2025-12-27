# 🧠 Emotion Care – Mental Health Web Application

Emotion Care is a full-stack Flask-based mental health web application that helps users
understand and track their emotional well-being using AI-based emotion detection,
chatbot interaction, mood tracking, and music recommendations.

---

## ✨ Features

- 🔐 User authentication (Signup / Login / Logout)
- 😊 Emotion detection from:
  - Facial images (DeepFace)
  - Chat text (TextBlob + Gemini AI)
- 📊 Mood Tracker with interactive charts (Chart.js)
- 💬 Emotion-aware AI Chatbot
- 🎵 Mood-based music recommendations with YouTube links
- 📝 Personal blog/journal posts
- ⚠️ Graceful handling of API failures and errors

---

## 🛠️ Tech Stack

### Backend
- Python
- Flask
- SQLAlchemy (ORM)
- SQLite
- Flask-Bcrypt (password hashing)

### Frontend
- HTML
- CSS
- Bootstrap
- JavaScript (Fetch API, DOM manipulation)

### AI & APIs
- DeepFace (facial emotion detection)
- TextBlob (sentiment analysis)
- Google Gemini API (chatbot & music recommendation)

---

## ⚙️ Environment Variables

Create a `.env` file (DO NOT upload it to GitHub):
GEMINI_API_KEY=your_api_key_here
SECRET_KEY=your_secret_key_here

