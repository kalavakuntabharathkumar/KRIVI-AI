from flask import Flask, request, render_template, send_from_directory, redirect, session
from resume_parser import extract_text_from_pdf, parse_resume_text
from jinja2 import Environment, FileSystemLoader
from html_generator import generate_portfolio_html
from flask import send_file

import os
import zipfile
import json

app = Flask(__name__)
app.secret_key = 'supersecretkey'

UPLOAD_FOLDER = 'uploads'
GENERATED_FOLDER = 'generated_portfolio'
ZIP_FOLDER = 'zips'
TEMPLATES_FOLDER = 'templates'
USER_FILE = 'users.json'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)
os.makedirs(ZIP_FOLDER, exist_ok=True)

env = Environment(loader=FileSystemLoader(TEMPLATES_FOLDER))

# Load users.json
def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, 'r') as f:
        return json.load(f)

# Save users.json
def save_users(users):
    with open(USER_FILE, 'w') as f:
        json.dump(users, f, indent=2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = load_users()
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        if email in users:
            return "❌ Email already registered."

        users[email] = {
            'name': name,
            'password': password,
            'role': 'user',
            'resumes': []
        }
        save_users(users)
        return redirect('/login')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = load_users()
        email = request.form['email']
        password = request.form['password']

        if email in users and users[email]['password'] == password:
            session['email'] = email
            session['role'] = users[email]['role']
            return redirect('/admin' if users[email]['role'] == 'admin' else '/dashboard')
        return "❌ Invalid credentials."

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return redirect('/')
    users = load_users()
    return render_template('admin_dashboard.html', users=users)

@app.route('/dashboard')
def dashboard():
    if not session.get('email'):
        return redirect('/login')
    users = load_users()
    email = session['email']
    history = users[email].get("resumes", [])
    return render_template('dashboard.html', email=email, history=history)

@app.route('/generate', methods=['POST'])
def generate():
    resume_file = request.files['resume']
    photo_file = request.files.get('photo')

    resume_path = os.path.join(UPLOAD_FOLDER, resume_file.filename)
    resume_file.save(resume_path)

    photo_filename = None
    if photo_file and photo_file.filename:
        photo_filename = "profile.jpg"
        photo_path = os.path.join(GENERATED_FOLDER, photo_filename)
        photo_file.save(photo_path)

    text = extract_text_from_pdf(resume_path)
    parsed_data = parse_resume_text(text)

    if not parsed_data:
        return "❌ Resume parsing failed. No data was extracted.", 400

    parsed_data["photo"] = photo_filename
    session['parsed_data'] = parsed_data

    template_name = request.form.get('template', 'default')

    if template_name == 'default':
        html = generate_default_html(parsed_data)
        with open("generated_portfolio.html", "w", encoding="utf-8") as f:
            f.write(html)
        return send_file("generated_portfolio.html")
    else:
        template_folder = template_name.split('/')[0]
        session['template_folder'] = template_folder

        generate_portfolio_html(parsed_data, template_name=template_name)

        zip_path = os.path.join(ZIP_FOLDER, "portfolio.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for filename in os.listdir(GENERATED_FOLDER):
                file_path = os.path.join(GENERATED_FOLDER, filename)
                zipf.write(file_path, arcname=filename)
            zipf.write(resume_path, arcname=resume_file.filename)

        return f'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <title>Portfolio Created</title>
          <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
          <style>
            body {{
              background: linear-gradient(to right, #00c6ff, #0072ff);
              font-family: 'Segoe UI', sans-serif;
              color: white;
              text-align: center;
              padding-top: 10%;
            }}
            .card {{
              background: rgba(255, 255, 255, 0.1);
              border-radius: 15px;
              padding: 2rem;
              max-width: 600px;
              margin: auto;
              backdrop-filter: blur(10px);
              box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
            }}
            a.btn {{
              margin: 10px;
              border-radius: 30px;
            }}
            a:hover {{
              transform: scale(1.05);
              transition: all 0.2s ease-in-out;
            }}
          </style>
        </head>
        <body>
          <div class="card">
            <h2>✅ Multi-Page Portfolio Generated!</h2>
            <p class="lead">Your portfolio website is ready with multiple sections.</p>
            <a href="/home" target="_blank" class="btn btn-light btn-lg">🌐 View Portfolio</a>
            <a href="/download/portfolio.zip" target="_blank" class="btn btn-outline-light btn-lg">📦 Download ZIP</a>
            <br><br>
            <a href="/dashboard" class="btn btn-secondary">⬅️ Back to Dashboard</a>
          </div>
        </body>
        </html>
        '''

@app.route('/portfolio/<path:filename>')
def serve_portfolio(filename):
    return send_from_directory(GENERATED_FOLDER, filename)

@app.route('/portfolio/style.css')
def serve_css():
    return send_from_directory('generated_portfolio', 'style.css')

@app.route('/home')
def home():
    return render_template("home.html", data=session.get('parsed_data'))

@app.route('/skills')
def skills():
    return render_template("skills.html", data=session.get('parsed_data'))

@app.route('/projects')
def projects():
    return render_template("projects.html", data=session.get('parsed_data'))

@app.route('/certificates')
def certificates():
    return render_template("certificates.html", data=session.get('parsed_data'))

@app.route('/experience')
def experience():
    return render_template("experience.html", data=session.get('parsed_data'))

@app.route('/education')
def education():
    return render_template("education.html", data=session.get('parsed_data'))

@app.route('/languages')
def languages():
    return render_template("languages.html", data=session.get('parsed_data'))

@app.route('/download/<path:filename>')
def download_zip(filename):
    return send_from_directory(ZIP_FOLDER, filename, as_attachment=True)

def generate_default_html(data):
    return f"""
    <html>
    <head><title>{data['name']}</title></head>
    <body>
      <h1>{data['name']}</h1>
      <p>{data['email']} | {data['phone']}</p>
      <h2>Skills</h2>
      <p>{', '.join(data['skills'])}</p>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(debug=True)
