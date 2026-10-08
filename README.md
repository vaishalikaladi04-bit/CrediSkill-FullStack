# Smart Recruitment Platform

A Flask and MongoDB application for students, recruiters, and administrators. It includes candidate profiles and resumes, job listings and applications, assessments, interview scheduling, messaging, and feedback. Optional Groq integration can generate assessment questions.

## Requirements

- Python 3.10 or newer
- MongoDB, either running locally or hosted with MongoDB Atlas
- A Groq API key is optional

## Run locally

1. Clone the repository and enter its directory:

   ```powershell
   git clone https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
   cd YOUR-REPOSITORY
   ```

2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   On macOS or Linux, use `python3 -m venv .venv` and `source .venv/bin/activate`.

3. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env`:

   ```powershell
   Copy-Item .env.example .env
   ```

   Set `SECRET_KEY` to a unique random value and set `MONGO_URI` to your MongoDB connection string. Add `GROQ_API_KEY` only if you want the optional Groq-powered features.

   Generate a secret key with:

   ```powershell
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

5. Start the application:

   ```powershell
   python app.py
   ```

6. Open <http://127.0.0.1:5000> in your browser.

## Create an administrator

After configuring MongoDB and `.env`, set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env` to the administrator credentials you want to use. Choose a unique, strong password, then run:

```powershell
python create_admin.py
```

The script creates the account only if that email does not already exist. It does not reset an existing account's password.

## Configuration

| Variable | Required | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | Yes | Signs Flask sessions. Use a private, randomly generated value. |
| `MONGO_URI` | Yes | MongoDB connection URI. The local example connects to `smart_education`. |
| `GROQ_API_KEY` | No | Enables optional Groq-powered assessment generation. |
| `ADMIN_EMAIL` | Only for administrator setup | Email for the initial administrator account. |
| `ADMIN_PASSWORD` | Only for administrator setup | Password for the initial administrator account. |

Never commit `.env`, database credentials, API keys, real user data, or uploaded resumes. `.gitignore` excludes these local files and generated uploads.

## Publish the source on GitHub

Create an empty repository on GitHub, then from this project directory run:

```powershell
git init
git add .
git status
```

Review `git status` and confirm `.env`, `templates/.env`, and uploaded files are not staged. Then commit and push:

```powershell
git commit -m "Initial project upload"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Replace `YOUR-USERNAME` and `YOUR-REPOSITORY` with the values from the GitHub repository you created. GitHub stores and versions the source code; GitHub Pages cannot run this Flask application. Making the application available as a live website requires a Python web host and a reachable MongoDB database.
