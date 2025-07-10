# zip_generator.py
import os
import shutil
import zipfile

def generate_zip(output_dir="output_portfolio", html_file="index.html", resume_file="resume.pdf"):
    os.makedirs(output_dir, exist_ok=True)

    # Copy HTML
    shutil.copy(html_file, os.path.join(output_dir, "index.html"))

    # Copy resume
    if os.path.exists(resume_file):
        shutil.copy(resume_file, os.path.join(output_dir, "resume.pdf"))
    else:
        print("⚠️ Resume file not found. Skipping resume copy.")

    # Create zip file
    zip_filename = output_dir + ".zip"
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_dir)
                zipf.write(file_path, arcname)

    print(f"✅ Portfolio ZIP generated: {zip_filename}")

if __name__ == "__main__":
    generate_zip()
