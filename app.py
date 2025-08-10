###############################################################################
#  app.py  –  auto_portfolio (clean + PDF resume)
###############################################################################
from flask import (
    Flask, request, render_template, send_from_directory,
    redirect, session, url_for
)
import os, json, random, zipfile, re
import request
import base64

from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from dotenv import load_dotenv
load_dotenv()
from urllib.parse import urlencode


from resume_parser      import extract_text_from_pdf, parse_resume_text
from resume_precleaner  import standardize_resume_text               # your cleaner

# ─────────────────────────────  CONFIG  ─────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_secret")

UPLOAD_FOLDER    = "uploads"
GENERATED_FOLDER = "generated_portfolio"
ZIP_FOLDER       = "zips"
TEMPLATES_FOLDER = "templates"
USER_FILE        = "users.json"

from flask_mail import Mail, Message

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'vigoenterprises8@gmail.com'  # your email
app.config['MAIL_PASSWORD'] = 'rwwj didl cjyd yhin'           # use App Password here (not real password)

mail = Mail(app)


for folder in (UPLOAD_FOLDER, GENERATED_FOLDER, ZIP_FOLDER):
    os.makedirs(folder, exist_ok=True)

env = Environment(loader=FileSystemLoader('templates'))
env.globals.update(url_for=url_for)
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

def get_parsed_data():
    json_path = "parsed_data.json"
    if os.path.exists(json_path):
        with open(json_path, "r") as f:
            return json.load(f)
    data = session.get("parsed_data")
    if data:
        return data
    # fallback — redirect to home with a message
    return redirect(url_for("index"))




# ─────────────────────────────  HELPERS  ────────────────────────────
def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r") as fh:
        return json.load(fh)

def save_users(users):
    with open(USER_FILE, "w") as fh:
        json.dump(users, fh, indent=2)

def current_theme(default="template_01"):
    return session.get("theme", default)

def save_clean_text(text: str, name="cleaned_resume.txt") -> str:
    path = os.path.join(UPLOAD_FOLDER, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path

# Regex for hyperlinks in cleaner + PDF builder
URL_RX = re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.I)

def create_cleaned_resume_pdf(text: str, pdf_path: str) -> None:
    """Write cleaned text to PDF and embed clickable hyperlinks."""
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4
    y = height - 40
    c.setFont("Helvetica", 10)

    for raw in text.splitlines():
        if y < 40:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 10)

        urls = list(URL_RX.finditer(raw))
        if not urls:                   # simple line (no link)
            c.drawString(40, y, raw)
        else:
            x = 40
            cursor = 0
            for m in urls:
                before = raw[cursor:m.start()]
                url    = m.group(0)
                after  = ""            # only draw first link per line for simplicity
                # draw part before link
                c.drawString(x, y, before)
                x += c.stringWidth(before, "Helvetica", 10)
                # draw the link (blue, underlined)
                c.setFillColor(colors.blue)
                c.drawString(x, y, url)
                link_w = c.stringWidth(url, "Helvetica", 10)
                c.linkURL(url if url.startswith("http") else f"https://{url}",
                          (x, y-1, x+link_w, y+9))
                c.line(x, y-1, x+link_w, y-1)
                c.setFillColor(colors.black)
                x += link_w
                cursor = m.end()
            # any remainder of line (after last link)
            if cursor < len(raw):
                c.drawString(x, y, raw[cursor:])
        y -= 14
    c.save()

def load_template_css(theme) -> str:
    css_path = os.path.join(TEMPLATES_FOLDER, theme, "style.css")
    if os.path.exists(css_path):
        return open(css_path, encoding="utf-8").read()
    return ""

def render_page(page, **ctx):
    theme = current_theme()
    ctx.setdefault("template", theme)
    ctx.setdefault("year", datetime.now().year)
    tpl = f"{theme}/{page}.html"
    if os.path.exists(os.path.join(TEMPLATES_FOLDER, tpl)):
        return render_template(tpl, **ctx)
    return render_template(f"{page}.html", **ctx)

# ───────────────────────  AUTH / BASIC ROUTES  ──────────────────────
@app.route("/")
def index(): return render_template("index.html")

# (register / login / logout unchanged — omitted here for brevity)
# … include your register, login, logout, admin, dashboard routes …

# ─────────────────────────  GENERATE ROUTE  ────────────────────────
@app.route("/generate", methods=["POST"])
def generate():
    resume_file = request.files["resume"]
    photo_file = request.files.get("photo")
    theme = request.form.get("theme", "template_01").strip()

    if theme.lower() == "galaxy":
        return "❌ Galaxy theme does not support static export.", 400

    if theme == "random":
        themes = [d for d in os.listdir(TEMPLATES_FOLDER) if d.startswith("template_")]
        theme = random.choice(themes) if themes else "template_01"
    session["theme"] = theme

    resume_path = os.path.join(UPLOAD_FOLDER, resume_file.filename)
    resume_file.save(resume_path)

    photo_filename = None
    if photo_file and photo_file.filename:
        photo_filename = "profile.jpg"
        photo_path = os.path.join(GENERATED_FOLDER, photo_filename)
        photo_file.save(photo_path)

    raw_text = extract_text_from_pdf(resume_path)
    cleaned_text = standardize_resume_text(raw_text)
    data = parse_resume_text(cleaned_text)
    if not data:
        return "❌ Resume parsing failed.", 400
    data["photo"] = photo_filename
    session["parsed_data"] = data

    # Save cleaned resume files
    with open(os.path.join(UPLOAD_FOLDER, "cleaned_resume.txt"), "w", encoding="utf-8") as fh:
        fh.write(cleaned_text)
    create_cleaned_resume_pdf(cleaned_text, os.path.join(UPLOAD_FOLDER, "cleaned_resume.pdf"))

    # Jinja context
    ctx = {
        "data": data,
        "template": theme,
        "year": datetime.now().year,
        "css": load_template_css(theme),
        "is_static": True  # Flag for navbar.html
    }

    # List of portfolio pages
    pages = ["home", "skills", "projects", "experience", "education", "certificates", "languages"]

    # Generate all pages
    for page in pages:
        rendered = env.get_template(f"{theme}/{page}.html").render(**ctx)
        with open(os.path.join(GENERATED_FOLDER, f"{page}.html"), "w", encoding="utf-8") as f:
            f.write(rendered)

    session["latest_portfolio_folder"] = GENERATED_FOLDER

    # Create ZIP of generated portfolio
    zip_path = os.path.join(ZIP_FOLDER, "portfolio.zip")
    with zipfile.ZipFile(zip_path, "w") as z:
        for page in pages:
            z.write(os.path.join(GENERATED_FOLDER, f"{page}.html"), arcname=f"{page}.html")
        if photo_filename:
            z.write(os.path.join(GENERATED_FOLDER, photo_filename), arcname=photo_filename)
        return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Portfolio Created</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {{
      margin: 0;
      overflow: hidden;
      position: relative;
      background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
      height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    /* Floating colorful circles */
    .background-circles {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      z-index: 0;
    }}

    .background-circles span {{
      position: absolute;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(255,255,255,0.4), rgba(255,255,255,0));
      box-shadow: 0 0 15px rgba(255, 255, 255, 0.3);
      animation: float 18s linear infinite;
    }}

    @keyframes float {{
      0% {{
        transform: translateY(100vh) scale(0.5);
        opacity: 0;
      }}
      50% {{
        opacity: 0.7;
      }}
      100% {{
        transform: translateY(-100vh) scale(1);
        opacity: 0;
      }}
    }}

    .background-circles span:nth-child(1) {{
      width: 100px;
      height: 100px;
      left: 20%;
      animation-delay: 0s;
      background: rgba(255, 99, 132, 0.3);
    }}
    .background-circles span:nth-child(2) {{
      width: 60px;
      height: 60px;
      left: 70%;
      animation-delay: 3s;
      background: rgba(54, 162, 235, 0.3);
    }}
    .background-circles span:nth-child(3) {{
      width: 120px;
      height: 120px;
      left: 40%;
      animation-delay: 6s;
      background: rgba(255, 206, 86, 0.3);
    }}
    .background-circles span:nth-child(4) {{
      width: 80px;
      height: 80px;
      left: 90%;
      animation-delay: 1.5s;
      background: rgba(75, 192, 192, 0.3);
    }}
    .background-circles span:nth-child(5) {{
      width: 50px;
      height: 50px;
      left: 10%;
      animation-delay: 4s;
      background: rgba(153, 102, 255, 0.3);
    }}

    /* KRIVI AI Logo */
    .brand-header {{
      position: absolute;
      top: 20px;
      right: 30px;
      z-index: 10;
      display: flex;
      align-items: center;
      font-size: 28px;
      font-weight: bold;
      color: #ffffff;
      text-shadow: 0 0 10px #00ffe0, 0 0 20px #00ffe0;
      font-family: 'Orbitron', sans-serif;
    }}

    .card {{
      position: relative;
      z-index: 1;
      background: rgba(255, 255, 255, 0.1);
      box-shadow: 0 0 25px rgba(255, 255, 255, 0.2);
      border: none;
      color: white;
    }}
  </style>
  <!-- Orbitron sci-fi font -->
  <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&display=swap" rel="stylesheet">
</head>
<body>

  <!-- Animated Background -->
  <div class="background-circles">
    <span></span><span></span><span></span><span></span><span></span>
  </div>

  <!-- KRIVI AI Branding -->
  <div class="brand-header">KRIVI AI</div>

  <!-- Main Card -->
  <div class="card p-4 text-center">
    <h3 class="mb-3">✅ Portfolio Ready</h3>
    <a class="btn btn-success m-2" href="/portfolio/home.html" target="_blank">🌌 View Portfolio</a>
    <a class="btn btn-outline-success m-2" href="/download/portfolio.zip">📦 Download ZIP</a>

    <form action="/push-to-github" method="get" class="m-2">
      <button type="submit" class="btn btn-outline-primary">🚀 Push Portfolio to GitHub</button>
    </form>

    <hr>
    <h5 class="mt-3">Need the cleaned résumé?</h5>
    <a class="btn btn-secondary m-1" href="/download_cleaned">📝 TXT</a>
    <a class="btn btn-secondary m-1" href="/download_cleaned_pdf">📄 PDF</a>
  </div>

</body>
</html>
"""

# ─────────────────────────  DOWNLOAD ROUTES  ─────────────────────────
@app.route("/download_cleaned")
def download_cleaned():
    path = os.path.join(UPLOAD_FOLDER, "cleaned_resume.txt")
    if not os.path.exists(path):
        return "Cleaned file not found.", 404
    return send_from_directory(UPLOAD_FOLDER, "cleaned_resume.txt", as_attachment=True)

@app.route("/download_cleaned_pdf")
def download_cleaned_pdf():
    path = os.path.join(UPLOAD_FOLDER, "cleaned_resume.pdf")
    if not os.path.exists(path):
        return "Cleaned PDF not found.", 404
    return send_from_directory(UPLOAD_FOLDER, "cleaned_resume.pdf", as_attachment=True)

# ─────────────────────  STATIC / PREVIEW ROUTES  ─────────────────────
@app.route("/portfolio/<path:filename>")
def serve_portfolio(filename):
    return send_from_directory(GENERATED_FOLDER, filename)
from flask import request, redirect, flash
from flask_mail import Message

@app.route('/send_request', methods=['POST'])
def send_request():
    name = request.form['name']
    email = request.form['email']
    reason = request.form['reason']
    project = request.form['project']

    msg = Message(subject=f"Access Request: {project}",
                  sender=app.config['MAIL_USERNAME'],
                  recipients=["vigoenterprises8@gmail.com"])
    
    msg.body = f"""
    New access request received.

    Project Domain: {project}
    Name: {name}
    Email: {email}
    Reason: {reason}

    Please review and reply manually if you approve.
    """

    mail.send(msg)
    flash('Request sent successfully! You will get an email if approved.', 'success')
    return redirect('/project-bank')


@app.route("/static_tpl/<theme>/<path:filename>")
def serve_theme_static(theme, filename):
    return send_from_directory(os.path.join(TEMPLATES_FOLDER, theme, "static"), filename)
from flask import Flask, render_template, request, redirect, url_for, flash, session
# ... other imports ...

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username')
        password = request.form.get('password')

        # Case 1: Admin Login
        if username_or_email == 'admin' and password == 'admin123':
            flash("Admin Login Successful ✅", "success")
            session['user'] = username_or_email
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard.html'))

        # Case 2: Registered user login
        users = load_users()
        if username_or_email in users and users[username_or_email]["password"] == password:
            flash("Login Successful ✅", "success")
            session['user'] = username_or_email
            session['is_admin'] = False
            return redirect(url_for('dashboard.html'))

        # Case 3: Not found
        flash("❌ Account not found or wrong password. Please register.", "danger")
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/jobs')
def job_board():
    import requests
    from bs4 import BeautifulSoup

    # Example: RemoteOK scraping
    url = "https://remoteok.com/remote-dev-jobs"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    jobs = []
    for div in soup.find_all('tr', class_='job'):
        title = div.find('h2')
        company = div.find('h3')
        link = div.get('data-href')
        if title and company:
            jobs.append({
                'title': title.text.strip(),
                'company': company.text.strip(),
                'link': 'https://remoteok.com' + link if link else '#'
            })

    return render_template('job_board.html', jobs=jobs)



@app.route('/resume-analyzer', methods=['GET', 'POST'])
def resume_analyzer():
    if request.method == 'POST':
        file = request.files['resume']
        resume_path = os.path.join("uploads", file.filename)
        file.save(resume_path)

        score, data = score_resume(resume_path)

        improved_path = resume_path.replace(".pdf", "_improved.docx")
        improve_resume(resume_path, improved_path, data)

        return render_template("analyze_result.html",
                               original_score=score,
                               resume_path=resume_path,
                               improved_path=improved_path)
    return render_template("resume_upload.html")
@app.route('/resume-builder')
def resume_builder():
    return render_template('resume_builder.html')  # or your actual filename


@app.route('/generate_resume', methods=['POST'])
def generate_resume():
    uploaded_file = request.files['resume_file']
    if uploaded_file:
        filename = secure_filename(uploaded_file.filename)
        filepath = os.path.join('static/uploads', filename)
        uploaded_file.save(filepath)

        # Dummy original and improved scores
        original_score = random.randint(40, 70)
        improved_score = original_score + random.randint(10, 25)

        # Dummy improved resume generation
        improved_filename = "improved_" + filename
        improved_path = os.path.join("static/generated", improved_filename)
        with open(improved_path, 'w') as f:
            f.write("This is an improved resume content...")  # Replace with real resume logic

        return render_template("resume_result.html",
                               filename=filename,
                               score=original_score,
                               improved_filename=improved_filename,
                               improved_score=improved_score)
    return "No file uploaded", 400


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        users = load_users()
        if email in users:
            return "❌ User already exists.", 400
        users[email] = {"password": password}
        save_users(users)
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))
@app.route("/github/login")
def github_login():
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&scope=read:user user:email repo"
    )
    return redirect(github_auth_url)
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash("Please log in first ❗", "warning")
        return redirect(url_for('login'))
    return render_template('dashboard.html')


@app.route("/github/callback")
def github_callback():
    code = request.args.get("code")
    if not code:
        return "❌ GitHub login failed (no code returned)."

    # Exchange code for access token
    token_res = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
        },
    )

    token_data = token_res.json()
    access_token = token_data.get("access_token")
    if not access_token:
        return "❌ Failed to get access token from GitHub."

    # Get user info using the token
    user_info = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"token {access_token}"}
    ).json()

    # Get verified email
    email_info = requests.get(
        "https://api.github.com/user/emails",
        headers={"Authorization": f"token {access_token}"}
    ).json()

    email = None
    for e in email_info:
        if e.get("primary") and e.get("verified"):
            email = e.get("email")
            break

    if not email:
        return "❌ Could not get a verified email from GitHub."

    # ✅ Store GitHub user info in session
    session["user"] = email
    session["github_token"] = access_token
    session["github_username"] = user_info.get("login")
    session["github_name"] = user_info.get("name") or user_info.get("login")

    # ✅ Auto-register GitHub users if not present
    users = load_users()
    if email not in users:
        users[email] = {
            "name": session["github_name"],
            "password": None,
            "role": "user",
            "resumes": []
        }
        save_users(users)

    # ✅ FINAL RETURN — don't forget this
    return redirect(url_for("dashboard"))


   

@app.route("/push-to-github")

def push_to_github():
    token = session.get("github_token")
    username = session.get("github_username")
    folder = session.get("latest_portfolio_folder")

    if not token or not folder or not os.path.exists(folder):
        return "❌ You're not logged in with GitHub or no portfolio found."

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    # Unique repo name with timestamp
    repo_name = f"portfolio-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Step 1: Create the repository
    create_repo = requests.post(
        "https://api.github.com/user/repos",
        headers=headers,
        json={
            "name": repo_name,
            "description": "Portfolio created by AutoPortfolio",
            "private": False
        }
    )

    if create_repo.status_code != 201:
        return f"❌ Repo creation failed: {create_repo.json()}"

    # Step 2: Push each file in the generated portfolio folder
    for root, _, files in os.walk(folder):
        for file in files:
            local_path = os.path.join(root, file)
            rel_path = os.path.relpath(local_path, folder)
            with open(local_path, "rb") as f:
                content = base64.b64encode(f.read()).decode()

            upload = requests.put(
                f"https://api.github.com/repos/{username}/{repo_name}/contents/{rel_path}",
                headers=headers,
                json={
                    "message": f"Add {rel_path}",
                    "content": content
                }
            )

            if upload.status_code not in [200, 201]:
                return f"❌ Failed to push {rel_path}: {upload.json()}"

    # ✅ Return success page with repo link
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>KRIVI AI | Success</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      font-family: 'Segoe UI', sans-serif;
      background: #0f0f0f;
      color: #fff;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      position: relative;
      z-index: 1;
    }}

    .branding {{
      position: absolute;
      top: 20px;
      right: 40px;
      font-size: 28px;
      font-weight: bold;
      color: white;
      letter-spacing: 1px;
      z-index: 2;
    }}

    h2 {{
      font-size: 30px;
      background: linear-gradient(to right, #00c3ff, #ffff1c);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      animation: pulse 2s infinite;
    }}

    a {{
      text-decoration: none;
      padding: 12px 24px;
      margin: 10px;
      border-radius: 8px;
      background: #1f1f1f;
      color: #fff;
      border: 1px solid #555;
      font-size: 18px;
      transition: all 0.3s ease;
    }}

    a:hover {{
      background: #00c3ff;
      color: black;
      transform: scale(1.05);
    }}

    @keyframes pulse {{
      0% {{ opacity: 1; }}
      50% {{ opacity: 0.7; }}
      100% {{ opacity: 1; }}
    }}

    .sphere {{
      position: absolute;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.2);
      animation: float 12s infinite ease-in-out;
      z-index: 0;
    }}

    .sphere:nth-child(1) {{
      width: 120px; height: 120px;
      top: 10%; left: 15%;
      animation-duration: 14s;
    }}

    .sphere:nth-child(2) {{
      width: 200px; height: 200px;
      bottom: 20%; right: 10%;
      animation-duration: 18s;
    }}

    .sphere:nth-child(3) {{
      width: 80px; height: 80px;
      top: 60%; left: 60%;
      animation-duration: 16s;
    }}

    @keyframes float {{
      0% {{ transform: translateY(0px) rotate(0deg); }}
      50% {{ transform: translateY(-30px) rotate(180deg); }}
      100% {{ transform: translateY(0px) rotate(360deg); }}
    }}
  </style>
</head>
<body>
  <div class="branding">KRIVI AI</div>
  <h2>✅ Portfolio successfully pushed to GitHub!</h2>
  <a href="https://github.com/{username}/{repo_name}" target="_blank">🔗 View Repository</a><br>
  <a href="/">🔙 Back to Home</a>

  <!-- Background spheres -->
  <div class="sphere"></div>
  <div class="sphere"></div>
  <div class="sphere"></div>
</body>
</html>
"""
@app.route("/project-bank")
def project_bank():
    return render_template("project_bank/project_bank.html")



@app.route("/github/full_logout")
def github_full_logout():
    session.clear()
    return redirect("https://github.com/logout")



# ────────────── MULTIPAGE VIEWS FOR GALAXY TEMPLATE ──────────────
@app.route('/')
def home():
    data = get_parsed_data()
    return render_template(f'{current_theme()}/home.html', data=data)

@app.route('/skills')
def skills():
    data = get_parsed_data()
    return render_template(f'{current_theme()}/skills.html', data=data)

@app.route('/projects')
def projects():
    data = get_parsed_data()
    return render_template(f'{current_theme()}/projects.html', data=data)

@app.route('/experience')
def experience():
    data = get_parsed_data()
    return render_template(f'{current_theme()}/experience.html', data=data)

@app.route('/education')
def education():
    data = get_parsed_data()
    return render_template(f'{current_theme()}/education.html', data=data)

@app.route('/certificates')
def certificates():
    data = get_parsed_data()
    return render_template(f'{current_theme()}/certificates.html', data=data)

@app.route('/languages')
def languages():
    data = get_parsed_data()
    return render_template(f'{current_theme()}/languages.html', data=data)



@app.route('/')
def home_04():
    data = get_parsed_data()
    return render_template('template_04/home.html', data=data)

@app.route('/skills')
def skills_04():
    if current_theme() != "template_04":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_04/skills.html', data=data)

@app.route('/projects')
def projects_04():
    if current_theme() != "template_04":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_04/projects.html', data=data)

@app.route('/experience')
def experience_04():
    if current_theme() != "template_04":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_04/experience.html', data=data)

@app.route('/education')
def education_04():
    if current_theme() != "template_04":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_04/education.html', data=data)

@app.route('/certificates')
def certificates_04():
    if current_theme() != "template_04":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_04/certificates.html', data=data)

@app.route('/languages')
def languages_04():
    if current_theme() != "template_04":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_04/languages.html', data=data)
@app.route('/')
def home_03():
    data = get_parsed_data()
    return render_template('template_03/home.html', data=data)

@app.route('/skills')
def skills_03():
    if current_theme() != "template_03":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_03/skills.html', data=data)

@app.route('/projects')
def projects_03():
    if current_theme() != "template_03":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_03/projects.html', data=data)

@app.route('/experience')
def experience_03():
    if current_theme() != "template_03":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_03/experience.html', data=data)

@app.route('/education')
def education_03():
    if current_theme() != "template_03":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_03/education.html', data=data)

@app.route('/certificates')
def certificates_03():
    if current_theme() != "template_03":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_03/certificates.html', data=data)

@app.route('/languages')
def languages_03():
    if current_theme() != "template_03":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_03/languages.html', data=data)

@app.route('/')
def home_02():
    data = get_parsed_data()
    return render_template('template_02/home.html', data=data)

@app.route('/skills')
def skills_02():
    if current_theme() != "template_02":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_02/skills.html', data=data)

@app.route('/projects')
def projects_02():
    if current_theme() != "template_02":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_02/projects.html', data=data)

@app.route('/experience')
def experience_02():
    if current_theme() != "template_02":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_02/experience.html', data=data)

@app.route('/education')
def education_02():
    if current_theme() != "template_02":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_02/education.html', data=data)

@app.route('/certificates')
def certificates_02():
    if current_theme() != "template_02":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_02/certificates.html', data=data)

@app.route('/languages')
def languages_02():
    if current_theme() != "template_02":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_02/languages.html', data=data)


@app.route('/')
def home_01():
    data = get_parsed_data()
    return render_template('template_01/home.html', data=data)

@app.route('/skills')
def skills_01():
    if current_theme() != "template_01":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_01/skills.html', data=data)

@app.route('/projects')
def projects_01():
    if current_theme() != "template_01":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_01/projects.html', data=data)

@app.route('/experience')
def experience_01():
    if current_theme() != "template_01":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_01/experience.html', data=data)

@app.route('/education')
def education_01():
    if current_theme() != "template_01":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_01/education.html', data=data)

@app.route('/certificates')
def certificates_01():
    if current_theme() != "template_01":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_01/certificates.html', data=data)

@app.route('/languages')
def languages_01():
    if current_theme() != "template_01":
        return redirect(url_for("home"))
    data = get_parsed_data()
    return render_template('template_01/languages.html', data=data)




def render_galaxy(section):
    data = session.get("parsed_data")

    if not data:
        path = os.path.join(UPLOAD_FOLDER, "cleaned_resume.txt")
        if not os.path.exists(path):
            return redirect("/")
        with open(path, encoding="utf-8") as fh:
            cleaned_text = fh.read()
        data = parse_resume_text(cleaned_text)

    photo_path = os.path.join(GENERATED_FOLDER, "profile.jpg")
    data["photo"] = "profile.jpg" if os.path.exists(photo_path) else None

    return render_template(f"template_05/{section}.html", data=data)

if __name__ == "__main__":
    app.run(debug=True)
