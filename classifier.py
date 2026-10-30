"""Educational text classifier: TF-IDF + Logistic Regression with confidence estimate."""
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

TRAINING_DATA = [
    ("wifi is not working in the library", "IT & Wi-Fi"),
    ("internet connection is very slow in computer lab", "IT & Wi-Fi"),
    ("computer lab computers are not starting", "IT & Wi-Fi"),
    ("college portal login is broken", "IT & Wi-Fi"),
    ("projector is not working in classroom", "IT & Wi-Fi"),
    ("classroom fans and lights are broken", "Infrastructure"),
    ("broken desks in lecture hall", "Infrastructure"),
    ("classroom ceiling is leaking during rain", "Infrastructure"),
    ("the elevator is out of order", "Infrastructure"),
    ("library chairs and tables are damaged", "Infrastructure"),
    ("there is no water in the washroom", "Water & Sanitation"),
    ("toilets are dirty and smell bad", "Water & Sanitation"),
    ("drinking water cooler is empty", "Water & Sanitation"),
    ("garbage has not been collected", "Water & Sanitation"),
    ("washroom taps are leaking", "Water & Sanitation"),
    ("canteen food is stale and poor quality", "Canteen & Food"),
    ("the cafeteria is too expensive", "Canteen & Food"),
    ("there are insects in the food", "Canteen & Food"),
    ("canteen is not clean", "Canteen & Food"),
    ("hostel room has no hot water", "Hostel"),
    ("hostel water supply is not working", "Hostel"),
    ("hostel rooms are dirty", "Hostel"),
    ("hostel warden is not responding", "Hostel"),
    ("hostel room fan is broken", "Hostel"),
    ("college bus arrived late again", "Transport"),
    ("bus route does not cover our stop", "Transport"),
    ("college bus driver was driving dangerously", "Transport"),
    ("transport fees were charged twice", "Transport"),
    ("my scholarship form is pending in office", "Administration"),
    ("student ID card has not been issued", "Administration"),
    ("fee payment receipt is missing", "Administration"),
    ("office staff are not responding to emails", "Administration"),
    ("there is an error in my admission record", "Administration"),
    ("teacher has not uploaded assignment marks", "Academics"),
    ("exam timetable has a mistake", "Academics"),
    ("lecture was cancelled without notice", "Academics"),
    ("I have not received my exam result", "Academics"),
    ("the syllabus is not being completed", "Academics"),
    ("urgent exposed electrical wire in corridor", "Infrastructure"),
    ("smoke coming from an electrical panel", "Infrastructure"),
    ("someone is threatening students", "Other"),
    ("I want to report ragging by seniors", "Other"),
    ("lost item found in the campus", "Other"),
    ("library opening hours are too short", "Academics"),
    ("teacher changed class schedule without notice", "Academics"),
    ("wifi password is not accepted", "IT & Wi-Fi"),
    ("network disconnects every few minutes", "IT & Wi-Fi"),
    ("broken window in the classroom", "Infrastructure"),
    ("classroom projector screen is damaged", "Infrastructure"),
    ("washroom has no soap", "Water & Sanitation"),
    ("water is leaking from the ceiling", "Water & Sanitation"),
    ("food serving is delayed in the canteen", "Canteen & Food"),
    ("hostel security gate is not locking", "Hostel"),
    ("bus is overcrowded every morning", "Transport"),
    ("incorrect tuition fee on student account", "Administration"),
    ("need correction in my marksheet", "Academics"),
]

MODEL = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), lowercase=True, strip_accents="unicode")),
    ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced"))
])
MODEL.fit([x[0] for x in TRAINING_DATA], [x[1] for x in TRAINING_DATA])

HIGH_PRIORITY_TERMS = [
    "fire", "smoke", "electric shock", "exposed wire", "threat", "violence",
    "ragging", "harassment", "unsafe", "accident", "dangerous", "emergency",
    "insects in the food", "contaminated", "no drinking water"
]
MEDIUM_PRIORITY_TERMS = [
    "not working", "broken", "leaking", "dirty", "slow", "late",
    "missing", "pending", "poor quality", "no water", "out of order"
]

def classify_complaint(text):
    cleaned = text.strip()
    probabilities = MODEL.predict_proba([cleaned])[0]
    best_index = probabilities.argmax()
    category = MODEL.classes_[best_index]
    confidence = float(probabilities[best_index])
    lower = cleaned.lower()
    if any(term in lower for term in HIGH_PRIORITY_TERMS):
        priority = "High"
    elif any(term in lower for term in MEDIUM_PRIORITY_TERMS):
        priority = "Medium"
    else:
        priority = "Low"
    return category, priority, confidence
