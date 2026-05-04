# PCU Attendance System

Web-based lecture attendance system for Precious Cornerstone University. Lecturers display a **dynamic QR code** that rotates after every successful scan, and students mark themselves present by scanning + a server-side **face match**.

## Features

- Three privileged roles: `admin`, `lecturer`, `course_rep`. Plus `student`.
- Student self-registration with one-time live face capture (encoded with `face_recognition`).
- Lecturer dashboard: create lectures, start lectures, show rotating QR, end lectures.
- One-shot QR tokens — every successful scan immediately invalidates the current code and the lecturer's screen rotates within ~1 second.
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
templates/        # Django templates
static/           # JS + CSS
```

## Setup (Windows)

> **Note on `face_recognition` / `dlib`** — `face_recognition` depends on `dlib`, which compiles native code. On Windows the cleanest path is to install a prebuilt wheel (`dlib-bin`).

```powershell
# 1. Create + activate a virtualenv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dlib via prebuilt wheel (saves you from needing CMake + MSVC build tools)
pip install dlib-bin

# 3. Install the rest
pip install -r requirements.txt

# 4. Migrate DB and create the admin user
python manage.py migrate
python manage.py createsuperuser   # role defaults to "admin" via Django admin

# 5. Run the dev server (bind 0.0.0.0 so phones on your LAN can reach it)
python manage.py runserver 0.0.0.0:8000
```

If `pip install dlib-bin` fails, fall back to compiling from source: install **CMake** and **Visual Studio Build Tools (Desktop development with C++)**, then `pip install dlib face_recognition`.

## First run

1. Visit `http://localhost:8000/admin/` and log in as the superuser you created.
2. Edit your superuser, set role = `admin` (it should already be set if you used `createsuperuser` — otherwise change via the Role panel).
3. Add a couple of users with role = `lecturer`. Then create a `Course` and assign one of those lecturers.
4. Visit `/auth/register/student/` (in a normal browser tab) and register one or two students. The face capture happens in-browser.
5. Sign in as a student → enroll in the course at `/courses/`.
6. Sign in as the lecturer → "+ Create lecture" → fill in start/end times → click "Start lecture". A live QR will appear.
7. On a second device (or another browser tab on the same machine), sign in as the student → click "Scan to mark attendance" → point camera at the lecturer's QR → take a selfie. After verification you'll see "Attendance marked" and the lecturer's QR will rotate.
8. Try scanning the **old** QR (e.g. from a screenshot you took before rotation). It will be rejected with "code expired".

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
