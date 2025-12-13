```
SEAT ALLOCATION SYSTEM - PROJECT STRUCTURE & FLOWCHART
=====================================================

┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                            │
│                   Port: 3000 (npm start)                            │
└─────────────────────────────────────────────────────────────────────┘

Frontend/
├── public/
│   ├── index.html
│   ├── manifest.json
│   └── robots.txt
│
├── src/
│   ├── index.js                 # Entry point
│   ├── App.jsx                  # Main router/page manager
│   ├── App.css
│   ├── index.css
│   │
│   ├── context/
│   │   └── AuthContext.jsx      # Auth state & API calls
│   │       ├── login()
│   │       ├── signup()
│   │       ├── logout()
│   │       ├── getProfile()
│   │       └── updateProfile()
│   │
│   ├── components/
│   │   ├── Navbar.jsx           # Navigation bar (with logout)
│   │   ├── Footer.jsx           # Footer component
│   │   └── Toast.jsx            # Toast notifications
│   │
│   └── pages/
│       ├── LandingPage.jsx      # Home page
│       ├── LoginPage.jsx        # Login form → calls /api/auth/login
│       ├── SignupPage.jsx       # Signup form → calls /api/auth/signup
│       ├── ProfilePage.jsx      # User profile → calls /api/auth/profile
│       ├── DashboardPage.jsx    # Dashboard
│       ├── UploadPage.jsx       # Student data upload
│       ├── LayoutPage.jsx       # Seat layout visualization
│       └── LayoutPage.jsx
│
└── package.json


┌─────────────────────────────────────────────────────────────────────┐
│                      BACKEND (Flask/Python)                         │
│                   Port: 5000 (python app.py)                        │
└─────────────────────────────────────────────────────────────────────┘

algo/
├── app.py                       # Flask app with all endpoints
├── algo.py                      # Seating algorithm
├── index.html                   # Web UI template
├── main.py                      # Additional script
├── requirements.txt             # Dependencies
│
└── __pycache__/


Backend/
├── database.py                  # SQLite database setup
│   ├── get_db()                 # Get DB connection
│   └── init_db()                # Initialize tables
│
├── auth_service.py              # Authentication service
│   ├── hash_password()          # Bcrypt hashing
│   ├── verify_password()        # Password verification
│   ├── create_access_token()    # JWT token generation
│   ├── verify_token()           # JWT verification
│   ├── signup()                 # User registration
│   ├── login()                  # User authentication
│   ├── get_user_by_token()      # Get user from token
│   └── update_user_profile()    # Update user info
│
└── auth_demo.db                 # SQLite database (auto-created)
    ├── users table
    │   ├── id (PRIMARY KEY)
    │   ├── username (UNIQUE)
    │   ├── email (UNIQUE)
    │   ├── password (hashed)
    │   ├── role (STUDENT/ADMIN/FACULTY)
    │   └── created_at
    │
    └── sessions table
        ├── id (PRIMARY KEY)
        ├── user_id (FOREIGN KEY)
        ├── token
        └── created_at


┌─────────────────────────────────────────────────────────────────────┐
│                    API ENDPOINTS & FLOW                             │
└─────────────────────────────────────────────────────────────────────┘

AUTHENTICATION ENDPOINTS:
========================

1. SIGNUP
   POST /api/auth/signup
   ├─ Frontend: SignupPage.jsx sends (username, email, password, role)
   ├─ Backend: auth_service.signup() validates & stores in DB
   ├─ Response: { success, message }
   └─ Flow: Signup → Login Page

2. LOGIN
   POST /api/auth/login
   ├─ Frontend: LoginPage.jsx sends (email, password)
   ├─ Backend: auth_service.login() validates credentials
   ├─ Response: { success, token, user }
   ├─ Frontend: Stores token & user in localStorage
   └─ Flow: Login → Dashboard

3. GET PROFILE (Protected)
   GET /api/auth/profile
   ├─ Frontend: ProfilePage.jsx requests user data
   ├─ Header: Authorization: Bearer <token>
   ├─ Backend: Verifies token, returns user data
   └─ Response: { success, user }

4. UPDATE PROFILE (Protected)
   PUT /api/auth/profile
   ├─ Frontend: ProfilePage.jsx sends updated (username, email)
   ├─ Header: Authorization: Bearer <token>
   ├─ Backend: auth_service.update_user_profile()
   └─ Response: { success, message, user }

5. LOGOUT
   POST /api/auth/logout
   ├─ Frontend: Clears token & user from localStorage
   ├─ Response: { success, message }
   └─ Flow: Redirect to Landing Page

SEATING ALGORITHM ENDPOINTS:
============================

POST /api/generate-seating
├─ Receives: rows, cols, num_batches, broken_seats, etc.
├─ Algorithm: SeatingAlgorithm.generate_seating()
└─ Returns: Seating arrangement + validation


┌─────────────────────────────────────────────────────────────────────┐
│                    USER AUTHENTICATION FLOW                         │
└─────────────────────────────────────────────────────────────────────┘

SIGNUP FLOW:
============
SignupPage (React)
    ↓
    └─ User enters: username, email, password, role
    └─ Validation: password length ≥ 6, match confirmation
    ↓
POST /api/auth/signup
    ↓
Backend: auth_service.signup()
    ├─ Check if user exists (username/email unique)
    ├─ Hash password with bcrypt
    ├─ Store in users table
    └─ Return { success, message }
    ↓
Frontend: Show toast "Account created successfully"
    ↓
Redirect to LoginPage


LOGIN FLOW:
===========
LoginPage (React)
    ↓
    └─ User enters: email, password
    ↓
POST /api/auth/login
    ↓
Backend: auth_service.login()
    ├─ Find user by email
    ├─ Verify password with bcrypt
    ├─ Create JWT token (7 days expiry)
    ├─ Create session record
    └─ Return { success, token, user }
    ↓
Frontend:
    ├─ localStorage.setItem('token', token)
    ├─ localStorage.setItem('user', user_data)
    └─ Set AuthContext user state
    ↓
Show toast "Login successful"
    ↓
Redirect to Dashboard


PROFILE FLOW:
=============
ProfilePage (React)
    ↓
useEffect → getProfile()
    ↓
GET /api/auth/profile
    ├─ Header: Authorization: Bearer <token>
    ↓
Backend: token_required() middleware
    ├─ Extract token from header
    ├─ Verify JWT signature & expiry
    ├─ Get user_id from payload
    └─ Allow request or return 401
    ↓
Backend: get_user_by_token()
    └─ Fetch user from database
    ↓
Return { success, user }
    ↓
Frontend: Display user profile
    ├─ Name: user.name
    ├─ Email: user.email
    ├─ Role: user.role
    └─ Recent activities (mock data)


LOGOUT FLOW:
============
ProfilePage or Navbar
    ↓
    └─ User clicks "Logout"
    ↓
AuthContext.logout()
    ├─ localStorage.removeItem('token')
    ├─ localStorage.removeItem('user')
    └─ setUser(null)
    ↓
POST /api/auth/logout
    └─ Server-side cleanup (optional)
    ↓
Frontend: Show toast "Logged out successfully"
    ↓
Redirect to Landing Page


EDIT PROFILE FLOW:
==================
ProfilePage (React)
    ↓
    └─ Click "Edit Profile" button
    └─ Update form fields
    └─ Click "Save"
    ↓
PUT /api/auth/profile
    ├─ Header: Authorization: Bearer <token>
    ├─ Body: { username, email }
    ↓
Backend: token_required() middleware ✓
    ↓
Backend: update_user_profile(user_id, username, email)
    ├─ Update users table
    └─ Return { success, message }
    ↓
Frontend:
    ├─ Update localStorage user data
    ├─ Update AuthContext user state
    └─ Show toast "Profile updated successfully"
    ↓
Exit edit mode & display new data


┌─────────────────────────────────────────────────────────────────────┐
│                    SECURITY ARCHITECTURE                            │
└─────────────────────────────────────────────────────────────────────┘

PASSWORD SECURITY:
==================
User Input → bcrypt.hashpw() → salt + hash → stored in DB
Login: plaintext → bcrypt.checkpw() → verify against stored hash

TOKEN SECURITY:
===============
JWT Payload: { user_id, email, username, exp, iat }
Signing: HMAC-SHA256(payload, SECRET_KEY)
Token: Header.Payload.Signature

Protected Routes:
├─ GET /api/auth/profile    → @token_required
├─ PUT /api/auth/profile    → @token_required
└─ Other endpoints: (add @token_required as needed)

Token Expiry: 7 days
Storage: localStorage (secure from XSS in this setup)


┌─────────────────────────────────────────────────────────────────────┐
│                    DEPENDENCIES & VERSIONS                          │
└─────────────────────────────────────────────────────────────────────┘

BACKEND (Python):
=================
Flask >= 2.0.0              # Web framework
flask-cors >= 3.0.0         # CORS support
bcrypt >= 4.0.0             # Password hashing
PyJWT >= 2.6.0              # JWT tokens
sqlite3 (built-in)          # Database

FRONTEND (Node.js):
===================
react: ^19.2.0              # UI framework
react-dom: ^19.2.0          # React rendering
lucide-react: ^0.552.0      # Icons
react-scripts: 5.0.1        # Build tool


┌─────────────────────────────────────────────────────────────────────┐
│                    STARTUP SEQUENCE                                 │
└─────────────────────────────────────────────────────────────────────┘

Terminal 1 (Backend):
=====================
$ cd algo
$ pip install -r requirements.txt
$ python database.py        # Creates auth_demo.db with tables
$ python app.py             # Starts Flask on localhost:5000

Terminal 2 (Frontend):
=====================
$ cd Frontend
$ npm install               # Install React dependencies
$ npm start                 # Starts React on localhost:3000

Browser:
========
Open http://localhost:3000
├─ Landing Page → Signup/Login
├─ Signup → Create account → Redirect to Login
├─ Login → Verify with backend → Redirect to Dashboard
├─ Dashboard → Available pages
├─ Profile → Load user data from /api/auth/profile
└─ Logout → Clear token → Redirect to Landing


┌─────────────────────────────────────────────────────────────────────┐
│                    KEY FILES REFERENCE                              │
└─────────────────────────────────────────────────────────────────────┘

CRITICAL FILES:
===============
Backend/database.py         → Database initialization & connection
Backend/auth_service.py     → All auth logic
algo/app.py                 → Flask app & API endpoints
Frontend/src/context/AuthContext.jsx  → Auth state & API calls
Frontend/src/pages/LoginPage.jsx      → Login UI
Frontend/src/pages/ProfilePage.jsx    → Profile UI
Frontend/src/components/Navbar.jsx    → Navigation & logout

DATABASE:
=========
Backend/auth_demo.db        → SQLite database (auto-created)
Tables: users, sessions
```
