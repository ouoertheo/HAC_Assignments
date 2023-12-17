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
templates = Jinja2Templates(directory=template_path)

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
with open("students.json",'r') as fh:
    data = json.load(fh)
    students = {student['name']:HACStudent(**student) for student in data}
    logger.info(f"Loaded students: {students}")

if students:
    current_student = list(students.values())[0]
    logger.info(f"Current student: {current_student.name}")

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
        cache[key] = CacheEntry(key,data, CACHE_TTL)
        return data


def get_classwork(student: str, marking_periods: dict):
    payload = get_student_base_payload(student) | marking_periods
    data = post_cached(HAC_API_BASE+"/classwork", json=payload)
    return data


def get_bad_assignments(student: str, marking_periods: dict):
    classwork = get_classwork(student, marking_periods)
    if classwork['err']:
        raise Exception(classwork['msg'])
    
    headers = ["Period", "Class", "Average", "Assignment","Grade"]
    rows = []

    # String together data about class, assignments and grade to populate rows
    for grading_period in classwork["classwork"]:
        period = f"Grading Period {grading_period['sixWeeks']}"
        print("Period:", grading_period['sixWeeks'])
        for class_entry in grading_period["entries"]:
            class_name = class_entry['class']['name']
            class_avg = class_entry['average']
            for assignment in class_entry['assignments']:
                row_common = [period,class_name,class_avg,assignment['name']]
                try:
                    grade = float(assignment['grade']) / float(assignment['totalPoints'])
                    grade = int(grade*100)
                    if grade < 50:
                        rows.append(row_common + [grade])
                except:
                    if assignment['grade'] == 'M':
                        rows.append(row_common + [assignment['grade']])
                    if not assignment['grade']:
                        rows.append(row_common + ['Not Graded'])
        return headers, rows

@app.get("/")
def read_root(request: Request):
    marking_periods = {"markingPeriods": [1,2]}
    headers, rows = get_bad_assignments(current_student.name, marking_periods)
    return templates.TemplateResponse("table.html", {"request": request, "headers": headers, "rows": rows, "student_list": students})

@app.get("/api/get_student/{student}")
def get_dataset(student: str):
    try:
        marking_periods = {"markingPeriods": [1,2]}
        current_student = students[student]
        logger.info(f"Current student changed to: {current_student}")
        _, rows = get_bad_assignments(current_student.name, marking_periods)
        return rows
    except Exception as e:
        logger.exception(e)
        return {f"error: {str(e)}"}
    
@app.post("/api/clear_cache")
def clear_cache():
    global cache
    cache = {}
    return

uvicorn.run(app, host="0.0.0.0", port=3001)
