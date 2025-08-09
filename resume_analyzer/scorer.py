from pyresparser import ResumeParser
import os

def score_resume(file_path):
    data = ResumeParser(file_path).get_extracted_data()
    score = 0
    if data is None:
        return 0, "Resume could not be parsed"

    if data.get('skills'):
        score += 20
    if data.get('experience'):
        score += 20
    if data.get('education'):
        score += 20
    if data.get('email'):
        score += 10
    if data.get('phone'):
        score += 10
    if data.get('designation'):
        score += 10
    if data.get('degree'):
        score += 10

    return min(score, 100), data
