from typing import Any
import requests
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
import uvicorn
import time
from hashlib import md5
from loguru import logger
import json
from pathlib import Path

app = FastAPI()
cwd = Path(__file__)
template_path = cwd.parent.joinpath('templates')
students_path = cwd.parent.joinpath('students.json')
templates = Jinja2Templates(directory=template_path)
grading_period = None
HEADERS = ["Semester", "Class", "Average", "Assignment", "Assigned","Due","Grade"]

HAC_API_BASE = "http://192.168.50.121:3000/api/v1"
HAC_URL_BASE =  "https://accesscenter.roundrockisd.org"
HAC_student = "s312393"
HAC_PASSWORD = "M00sefart"
CACHE_TTL = 24*60*60*1000

BASE_REQUEST = {
  "base": HAC_URL_BASE,
  "password": HAC_PASSWORD,
  "studentname": HAC_student
}

class HACStudent:
    def __init__(self, name:str, username:str, password:str) -> None:
        self.name = name
        self.username = username
        self.password = password

# Populate the HACstudents from the students.json file
with students_path.open('r') as fh:
    data = json.load(fh)
    students = {student['name']:HACStudent(**student) for student in data}
    logger.info(f"Loaded students: {students}")


def get_student_base_payload(student: str):
    return  {
        "base": HAC_URL_BASE,
        "username": students[student].username,
        "password": students[student].password
    }

class CacheEntry:
    def __init__(self, key, data, ttl_ms) -> None:
        self.key = key
        self.data = data
        self.ttl = time.time() + ttl_ms

    def expired(self, invalidate = False) -> Any:
        if time.time() > self.ttl or invalidate:
            return True
        else:
            return False
        
cache: dict[str, CacheEntry] = {}

def post_cached(*args, **kwargs):
    key = md5(f"{args}{kwargs}".encode('utf-8')).hexdigest()
    if key in cache and not cache[key].expired():
        logger.info(f"Retrieved cache entry {key}")
        return cache[key].data
    else:
        # Don't want invalidate_cache args getting in
        logger.info(f"Key {key} not cached. Making fresh call")
        data = requests.post(*args, **kwargs).json()
        if data['err']:
            raise Exception(data['msg'])
        cache[key] = CacheEntry(key,data, CACHE_TTL)
        return data


def get_classwork(student: str, marking_periods: dict):
    payload = get_student_base_payload(student) | marking_periods
    data = post_cached(HAC_API_BASE+"/classwork", json=payload)
    return data


def get_bad_assignments(student: str):
    classwork = get_classwork(student, {"markingPeriods": [1,2,3,4]})
    
    rows = []

    # String together data about class, assignments and grade to populate rows
    for period in classwork["classwork"]:
        for class_entry in period["entries"]:
            class_name = class_entry['class']['name']
            class_avg = class_entry['average']
            for assignment in class_entry['assignments']:
                row_common = [period['sixWeeks'],class_name,class_avg,assignment['name'], assignment['assignedDate'],assignment['dueDate']]
                try:
                    grade = float(assignment['grade']) / float(assignment['totalPoints'])
                    grade = int(grade*100)
                    if grade < 50:
                        rows.append(row_common + [grade])
                except:
                    if assignment['grade'] and assignment['grade'] != 'P':
                        rows.append(row_common + [assignment['grade']])
                    if not assignment['grade']:
                        rows.append(row_common + ['Not Graded'])
    return rows
    
def most_recent_period(rows: str):
    most_recent = 0
    for row in rows:
        # Ugly, but works.
        period = row[0]
        if  period > most_recent:
            most_recent = period
    return int(most_recent)

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("table.html", {"request":request, "headers": HEADERS, "student_list": students, "grading_period": grading_period})

@app.get("/api/get_student/{student}")
def get_dataset(student: str):
    try:
        global grading_period
        rows = get_bad_assignments(student)
        if not grading_period:
            grading_period = most_recent_period(rows)
        logger.info(f"Current student changed to: {student}")
        return [r for r in rows if r[0] == grading_period]
    except Exception as e:
        logger.exception(e)
        return {f"error: {str(e)}"}

@app.post("/api/grading_period/{period}/{student}")
def set_grading_period(period: str, student: str):
    global grading_period 
    grading_period = int(period)
    logger.info(f"Grading period changed to: {grading_period}")
    return get_dataset(student)
    
@app.post("/api/clear_cache")
def clear_cache():
    global cache
    cache = {}

uvicorn.run(app, host="0.0.0.0", port=3001)
