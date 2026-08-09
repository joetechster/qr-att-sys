# PCU Attendance System

Web-based lecture attendance system for Precious Cornerstone University. Lecturers display a **dynamic QR code** that rotates after every successful scan, and students mark themselves present by scanning + a server-side **face match**.

## Features

- Roles: `admin`, `hod`, `lecturer`, `course_rep`, `student`.
- Student self-registration with one-time live face capture (encoded with `face_recognition`).
- HOD console: owns the course catalogue, provisions lecturer accounts (with generated temporary passwords), bulk-imports lecturers and courses from CSV, and reviews student complaints.
- Lecturer dashboard: schedule lectures against assigned courses, start lectures, show rotating QR, end lectures.
- Staff accounts created with a temporary password are locked to the password-change page until they set their own.
- Personal profile page for every role at `/auth/profile/`.
- One-shot QR tokens — every successful scan immediately invalidates the current code and the lecturer's screen rotates within ~1 second. A successful scan returns the student to their dashboard.
- Course enrollment required for attendance.
- Server-side face match (Euclidean distance < 0.6 by default).
- Centralized SQLite database with full Django admin.

## Project layout

```
attendance_sys/   # project settings + URL conf
apps/
  accounts/       # User, StudentProfile, registration with face capture
  courses/        # Course, Enrollment
  lectures/       # Lecture, QRToken, rotating QR display
  attendance/     # AttendanceRecord, scan + verify endpoint
  complaints/     # Complaint, student submission + HOD review
  hod/            # HOD console: lecturer accounts + CSV imports (no models)
templates/        # Django templates
static/           # JS + CSS
```

## Setup (Windows)

> **Note on `face_recognition` / `dlib`** — `face_recognition` depends on `dlib`, which compiles native code. On Windows the cleanest path is to install a prebuilt wheel (`dlib-bin`).

```powershell
# 1. Create + activate a virtualenv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install the face-recognition stack without compiling dlib
pip install --no-deps -r requirements-face.txt

# 3. Install the rest
pip install -r requirements.txt

# 4. Migrate DB and create the admin user
python manage.py makemigrations accounts
python manage.py makemigrations attendance
python manage.py makemigrations courses
python manage.py makemigrations lectures
python manage.py migrate
python manage.py createsuperuser   # role defaults to "admin" via Django admin

# 5. Run the dev server (bind 0.0.0.0 so phones on your LAN can reach it)
python manage.py runserver 0.0.0.0:8000
```

The `--no-deps` flag is critical: `face_recognition`'s metadata asks pip for the source `dlib` package, which triggers a Visual Studio C++ build error. `dlib-bin` provides the same compiled module under a different distribution name, so we install it ourselves and tell pip not to resolve `face_recognition`'s deps. If `pip install dlib-bin` fails, fall back to compiling from source: install **CMake** and **Visual Studio Build Tools (Desktop development with C++)**, then `pip install dlib face_recognition`.

## First run

1. Visit `http://localhost:8000/admin/` and log in as the superuser you created.
2. Add one user with role = `hod`, and give them a password. Everything below is done from the app, not the admin.
3. Sign in as the HOD at `/auth/login/` → `/hod/`.
   - **New lecturer** creates one account and shows its temporary password once — write it down.
   - **Import lecturers (CSV)** does the same in bulk; the result table lists every generated password.
   - **New course** (or **Import courses (CSV)**) adds courses and assigns each to a lecturer.
4. Sign in as a lecturer with the temporary password. You'll be held on the password-change page until you set your own.
5. Visit `/auth/register/student/` (in a normal browser tab) and register one or two students. The face capture happens in-browser.
6. Sign in as a student → enroll in the course at `/courses/`.
7. Sign in as the lecturer → "Create lecture" → pick one of your assigned courses, fill in start/end times → click "Start lecture". A live QR will appear.
8. On a second device (or another browser tab on the same machine), sign in as the student → "Scan" → point camera at the lecturer's QR → take a selfie. After verification you land back on the student dashboard with "Attendance marked", and the lecturer's QR rotates.
9. Try scanning the **old** QR (e.g. from a screenshot you took before rotation). It will be rejected with "code expired".

### CSV formats

```csv
# lecturers — required: username, first_name, last_name; optional: email, password
username,first_name,last_name,email
j.adeyemi,Jumoke,Adeyemi,j.adeyemi@pcu.edu.ng

# courses — required: code, title, department, lecturer_username; optional: course_rep_username
code,title,department,lecturer_username
CSC301,Intro to Compilers,Computer Science,j.adeyemi
```

Rows whose key already exists are **skipped**, not errored, so a corrected file can be re-uploaded safely.

## Tests

```powershell
python manage.py test
```

## HTTPS / Camera access from phones

Browsers only allow `getUserMedia` (camera) on **HTTPS** or **localhost**. To test from a phone on the same Wi-Fi:

- **Easy option**: open the site on the lecturer's machine via `http://localhost:8000/` (camera works), and have students scan from the same machine via a second browser. Demo-friendly.
- **Real LAN option**: run via HTTPS. Easiest is `mkcert`:
  ```powershell
  choco install mkcert
  mkcert -install
  mkcert <your-lan-ip>
  pip install django-extensions Werkzeug pyOpenSSL
  # add 'django_extensions' to INSTALLED_APPS, then:
  python manage.py runserver_plus 0.0.0.0:8000 --cert-file <your-lan-ip>.pem --key-file <your-lan-ip>-key.pem
  ```
- Or tunnel via `ngrok http 8000` — gives you HTTPS for free.

## How the dynamic QR works

`Lecture` has many `QRToken`s, but the invariant is **at most one is unused at any time** — that's the "current" code. The lecturer's `/lecturer/lecture/<id>/qr/` page polls `/lectures/<id>/qr/current/` once per second and redraws the QR whenever the token changes. The QR encodes a deep link like `http://<host>:8000/scan/?t=<uuid>` so a student can scan with the system camera or our in-app scanner.

`/scan/verify/` runs every request inside a `transaction.atomic()` with `SELECT … FOR UPDATE` on the token row, so concurrent scans race-safely yield exactly one winner. After a successful match it marks the token used and creates a fresh one — and the lecturer's screen picks up the new token on its next poll.

## Configuration

In `attendance_sys/settings.py`:

- `FACE_MATCH_THRESHOLD` (default `0.6`) — Euclidean distance threshold between encodings. Lower is stricter.
- `MEDIA_ROOT` — where face reference images are stored (`media/faces/...`).
- `TIME_ZONE` — defaults to `Africa/Lagos`.

## Out of scope (per the project chapter)

- Mobile app development (web only).
- Advanced biometric hardware (we use the device camera).
- Payroll / grading / analytics.
