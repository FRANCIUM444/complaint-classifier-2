# CampusCare Advanced — College Complaint Classifier

A Flask + SQLite mini project with text classification, an admin login, analytics charts, search/filters, CSV export, anonymous submissions, and student feedback.

## Run on Windows CMD
1. Extract the ZIP file.
2. Open CMD in the `CampusCare_Advanced` folder (the folder containing `app.py`).
3. Install dependencies:
   `python -m pip install -r requirements.txt`
4. Start the app:
   `python app.py`
5. Open `http://127.0.0.1:5000`

## Demo admin login
- Username: `admin`
- Password: `admin123`

Change these for anything beyond a local demo by setting environment variables before running:
```cmd
set ADMIN_USERNAME=youradmin
set ADMIN_PASSWORD=use-a-strong-password
set SECRET_KEY=replace-with-a-long-random-secret
python app.py
```

## Features
- Student complaint submission with optional anonymous mode
- TF-IDF + Logistic Regression category prediction
- Approximate model confidence (not a guarantee of correctness)
- Rule-based priority estimate
- SQLite storage and complaint ID tracking
- Admin login and logout
- Dashboard charts (Chart.js loaded from CDN, internet required for charts)
- Search, category, priority, status and date filters
- Complaint status updates
- CSV export for reports
- Student feedback (1–5 rating and comment) after resolution
- Automatic SMTP email forwarding to the department mapped to the predicted category
- Migration helper for the earlier version's SQLite database

## Notes and limitations
- The built-in training examples are small illustrative examples. Model confidence is not the same as validated real-world accuracy. Evaluate with a held-out labeled dataset before claiming model performance.
- Priority is estimated by simple keyword rules and must not replace direct reporting of emergencies or safety issues.
- The admin login is a simple educational demo and has no rate limiting or CSRF protection. Do not deploy publicly without security hardening.
- Email forwarding requires SMTP credentials and real department addresses configured as environment variables. If not configured, complaints are still saved and the result page reports that email is not configured.

## Configure automatic department email forwarding (Windows CMD)

Use an SMTP account approved for this project. For Gmail, use an App Password with 2-Step Verification enabled; do not use your normal account password. Replace example addresses with actual college department addresses:

```cmd
set SMTP_HOST=smtp.gmail.com
set SMTP_PORT=587
set SMTP_USERNAME=your-sending-account@gmail.com
set SMTP_PASSWORD=your-16-character-app-password
set SMTP_FROM=your-sending-account@gmail.com
set IT_EMAIL=it-department@yourcollege.edu
set ACADEMICS_EMAIL=academics@yourcollege.edu
set INFRASTRUCTURE_EMAIL=maintenance@yourcollege.edu
set SANITATION_EMAIL=facilities@yourcollege.edu
set CANTEEN_EMAIL=canteen@yourcollege.edu
set HOSTEL_EMAIL=hostel@yourcollege.edu
set TRANSPORT_EMAIL=transport@yourcollege.edu
set ADMINISTRATION_EMAIL=admin-office@yourcollege.edu
set OTHER_EMAIL=college-office@yourcollege.edu
python app.py
```

These `set` commands apply only to the current CMD window. Keep SMTP credentials private. The app records email status and recipient in the database. The predicted category can be wrong, so administrators should monitor routing and correct misclassified complaints.
- Avoid collecting sensitive student details. Anonymous submissions use a generic display name; do not enter names in the complaint text if anonymity is important.
