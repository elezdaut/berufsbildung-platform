"""
BerufsbildungGlobal - Swiss VET System Clone
Platform that replicates the Swiss dual education system for any country.
Currently configured for: North Macedonia (Maqedoni e Veriut)
"""

import os
import io
import json
import sqlite3
import uuid
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import hashlib
import secrets
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
CORS(app)

DATABASE = os.path.join(os.path.dirname(__file__), 'data', 'berufsbildung.db')
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'data', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

# ============================================================
# DATABASE SETUP
# ============================================================

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")

    db.executescript('''
    -- Users table (students, companies, schools, government)
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student', 'company', 'school', 'government')),
        full_name TEXT NOT NULL,
        phone TEXT,
        city TEXT,
        country TEXT DEFAULT 'North Macedonia',
        language TEXT DEFAULT 'sq',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1
    );

    -- Student profiles
    CREATE TABLE IF NOT EXISTS student_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        date_of_birth DATE,
        education_level TEXT,
        school_name TEXT,
        gpa REAL,
        interests TEXT,  -- JSON array
        skills TEXT,      -- JSON array
        languages TEXT,   -- JSON array
        bio TEXT,
        cv_path TEXT,
        availability_date DATE,
        preferred_professions TEXT,  -- JSON array
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- Company profiles
    CREATE TABLE IF NOT EXISTS company_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        company_name TEXT NOT NULL,
        industry TEXT,
        company_size TEXT CHECK(company_size IN ('1-10', '11-50', '51-200', '201-500', '500+')),
        description TEXT,
        website TEXT,
        logo_path TEXT,
        address TEXT,
        is_verified INTEGER DEFAULT 0,
        max_apprentices INTEGER DEFAULT 5,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- School profiles
    CREATE TABLE IF NOT EXISTS school_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        school_name TEXT NOT NULL,
        school_type TEXT,
        address TEXT,
        capacity INTEGER,
        programs_offered TEXT,  -- JSON array
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- Professions catalog (like Swiss 250 professions)
    CREATE TABLE IF NOT EXISTS professions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name_sq TEXT NOT NULL,
        name_en TEXT,
        name_mk TEXT,
        category TEXT NOT NULL,
        duration_years INTEGER NOT NULL CHECK(duration_years IN (2, 3, 4)),
        qualification_type TEXT CHECK(qualification_type IN ('EBA', 'EFZ')),
        description TEXT,
        skills_required TEXT,   -- JSON array
        school_days_per_week INTEGER DEFAULT 2,
        company_days_per_week INTEGER DEFAULT 3,
        salary_year1 REAL,
        salary_year2 REAL,
        salary_year3 REAL,
        salary_year4 REAL,
        is_active INTEGER DEFAULT 1
    );

    -- Apprenticeship positions (like LENA)
    CREATE TABLE IF NOT EXISTS apprenticeship_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        profession_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        requirements TEXT,
        positions_available INTEGER DEFAULT 1,
        positions_filled INTEGER DEFAULT 0,
        start_date DATE,
        salary_monthly REAL,
        city TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES company_profiles(id),
        FOREIGN KEY (profession_id) REFERENCES professions(id)
    );

    -- Applications
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        position_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'reviewed', 'interview', 'accepted', 'rejected')),
        cover_letter TEXT,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES student_profiles(id),
        FOREIGN KEY (position_id) REFERENCES apprenticeship_positions(id),
        UNIQUE(student_id, position_id)
    );

    -- Apprenticeship contracts (active apprenticeships)
    CREATE TABLE IF NOT EXISTS apprenticeship_contracts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        company_id INTEGER NOT NULL,
        school_id INTEGER,
        profession_id INTEGER NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'terminated', 'paused')),
        current_year INTEGER DEFAULT 1,
        salary_monthly REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES student_profiles(id),
        FOREIGN KEY (company_id) REFERENCES company_profiles(id),
        FOREIGN KEY (profession_id) REFERENCES professions(id)
    );

    -- Curriculum modules
    CREATE TABLE IF NOT EXISTS curriculum_modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profession_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        module_name TEXT NOT NULL,
        module_type TEXT CHECK(module_type IN ('theory', 'practical', 'inter_company')),
        description TEXT,
        hours INTEGER,
        competencies TEXT,  -- JSON array
        order_index INTEGER,
        FOREIGN KEY (profession_id) REFERENCES professions(id)
    );

    -- Progress tracking
    CREATE TABLE IF NOT EXISTS student_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contract_id INTEGER NOT NULL,
        module_id INTEGER NOT NULL,
        status TEXT DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'completed', 'failed')),
        grade REAL,
        completion_date DATE,
        evaluator_notes TEXT,
        FOREIGN KEY (contract_id) REFERENCES apprenticeship_contracts(id),
        FOREIGN KEY (module_id) REFERENCES curriculum_modules(id)
    );

    -- Certificates / Diplomas
    CREATE TABLE IF NOT EXISTS certificates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contract_id INTEGER NOT NULL,
        certificate_type TEXT CHECK(certificate_type IN ('EBA', 'EFZ', 'BM')),
        certificate_number TEXT UNIQUE,
        issue_date DATE,
        profession_name TEXT,
        final_grade REAL,
        nqf_level INTEGER,
        eqf_level INTEGER,
        is_verified INTEGER DEFAULT 0,
        FOREIGN KEY (contract_id) REFERENCES apprenticeship_contracts(id)
    );

    -- Country configurations
    CREATE TABLE IF NOT EXISTS countries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        language TEXT,
        currency TEXT,
        min_apprentice_age INTEGER DEFAULT 15,
        max_apprentice_age INTEGER DEFAULT 25,
        government_body TEXT,
        legal_framework TEXT,
        is_active INTEGER DEFAULT 1
    );

    -- Notifications
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT,
        type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    -- Messages / Chat
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        subject TEXT,
        body TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        related_application_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES users(id),
        FOREIGN KEY (receiver_id) REFERENCES users(id)
    );

    -- Reviews / Ratings
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reviewer_id INTEGER NOT NULL,
        reviewed_id INTEGER NOT NULL,
        review_type TEXT NOT NULL CHECK(review_type IN ('student_to_company', 'company_to_student')),
        contract_id INTEGER,
        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        review_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (reviewer_id) REFERENCES users(id),
        FOREIGN KEY (reviewed_id) REFERENCES users(id),
        FOREIGN KEY (contract_id) REFERENCES apprenticeship_contracts(id),
        UNIQUE(reviewer_id, contract_id)
    );

    -- File uploads
    CREATE TABLE IF NOT EXISTS uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        original_name TEXT NOT NULL,
        file_type TEXT,
        file_size INTEGER,
        category TEXT CHECK(category IN ('cv', 'diploma', 'letter', 'certificate', 'other')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    -- Exams / Tests
    CREATE TABLE IF NOT EXISTS exams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        duration_minutes INTEGER DEFAULT 60,
        pass_grade REAL DEFAULT 4.0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (module_id) REFERENCES curriculum_modules(id)
    );

    CREATE TABLE IF NOT EXISTS exam_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        question_type TEXT CHECK(question_type IN ('multiple_choice', 'essay')),
        options TEXT,  -- JSON array for MC
        correct_answer TEXT,
        points REAL DEFAULT 1,
        order_index INTEGER,
        FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS exam_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        answers TEXT,  -- JSON
        score REAL,
        passed INTEGER,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY (exam_id) REFERENCES exams(id),
        FOREIGN KEY (student_id) REFERENCES student_profiles(id)
    );

    -- Mentoring
    CREATE TABLE IF NOT EXISTS mentorships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contract_id INTEGER NOT NULL,
        mentor_user_id INTEGER NOT NULL,
        mentor_name TEXT,
        mentor_role TEXT,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (contract_id) REFERENCES apprenticeship_contracts(id),
        FOREIGN KEY (mentor_user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS mentor_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mentorship_id INTEGER NOT NULL,
        week_number INTEGER,
        feedback_text TEXT NOT NULL,
        areas_of_improvement TEXT,
        rating INTEGER CHECK(rating BETWEEN 1 AND 5),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (mentorship_id) REFERENCES mentorships(id)
    );

    -- Schedule / Calendar
    CREATE TABLE IF NOT EXISTS schedule_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        contract_id INTEGER,
        title TEXT NOT NULL,
        description TEXT,
        event_type TEXT CHECK(event_type IN ('company', 'school', 'exam', 'inter_company', 'other')),
        day_of_week INTEGER,  -- 0=Monday, 4=Friday
        start_time TEXT,
        end_time TEXT,
        location TEXT,
        recurring INTEGER DEFAULT 1,
        specific_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    -- Favorites / Bookmarks
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        position_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (position_id) REFERENCES apprenticeship_positions(id) ON DELETE CASCADE,
        UNIQUE(user_id, position_id)
    );

    -- Application status history / timeline
    CREATE TABLE IF NOT EXISTS application_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL,
        old_status TEXT,
        new_status TEXT NOT NULL,
        changed_by INTEGER,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE,
        FOREIGN KEY (changed_by) REFERENCES users(id)
    );

    -- Translations (i18n)
    CREATE TABLE IF NOT EXISTS translations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL,
        lang TEXT NOT NULL CHECK(lang IN ('sq', 'mk', 'en')),
        value TEXT NOT NULL,
        UNIQUE(key, lang)
    );
    ''')

    # Seed data
    seed_data(db)
    db.commit()
    db.close()

def seed_data(db):
    """Insert initial data if tables are empty"""

    # Check if already seeded
    count = db.execute("SELECT COUNT(*) FROM professions").fetchone()[0]
    if count > 0:
        return

    # Countries
    countries = [
        ('MK', 'Maqedoni e Veriut / North Macedonia', 'sq,mk', 'MKD', 15, 25, 'Ministria e Arsimit dhe Shkencës', 'Ligji për Arsim Profesional 2025'),
        ('CH', 'Zvicër / Switzerland', 'de,fr,it', 'CHF', 15, 25, 'SERI/SBFI', 'BBG/LFPr 2004'),
        ('AL', 'Shqipëri / Albania', 'sq', 'ALL', 15, 25, 'Ministria e Arsimit', 'Ligji për Arsim Profesional'),
        ('XK', 'Kosovë / Kosovo', 'sq,sr', 'EUR', 15, 25, 'MASHT', 'Ligji për Arsim Profesional'),
        ('DE', 'Gjermani / Germany', 'de', 'EUR', 15, 25, 'BMBF', 'BBiG'),
    ]
    db.executemany("INSERT OR IGNORE INTO countries (code, name, language, currency, min_apprentice_age, max_apprentice_age, government_body, legal_framework) VALUES (?,?,?,?,?,?,?,?)", countries)

    # Professions (Swiss-style, adapted for Macedonia)
    professions = [
        # IT & Technology
        ('IT-001', 'Informatikan/e', 'IT Specialist', 'Информатичар/ка', 'Teknologji & IT', 4, 'EFZ',
         'Zhvillim softuerësh, administrim sistemesh, dhe rrjetash kompjuterike',
         '["Programim", "Rrjeta", "Databaza", "Siguri kibernetike"]', 2, 3, 5000, 7000, 9000, 11000),
        ('IT-002', 'Zhvillues/e Web', 'Web Developer', 'Веб Развивач/ка', 'Teknologji & IT', 3, 'EFZ',
         'Dizajn dhe zhvillim i faqeve web dhe aplikacioneve',
         '["HTML/CSS", "JavaScript", "React", "Backend"]', 2, 3, 5000, 7000, 9000, None),
        ('IT-003', 'Teknik/e IT', 'IT Technician', 'ИТ Техничар/ка', 'Teknologji & IT', 2, 'EBA',
         'Mirëmbajtje e pajisjeve dhe suport teknik',
         '["Hardware", "Software", "Suport"]', 2, 3, 4000, 5500, None, None),

        # Commerce & Retail
        ('COM-001', 'Tregtar/e me pakicë', 'Retail Specialist', 'Трговец на мало', 'Tregti & Shërbime', 3, 'EFZ',
         'Shitje, këshillim klientësh, menaxhim stoku në dyqane',
         '["Shitje", "Komunikim", "Menaxhim stoku", "Marketing"]', 2, 3, 4500, 6000, 7500, None),
        ('COM-002', 'Punonjës/e komercial/e', 'Commercial Employee', 'Комерцијален работник', 'Tregti & Shërbime', 3, 'EFZ',
         'Administratë biznesi, kontabilitet, korrespondencë',
         '["Office", "Kontabilitet", "Komunikim", "Organizim"]', 2, 3, 5000, 6500, 8000, None),
        ('COM-003', 'Asistent/e shitje', 'Sales Assistant', 'Асистент за продажба', 'Tregti & Shërbime', 2, 'EBA',
         'Ndihmë në shitje dhe mirëmbajtje dyqani',
         '["Shitje baze", "Komunikim"]', 2, 3, 4000, 5000, None, None),

        # Manufacturing & Technical
        ('MAN-001', 'Mekanik/e prodhimi', 'Production Mechanic', 'Механичар за производство', 'Prodhim & Industri', 4, 'EFZ',
         'Prodhim i pjesëve metalike, programim CNC, kontroll cilësie',
         '["CNC", "Vizatim teknik", "Materiale", "Cilësi"]', 2, 3, 5000, 7000, 9000, 11000),
        ('MAN-002', 'Elektricist/e', 'Electrician', 'Електричар/ка', 'Prodhim & Industri', 4, 'EFZ',
         'Instalime elektrike, sisteme automatizimi, mirëmbajtje',
         '["Elektroteknikë", "Automatizim", "Siguri"]', 2, 3, 5000, 7000, 9000, 11000),
        ('MAN-003', 'Saldator/e', 'Welder', 'Заварувач/ка', 'Prodhim & Industri', 3, 'EFZ',
         'Saldim i metaleve, lexim vizatimesh teknike',
         '["Saldim", "Vizatim teknik", "Siguri"]', 2, 3, 5000, 6500, 8000, None),

        # Health & Social
        ('HSC-001', 'Asistent/e mjekësor/e', 'Medical Assistant', 'Медицински асистент', 'Shëndetësi & Social', 3, 'EFZ',
         'Ndihmë në ordinanca mjekësore, laborator, kujdes pacientësh',
         '["Mjekësi bazë", "Laborator", "Komunikim", "Higjienë"]', 2, 3, 5000, 6500, 8000, None),
        ('HSC-002', 'Kujdestar/e', 'Care Worker', 'Негувател/ка', 'Shëndetësi & Social', 3, 'EFZ',
         'Kujdes për të moshuarit dhe personat me nevoja të veçanta',
         '["Kujdes", "Komunikim", "Mjekësi bazë"]', 2, 3, 4500, 6000, 7500, None),

        # Construction
        ('CON-001', 'Ndërtimtar/e', 'Construction Worker', 'Градежник/чка', 'Ndërtimtari', 3, 'EFZ',
         'Ndërtim i strukturave, punime betoni dhe murature',
         '["Ndërtim", "Vizatim teknik", "Siguri"]', 2, 3, 5500, 7000, 8500, None),
        ('CON-002', 'Instalues/e', 'Plumber', 'Водоинсталатер/ка', 'Ndërtimtari', 3, 'EFZ',
         'Instalime hidraulike dhe sanitare',
         '["Hidraulikë", "Vizatim teknik", "Siguri"]', 2, 3, 5000, 6500, 8000, None),

        # Gastronomy
        ('GAS-001', 'Kuzhinier/e', 'Chef', 'Готвач/ка', 'Gastronomi & Turizëm', 3, 'EFZ',
         'Përgatitje ushqimesh, menaxhim kuzhine, higjienë ushqimore',
         '["Gatim", "Higjienë", "Menaxhim kuzhine"]', 2, 3, 4500, 6000, 7500, None),
        ('GAS-002', 'Specialist/e hotelerie', 'Hotel Specialist', 'Хотелски специјалист/ка', 'Gastronomi & Turizëm', 3, 'EFZ',
         'Menaxhim hoteli, recepsion, shërbim mysafirësh',
         '["Hoteleri", "Komunikim", "Menaxhim"]', 2, 3, 4500, 6000, 7500, None),

        # Agriculture
        ('AGR-001', 'Bujk/e', 'Farmer', 'Земјоделец/ка', 'Bujqësi', 3, 'EFZ',
         'Kultivim i tokës, blegtori, teknologji bujqësore',
         '["Bujqësi", "Blegtori", "Teknologji"]', 2, 3, 4000, 5500, 7000, None),

        # Logistics
        ('LOG-001', 'Logjistikan/e', 'Logistics Specialist', 'Логистичар/ка', 'Logjistikë & Transport', 3, 'EFZ',
         'Menaxhim i depove, transport, zinxhir furnizimi',
         '["Logjistikë", "Organizim", "Software ERP"]', 2, 3, 5000, 6500, 8000, None),
    ]

    for p in professions:
        db.execute("""INSERT OR IGNORE INTO professions
            (code, name_sq, name_en, name_mk, category, duration_years, qualification_type,
             description, skills_required, school_days_per_week, company_days_per_week,
             salary_year1, salary_year2, salary_year3, salary_year4)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", p)

    # Seed curriculum modules for IT-001 as example
    it_profession = db.execute("SELECT id FROM professions WHERE code='IT-001'").fetchone()
    if it_profession:
        pid = it_profession[0]
        modules = [
            # Year 1
            (pid, 1, 'Bazat e Programimit', 'theory', 'Hyrje në logjikën e programimit, variabla, struktura të dhënash', 120, '["Logjikë", "Algoritme", "Variabla"]', 1),
            (pid, 1, 'Hardware & Rrjeta Bazë', 'theory', 'Komponentët e kompjuterit, rrjeta LAN, TCP/IP', 80, '["Hardware", "Networking"]', 2),
            (pid, 1, 'Praktikë në Kompani - Viti 1', 'practical', 'Suport IT, mirëmbajtje, detyra bazë programimi', 600, '["Suport", "Mirëmbajtje"]', 3),
            (pid, 1, 'Kurs Ndërkompanish - Bazat', 'inter_company', 'Workshop praktik me teknika bazë IT', 40, '["Workshop"]', 4),
            # Year 2
            (pid, 2, 'Programim i Avancuar', 'theory', 'OOP, databaza, API-të', 120, '["OOP", "SQL", "API"]', 5),
            (pid, 2, 'Siguri Kibernetike', 'theory', 'Bazat e sigurisë, enkriptim, firewall', 60, '["Siguri", "Enkriptim"]', 6),
            (pid, 2, 'Praktikë në Kompani - Viti 2', 'practical', 'Zhvillim projektesh, menaxhim databazash', 600, '["Zhvillim", "Databaza"]', 7),
            # Year 3
            (pid, 3, 'Zhvillim Web & Mobile', 'theory', 'Frontend, Backend, Mobile development', 120, '["Web", "Mobile", "Full-stack"]', 8),
            (pid, 3, 'Menaxhim Projektesh IT', 'theory', 'Agile, Scrum, dokumentacion', 40, '["Agile", "Scrum"]', 9),
            (pid, 3, 'Praktikë në Kompani - Viti 3', 'practical', 'Projekte të pavarura, mentoring', 600, '["Projekt", "Autonomi"]', 10),
            # Year 4
            (pid, 4, 'Specializim', 'theory', 'Cloud, DevOps, AI/ML bazë', 100, '["Cloud", "DevOps", "AI"]', 11),
            (pid, 4, 'Projekt Final (IPA)', 'practical', 'Projekt individual praktik - demonstrim i të gjitha kompetencave', 200, '["Projekt Final"]', 12),
            (pid, 4, 'Përgatitje për Provim', 'theory', 'Përsëritje dhe përgatitje për provimin përfundimtar', 60, '["Provim"]', 13),
        ]
        db.executemany("""INSERT OR IGNORE INTO curriculum_modules
            (profession_id, year, module_name, module_type, description, hours, competencies, order_index)
            VALUES (?,?,?,?,?,?,?,?)""", modules)

    # Seed curriculum for ALL professions
    def seed_modules(code, modules_data):
        prof = db.execute("SELECT id FROM professions WHERE code=?", (code,)).fetchone()
        if prof:
            pid = prof[0]
            existing = db.execute("SELECT COUNT(*) FROM curriculum_modules WHERE profession_id=?", (pid,)).fetchone()[0]
            if existing == 0:
                rows = [(pid, *m) for m in modules_data]
                db.executemany("""INSERT OR IGNORE INTO curriculum_modules
                    (profession_id, year, module_name, module_type, description, hours, competencies, order_index)
                    VALUES (?,?,?,?,?,?,?,?)""", rows)

    # IT-002: Web Developer (3 years)
    seed_modules('IT-002', [
        (1, 'HTML, CSS & Dizajn Bazë', 'theory', 'Struktura e faqeve web, stilizimi, responsive design', 120, '["HTML", "CSS", "Responsive"]', 1),
        (1, 'JavaScript Bazë', 'theory', 'Variabla, funksione, DOM manipulation', 100, '["JavaScript", "DOM"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Krijim faqesh statike, detyra frontend', 500, '["Frontend"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Git, mjete zhvillimi', 40, '["Git", "Tools"]', 4),
        (2, 'React & Frontend Avancuar', 'theory', 'Komponentë, state management, API calls', 120, '["React", "SPA"]', 5),
        (2, 'Backend me Node.js', 'theory', 'Express, REST API, databaza', 100, '["Node.js", "API", "SQL"]', 6),
        (2, 'Praktikë - Viti 2', 'practical', 'Zhvillim aplikacionesh full-stack', 500, '["Full-stack"]', 7),
        (3, 'DevOps & Deployment', 'theory', 'CI/CD, hosting, Docker bazë', 80, '["DevOps", "Docker"]', 8),
        (3, 'Projekt Final (IPA)', 'practical', 'Aplikacion web i plotë si projekt përfundimtar', 200, '["Projekt Final"]', 9),
        (3, 'Përgatitje për Provim', 'theory', 'Përsëritje e materialit, mock-teste', 60, '["Provim"]', 10),
    ])

    # IT-003: IT Technician (2 years)
    seed_modules('IT-003', [
        (1, 'Hardware Kompjuterik', 'theory', 'Komponentë, montim, diagnostikim', 100, '["Hardware", "Diagnostikim"]', 1),
        (1, 'Sisteme Operative', 'theory', 'Windows, Linux, instalim, konfigurim', 80, '["Windows", "Linux"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Suport teknik, riparim pajisjesh', 500, '["Suport", "Riparim"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Rrjeta dhe kabllim', 40, '["Rrjeta"]', 4),
        (2, 'Rrjeta & Siguri', 'theory', 'LAN/WAN, firewall, troubleshooting', 100, '["Networking", "Siguri"]', 5),
        (2, 'Projekt Final (IPA)', 'practical', 'Konfigurim i plotë i infrastrukturës IT', 200, '["Projekt Final"]', 6),
        (2, 'Përgatitje për Provim', 'theory', 'Përsëritje dhe provim', 60, '["Provim"]', 7),
    ])

    # COM-001: Retail (3 years)
    seed_modules('COM-001', [
        (1, 'Bazat e Shitjes', 'theory', 'Komunikim me klientë, teknika shitjeje, prezantim produktesh', 100, '["Shitje", "Komunikim"]', 1),
        (1, 'Menaxhim i Stokut', 'theory', 'Pranimin e mallit, inventar, ekspozim', 80, '["Stok", "Inventar"]', 2),
        (1, 'Praktikë në Dyqan - Viti 1', 'practical', 'Shërbim klientësh, arka, rafte', 500, '["Dyqan", "Arka"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Shërbim cilësor', 40, '["Shërbim"]', 4),
        (2, 'Marketing & Visual Merchandising', 'theory', 'Promovime, ekspozim, strategji marketingu', 100, '["Marketing", "Display"]', 5),
        (2, 'Kontabilitet Tregtar', 'theory', 'Faturim, llogaritje, raporte', 80, '["Kontabilitet"]', 6),
        (2, 'Praktikë - Viti 2', 'practical', 'Menaxhim seksioni, porositje', 500, '["Menaxhim"]', 7),
        (3, 'E-commerce & Digjitalizim', 'theory', 'Shitje online, platforma digjitale', 80, '["E-commerce"]', 8),
        (3, 'Projekt Final (IPA)', 'practical', 'Menaxhim i pavarur i një seksioni dyqani', 200, '["Projekt Final"]', 9),
        (3, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 10),
    ])

    # COM-002: Commercial Employee (3 years)
    seed_modules('COM-002', [
        (1, 'Administratë Biznesi', 'theory', 'Korrespondencë, organizim, protokolle', 120, '["Administratë", "Office"]', 1),
        (1, 'Kontabilitet Bazë', 'theory', 'Llogaritje, bilance, faturim', 80, '["Kontabilitet"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Punë administrative, dosje, email', 500, '["Zyrë"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Software ERP', 40, '["ERP"]', 4),
        (2, 'Menaxhim Financiar', 'theory', 'Buxhet, raporte financiare, taksim', 100, '["Financa"]', 5),
        (2, 'Komunikim Biznesi', 'theory', 'Prezantime, negociata, anglisht biznesi', 80, '["Komunikim"]', 6),
        (2, 'Praktikë - Viti 2', 'practical', 'Menaxhim projektesh, koordinim', 500, '["Projekt"]', 7),
        (3, 'Digjitalizim i Proceseve', 'theory', 'Automatizim, CRM, analitikë', 80, '["CRM", "Analitikë"]', 8),
        (3, 'Projekt Final (IPA)', 'practical', 'Projekt i pavarur administrativ', 200, '["Projekt Final"]', 9),
        (3, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 10),
    ])

    # COM-003: Sales Assistant (2 years)
    seed_modules('COM-003', [
        (1, 'Bazat e Komunikimit', 'theory', 'Si të flasësh me klientë, mirësjellje', 80, '["Komunikim"]', 1),
        (1, 'Njohuri Produktesh', 'theory', 'Kategoritë, çmimet, ekspozimi', 80, '["Produkte"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Punë në dyqan, ndihmë klientësh', 500, '["Shitje"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop praktik', 40, '["Workshop"]', 4),
        (2, 'Teknika Shitjeje', 'theory', 'Upselling, shërbim pas shitjes', 80, '["Teknika"]', 5),
        (2, 'Projekt Final (IPA)', 'practical', 'Demonstrim i aftësive të shitjes', 200, '["Projekt Final"]', 6),
        (2, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 7),
    ])

    # MAN-001: Production Mechanic (4 years)
    seed_modules('MAN-001', [
        (1, 'Vizatim Teknik', 'theory', 'Lexim dhe krijim i vizatimeve teknike, CAD bazë', 100, '["CAD", "Vizatim"]', 1),
        (1, 'Materiale & Përpunim', 'theory', 'Metalurgjia, materialet, vetitë mekanike', 80, '["Materiale"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Punë bazë me metale, matje, tornim', 500, '["Tornim", "Matje"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Mjete dhe makina bazë', 40, '["Mjete"]', 4),
        (2, 'Programim CNC', 'theory', 'G-code, koordinata, simulim', 120, '["CNC", "G-code"]', 5),
        (2, 'Kontroll Cilësie', 'theory', 'ISO, toleranca, instrumente matëse', 60, '["ISO", "Cilësi"]', 6),
        (2, 'Praktikë - Viti 2', 'practical', 'Operim makinash CNC, prodhim pjesësh', 500, '["CNC", "Prodhim"]', 7),
        (3, 'Automatizim Industrial', 'theory', 'PLC, sensorë, pneumatikë', 100, '["PLC", "Automatizim"]', 8),
        (3, 'Praktikë - Viti 3', 'practical', 'Prodhim i pavarur, menaxhim procesi', 500, '["Prodhim"]', 9),
        (4, 'Specializim & Optimizim', 'theory', 'Lean manufacturing, Six Sigma bazë', 80, '["Lean", "Optimizim"]', 10),
        (4, 'Projekt Final (IPA)', 'practical', 'Prodhim i një pjese komplekse nga fillimi', 200, '["Projekt Final"]', 11),
        (4, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 12),
    ])

    # MAN-002: Electrician (4 years)
    seed_modules('MAN-002', [
        (1, 'Elektroteknikë Bazë', 'theory', 'Ligjet e Ohm-it, qarqe, komponentë', 120, '["Elektroteknikë", "Qarqe"]', 1),
        (1, 'Siguria Elektrike', 'theory', 'Normat, mbrojtja, procedura sigurie', 60, '["Siguri"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Instalime bazë, kabllim, lidhje', 500, '["Instalime"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Mjete dhe matje elektrike', 40, '["Matje"]', 4),
        (2, 'Instalime Industriale', 'theory', 'Sisteme trefazore, panele, distribucioni', 100, '["Industri"]', 5),
        (2, 'Teknikë Digjitale', 'theory', 'Logjikë, PLC bazë, sensorë', 80, '["PLC", "Sensorë"]', 6),
        (2, 'Praktikë - Viti 2', 'practical', 'Instalime industriale, mirëmbajtje', 500, '["Mirëmbajtje"]', 7),
        (3, 'Automatizim & PLC', 'theory', 'Programim PLC, SCADA, HMI', 100, '["PLC", "SCADA"]', 8),
        (3, 'Praktikë - Viti 3', 'practical', 'Sisteme automatizimi, projekte', 500, '["Automatizim"]', 9),
        (4, 'Energji e Rinovueshme', 'theory', 'Solare, efiçencë energjetike', 80, '["Solare", "Energji"]', 10),
        (4, 'Projekt Final (IPA)', 'practical', 'Instalim i plotë i një sistemi elektrik', 200, '["Projekt Final"]', 11),
        (4, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 12),
    ])

    # MAN-003: Welder (3 years)
    seed_modules('MAN-003', [
        (1, 'Teknikat e Saldimit', 'theory', 'MIG, MAG, TIG, elektrodë, siguri', 100, '["MIG", "MAG", "TIG"]', 1),
        (1, 'Vizatim Teknik Saldimi', 'theory', 'Simbole saldimi, specifikimet', 60, '["Vizatim"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Saldim bazë, pozicione të ndryshme', 500, '["Saldim"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Teknika dhe siguri', 40, '["Siguri"]', 4),
        (2, 'Saldim i Avancuar', 'theory', 'Materiale speciale, aliazhe, testim', 100, '["Aliazhe", "Testim"]', 5),
        (2, 'Praktikë - Viti 2', 'practical', 'Saldim i strukturave komplekse', 500, '["Struktura"]', 6),
        (3, 'Kontroll Cilësie NDT', 'theory', 'Kontrolli jo-destruktiv, certifikim', 80, '["NDT", "Cilësi"]', 7),
        (3, 'Projekt Final (IPA)', 'practical', 'Saldim i një strukture të certifikuar', 200, '["Projekt Final"]', 8),
        (3, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 9),
    ])

    # HSC-001: Medical Assistant (3 years)
    seed_modules('HSC-001', [
        (1, 'Anatomi & Fiziologji', 'theory', 'Trupi i njeriut, organet, funksionet', 120, '["Anatomi", "Fiziologji"]', 1),
        (1, 'Higjienë & Siguri', 'theory', 'Dezinfektim, sterilizim, protokolle', 60, '["Higjienë"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Ndihmë në ordinancë, marrje gjakut', 500, '["Ordinancë"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Procedura bazë mjekësore', 40, '["Procedura"]', 4),
        (2, 'Farmakologji Bazë', 'theory', 'Medikamentet, dozimi, ndërveprimet', 80, '["Farmakologji"]', 5),
        (2, 'Teknika Laboratorike', 'theory', 'Analiza, aparatura, diagnostikim', 80, '["Laborator"]', 6),
        (2, 'Praktikë - Viti 2', 'practical', 'Laborator, kujdes pacientësh', 500, '["Kujdes"]', 7),
        (3, 'Emergjenca & Ndihma e Parë', 'theory', 'Trajtim emergjencash, CPR', 80, '["Emergjencë"]', 8),
        (3, 'Projekt Final (IPA)', 'practical', 'Menaxhim i pavarur i pacientëve', 200, '["Projekt Final"]', 9),
        (3, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 10),
    ])

    # HSC-002: Care Worker (3 years)
    seed_modules('HSC-002', [
        (1, 'Bazat e Kujdesit', 'theory', 'Komunikim me pacientë, etikë, psikologji', 100, '["Kujdes", "Etikë"]', 1),
        (1, 'Higjienë Personale', 'theory', 'Ndihmë në higjienën ditore, ushqyerje', 80, '["Higjienë"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Kujdes në shtëpi pleqsh/spital', 500, '["Praktikë"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Teknika kujdesi', 40, '["Teknika"]', 4),
        (2, 'Geriartri & Rehabilitim', 'theory', 'Sëmundjet e moshës, fizioterapi bazë', 100, '["Geriartri"]', 5),
        (2, 'Praktikë - Viti 2', 'practical', 'Kujdes i avancuar, menaxhim', 500, '["Kujdes"]', 6),
        (3, 'Kujdesi Paliativ', 'theory', 'Kujdesi në fund të jetës, mbështetje', 60, '["Paliativ"]', 7),
        (3, 'Projekt Final (IPA)', 'practical', 'Kujdes i pavarur i pacientëve', 200, '["Projekt Final"]', 8),
        (3, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 9),
    ])

    # CON-001: Construction (3 years)
    seed_modules('CON-001', [
        (1, 'Bazat e Ndërtimit', 'theory', 'Materialet, sigurinë, vizatim teknik', 100, '["Materiale", "Siguri"]', 1),
        (1, 'Muraturë & Beton', 'theory', 'Teknikat e murimit, betonimi, armatura', 80, '["Muraturë", "Beton"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Punë ndërtimi bazë në kantier', 500, '["Kantier"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Mjete ndërtimi', 40, '["Mjete"]', 4),
        (2, 'Konstruksione', 'theory', 'Struktura, llogaritje statike bazë', 100, '["Struktura"]', 5),
        (2, 'Praktikë - Viti 2', 'practical', 'Ndërtime më komplekse, fasada', 500, '["Ndërtim"]', 6),
        (3, 'Teknologji Moderne', 'theory', 'Izolim, efiçencë energjetike, BIM', 80, '["BIM", "Izolim"]', 7),
        (3, 'Projekt Final (IPA)', 'practical', 'Ndërtim i një strukture të plotë', 200, '["Projekt Final"]', 8),
        (3, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 9),
    ])

    # CON-002: Plumber (3 years)
    seed_modules('CON-002', [
        (1, 'Hidraulikë Bazë', 'theory', 'Ligjet e lëngjeve, tubacione, materiale', 100, '["Hidraulikë"]', 1),
        (1, 'Vizatim Instalimesh', 'theory', 'Skema sanitare, simbole, standarde', 60, '["Vizatim"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Instalim tubash, lidhje, riparime', 500, '["Instalim"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Mjete dhe teknika', 40, '["Mjete"]', 4),
        (2, 'Sisteme Ngrohje/Ftohje', 'theory', 'Radiatora, bojlera, klima', 100, '["Ngrohje", "Ftohje"]', 5),
        (2, 'Praktikë - Viti 2', 'practical', 'Instalime të plota sanitare', 500, '["Sanitare"]', 6),
        (3, 'Energji Solare Termike', 'theory', 'Panele solare, pompë nxehtësie', 60, '["Solare"]', 7),
        (3, 'Projekt Final (IPA)', 'practical', 'Instalim i plotë i sistemit', 200, '["Projekt Final"]', 8),
        (3, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 9),
    ])

    # GAS-001: Chef (3 years)
    seed_modules('GAS-001', [
        (1, 'Bazat e Gastronomisë', 'theory', 'Higjienë ushqimore, HACCP, organizim kuzhine', 100, '["HACCP", "Higjienë"]', 1),
        (1, 'Teknika Gatimi', 'theory', 'Prerje, zierje, pjekje, përmbajtje', 80, '["Teknika"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Punë në kuzhinë, përgatitje bazë', 500, '["Kuzhinë"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Gatim profesional', 40, '["Gatim"]', 4),
        (2, 'Kuzhinë Ndërkombëtare', 'theory', 'Kuzhinat e botës, receta, prezantim', 80, '["Ndërkombëtare"]', 5),
        (2, 'Menaxhim Kuzhine', 'theory', 'Porositje, kosto, menu planning', 60, '["Menaxhim"]', 6),
        (2, 'Praktikë - Viti 2', 'practical', 'Përgatitje e plotë e menysë', 500, '["Menu"]', 7),
        (3, 'Pastiçeri & Ëmbëlsira', 'theory', 'Torta, brumëra, dekorime', 60, '["Pastiçeri"]', 8),
        (3, 'Projekt Final (IPA)', 'practical', 'Menaxhim i pavarur i kuzhinës', 200, '["Projekt Final"]', 9),
        (3, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 10),
    ])

    # GAS-002: Hotel Specialist (3 years)
    seed_modules('GAS-002', [
        (1, 'Hyrje në Hoteleri', 'theory', 'Struktura e hotelit, departamentet, standardet', 100, '["Hoteleri"]', 1),
        (1, 'Recepsion & Front Office', 'theory', 'Check-in/out, rezervime, sisteme PMS', 80, '["Recepsion", "PMS"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Punë në recepsion, shërbim dhomash', 500, '["Praktikë"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Shërbim klienti', 40, '["Shërbim"]', 4),
        (2, 'Menaxhim Eventesh', 'theory', 'Organizim konferencash, banketesh', 80, '["Evente"]', 5),
        (2, 'Marketing Turistik', 'theory', 'Promovim, OTA, media sociale', 80, '["Marketing"]', 6),
        (2, 'Praktikë - Viti 2', 'practical', 'Koordinim eventesh, menaxhim', 500, '["Menaxhim"]', 7),
        (3, 'Revenue Management', 'theory', 'Çmimet, yield, strategji', 60, '["Revenue"]', 8),
        (3, 'Projekt Final (IPA)', 'practical', 'Menaxhim i pavarur i operacioneve', 200, '["Projekt Final"]', 9),
        (3, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 10),
    ])

    # AGR-001: Farmer (3 years)
    seed_modules('AGR-001', [
        (1, 'Bazat e Bujqësisë', 'theory', 'Toka, klima, bimët, ciklet e prodhimit', 100, '["Bujqësi"]', 1),
        (1, 'Blegtori Bazë', 'theory', 'Kujdesi i kafshëve, ushqyerja, strehimi', 80, '["Blegtori"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Punë në fermë, mbjellje, korrje', 500, '["Fermë"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Makineri bujqësore', 40, '["Makineri"]', 4),
        (2, 'Teknologji Bujqësore', 'theory', 'Ujitje, sera, pesticide, organik', 100, '["Teknologji"]', 5),
        (2, 'Praktikë - Viti 2', 'practical', 'Menaxhim i kulturave, kujdes shtazësh', 500, '["Menaxhim"]', 6),
        (3, 'Agrobiznes', 'theory', 'Marketing, shitje, subvencione, plan biznesi', 80, '["Agrobiznes"]', 7),
        (3, 'Projekt Final (IPA)', 'practical', 'Menaxhim i pavarur i fermës', 200, '["Projekt Final"]', 8),
        (3, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 9),
    ])

    # LOG-001: Logistics (3 years)
    seed_modules('LOG-001', [
        (1, 'Bazat e Logjistikës', 'theory', 'Zinxhiri i furnizimit, depo, transport', 100, '["Logjistikë", "SCM"]', 1),
        (1, 'Menaxhim i Depove', 'theory', 'Pranimit, ruajtja, dërgimi, inventar', 80, '["Depo", "Inventar"]', 2),
        (1, 'Praktikë - Viti 1', 'practical', 'Punë në depo, pranimin, dërgim', 500, '["Depo"]', 3),
        (1, 'Kurs Ndërkompanish', 'inter_company', 'Workshop: Software logjistike, WMS', 40, '["WMS"]', 4),
        (2, 'Transport & Distribucion', 'theory', 'Planifikim rutash, doganë, dokumente', 100, '["Transport"]', 5),
        (2, 'ERP & Sisteme Digjitale', 'theory', 'SAP bazë, barcode, RFID', 60, '["ERP", "SAP"]', 6),
        (2, 'Praktikë - Viti 2', 'practical', 'Koordinim dërgesash, planifikim', 500, '["Koordinim"]', 7),
        (3, 'Optimizim & Lean', 'theory', 'Lean logistics, KPI, analitikë', 80, '["Lean", "KPI"]', 8),
        (3, 'Projekt Final (IPA)', 'practical', 'Optimizim i procesit logjistik', 200, '["Projekt Final"]', 9),
        (3, 'Përgatitje për Provim', 'theory', 'Përsëritje', 60, '["Provim"]', 10),
    ])

    # Seed demo companies
    demo_password = hashlib.sha256('demo123'.encode()).hexdigest()

    companies = [
        ('info@alkaloid.mk', demo_password, 'company', 'Alkaloid AD', '389-2-3104000', 'Shkup', 'North Macedonia'),
        ('hr@kromberg.mk', demo_password, 'company', 'Kromberg & Schubert', '389-47-208000', 'Manastir', 'North Macedonia'),
        ('karriera@draexlmaier.mk', demo_password, 'company', 'DRAEXLMAIER Macedonia', '389-2-3200000', 'Shkup', 'North Macedonia'),
        ('info@vanhool.mk', demo_password, 'company', 'Van Hool Macedonia', '389-2-3250000', 'Shkup', 'North Macedonia'),
        ('hr@nelt.mk', demo_password, 'company', 'Nelt Group Macedonia', '389-2-3300000', 'Shkup', 'North Macedonia'),
    ]

    for c in companies:
        db.execute("INSERT OR IGNORE INTO users (email, password_hash, role, full_name, phone, city, country) VALUES (?,?,?,?,?,?,?)", c)

    # Company profiles
    company_profiles = [
        ('info@alkaloid.mk', 'Alkaloid AD', 'Farmaci & Kimi', '500+',
         'Kompania më e madhe farmaceutike në Maqedoni me mbi 90 vjet përvojë. Prodhon medikamente, kozmetikë, dhe produkte kimike.',
         'https://www.alkaloid.com.mk', 'Blvd. Aleksandar Makedonski 12, Shkup', 20),
        ('hr@kromberg.mk', 'Kromberg & Schubert', 'Prodhim Automobilistik', '500+',
         'Prodhues gjerman i instalimeve elektrike për automobila. Punëdhënësi i dytë më i madh në Maqedoni.',
         'https://www.kromberg-schubert.com', 'Zona Industriale, Manastir', 50),
        ('karriera@draexlmaier.mk', 'DRAEXLMAIER Macedonia', 'Prodhim Automobilistik', '201-500',
         'Prodhues gjerman i komponentëve të brendshme për automobila premium. Tashmë ka program dual edukimi.',
         'https://www.draexlmaier.com', 'Zona Teknologjike, Shkup', 30),
        ('info@vanhool.mk', 'Van Hool Macedonia', 'Prodhim Autobusësh', '201-500',
         'Prodhues belg i autobusëve dhe autokarëve. Fabrikë moderne në Shkup.',
         'https://www.vanhool.com', 'Zona Industriale, Shkup', 25),
        ('hr@nelt.mk', 'Nelt Group Macedonia', 'Distribucion & Logjistikë', '51-200',
         'Kompani rajonale e distribucionit. Partner me UNICEF për green skills.',
         'https://www.nfrr.mk', 'Shkup', 15),
    ]

    for cp in company_profiles:
        user = db.execute("SELECT id FROM users WHERE email=?", (cp[0],)).fetchone()
        if user:
            db.execute("""INSERT OR IGNORE INTO company_profiles
                (user_id, company_name, industry, company_size, description, website, address, max_apprentices)
                VALUES (?,?,?,?,?,?,?,?)""", (user[0], cp[1], cp[2], cp[3], cp[4], cp[5], cp[6], cp[7]))

    # Seed some apprenticeship positions
    positions_data = [
        ('Alkaloid AD', 'IT-001', 'Praktikant/e IT - Zhvillim Softuerësh',
         'Mundësi për të mësuar zhvillimin e softuerëve në departamentin tonë të IT. Do të punosh me teknologji moderne.',
         'Nxënës i shkollës së mesme, njohuri bazë programimi', 3, '2026-09-01', 8000, 'Shkup'),
        ('Alkaloid AD', 'HSC-001', 'Praktikant/e - Asistent Laboratori',
         'Punë praktike në laboratorin farmaceutik. Mëso teknikat e kontrollit të cilësisë.',
         'Nxënës i shkollës së mesme, interes për kimi/biologji', 2, '2026-09-01', 7000, 'Shkup'),
        ('Kromberg & Schubert', 'MAN-002', 'Praktikant/e Elektricist',
         'Trajnim në instalime elektrike për automobila. Program i strukturuar dual.',
         'Nxënës i shkollës së mesme teknike', 5, '2026-09-01', 7500, 'Manastir'),
        ('Kromberg & Schubert', 'MAN-001', 'Praktikant/e Mekanik Prodhimi',
         'Mëso programimin CNC dhe teknikat moderne të prodhimit.',
         'Nxënës, njohuri bazë matematike', 3, '2026-09-01', 7500, 'Manastir'),
        ('DRAEXLMAIER Macedonia', 'MAN-002', 'Dual Praktikant/e - Elektroteknikë',
         'Program dual edukimi sipas modelit gjerman. 3 ditë kompani + 2 ditë shkollë.',
         'Nxënës 15-18 vjeç', 10, '2026-09-01', 8000, 'Shkup'),
        ('DRAEXLMAIER Macedonia', 'IT-001', 'Dual Praktikant/e - IT',
         'Zhvillim i aftësive IT në mjedis industrial modern.',
         'Interes për IT, njohuri bazë kompjuteri', 5, '2026-09-01', 8500, 'Shkup'),
        ('Van Hool Macedonia', 'MAN-003', 'Praktikant/e Saldator',
         'Trajnim profesional në saldim për industrinë e autobusëve.',
         'Nxënës i shkollës teknike', 4, '2026-09-01', 7000, 'Shkup'),
        ('Van Hool Macedonia', 'MAN-001', 'Praktikant/e Mekanik',
         'Punë praktike në linjën e montimit të autobusëve.',
         'Nxënës i shkollës teknike', 3, '2026-09-01', 7000, 'Shkup'),
        ('Nelt Group Macedonia', 'LOG-001', 'Praktikant/e Logjistikë',
         'Mëso menaxhimin e depove dhe zinxhirin e furnizimit.',
         'Nxënës me aftësi organizative', 2, '2026-09-01', 6500, 'Shkup'),
        ('Nelt Group Macedonia', 'COM-001', 'Praktikant/e Shitje',
         'Trajnim në shitje, marketing, dhe menaxhim klientësh.',
         'Aftësi komunikimi të mira', 3, '2026-09-01', 6000, 'Shkup'),
    ]

    for pd in positions_data:
        company = db.execute("SELECT cp.id FROM company_profiles cp JOIN users u ON cp.user_id=u.id WHERE cp.company_name=?", (pd[0],)).fetchone()
        profession = db.execute("SELECT id FROM professions WHERE code=?", (pd[1],)).fetchone()
        if company and profession:
            db.execute("""INSERT OR IGNORE INTO apprenticeship_positions
                (company_id, profession_id, title, description, requirements, positions_available, start_date, salary_monthly, city)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (company[0], profession[0], pd[2], pd[3], pd[4], pd[5], pd[6], pd[7], pd[8]))

    # Seed a demo student
    db.execute("INSERT OR IGNORE INTO users (email, password_hash, role, full_name, phone, city, country) VALUES (?,?,?,?,?,?,?)",
        ('student@demo.com', demo_password, 'student', 'Artan Sulejmani', '070-123-456', 'Tetovë', 'North Macedonia'))

    student_user = db.execute("SELECT id FROM users WHERE email='student@demo.com'").fetchone()
    if student_user:
        db.execute("""INSERT OR IGNORE INTO student_profiles
            (user_id, date_of_birth, education_level, school_name, gpa, interests, skills, languages, bio, preferred_professions)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (student_user[0], '2009-05-15', 'Shkollë e mesme - viti 1', 'SHMT "Mosha Pijade" Tetovë', 4.2,
             '["Teknologji", "Programim", "Robotikë"]',
             '["Python bazë", "HTML/CSS", "Matematikë"]',
             '["Shqip", "Maqedonisht", "Anglisht"]',
             'Nxënës i motivuar me interes të madh për teknologjinë dhe programimin.',
             '["IT-001", "IT-002", "IT-003"]'))

    # Seed a demo school
    db.execute("INSERT OR IGNORE INTO users (email, password_hash, role, full_name, phone, city, country) VALUES (?,?,?,?,?,?,?)",
        ('admin@shmttetove.edu.mk', demo_password, 'school', 'SHMQP Tetovë', '044-330-100', 'Tetovë', 'North Macedonia'))

    school_user = db.execute("SELECT id FROM users WHERE email='admin@shmttetove.edu.mk'").fetchone()
    if school_user:
        db.execute("""INSERT OR IGNORE INTO school_profiles
            (user_id, school_name, school_type, address, capacity, programs_offered)
            VALUES (?,?,?,?,?,?)""",
            (school_user[0], 'Shkolla e Mesme Profesionale - Tetovë', 'Qendër Rajonale VET',
             'Rr. Ilindenit 50, Tetovë', 800,
             '["IT-001", "IT-002", "MAN-001", "MAN-002", "COM-001", "COM-002"]'))

    # Seed government user
    db.execute("INSERT OR IGNORE INTO users (email, password_hash, role, full_name, phone, city, country) VALUES (?,?,?,?,?,?,?)",
        ('admin@mon.gov.mk', demo_password, 'government', 'Ministria e Arsimit', '02-3140-100', 'Shkup', 'North Macedonia'))

    # Seed translations (core UI strings)
    translations = [
        # Navigation
        ('nav.home', 'sq', 'Ballina'), ('nav.home', 'mk', 'Почетна'), ('nav.home', 'en', 'Home'),
        ('nav.positions', 'sq', 'Pozicione (LENA)'), ('nav.positions', 'mk', 'Позиции (ЛЕНА)'), ('nav.positions', 'en', 'Positions (LENA)'),
        ('nav.professions', 'sq', 'Profesione'), ('nav.professions', 'mk', 'Професии'), ('nav.professions', 'en', 'Professions'),
        ('nav.dashboard', 'sq', 'Dashboard'), ('nav.dashboard', 'mk', 'Контролна табла'), ('nav.dashboard', 'en', 'Dashboard'),
        ('nav.login', 'sq', 'Hyr'), ('nav.login', 'mk', 'Најави се'), ('nav.login', 'en', 'Login'),
        ('nav.register', 'sq', 'Regjistrohu'), ('nav.register', 'mk', 'Регистрирај се'), ('nav.register', 'en', 'Register'),
        ('nav.logout', 'sq', 'Dil'), ('nav.logout', 'mk', 'Одјави се'), ('nav.logout', 'en', 'Logout'),
        # Hero
        ('hero.title', 'sq', 'Arsimi Profesional Dual — Modeli Zviceran, Global'),
        ('hero.title', 'mk', 'Стручно Дуално Образование — Швајцарски Модел, Глобален'),
        ('hero.title', 'en', 'Dual Vocational Education — Swiss Model, Global'),
        ('hero.subtitle', 'sq', 'Mëso duke punuar — 3 ditë në kompani, 2 ditë në shkollë.'),
        ('hero.subtitle', 'mk', 'Учи работејќи — 3 дена во компанија, 2 дена во училиште.'),
        ('hero.subtitle', 'en', 'Learn by working — 3 days in company, 2 days in school.'),
        # Common
        ('common.search', 'sq', 'Kërko'), ('common.search', 'mk', 'Пребарај'), ('common.search', 'en', 'Search'),
        ('common.apply', 'sq', 'Apliko'), ('common.apply', 'mk', 'Аплицирај'), ('common.apply', 'en', 'Apply'),
        ('common.save', 'sq', 'Ruaj'), ('common.save', 'mk', 'Зачувај'), ('common.save', 'en', 'Save'),
        ('common.cancel', 'sq', 'Anulo'), ('common.cancel', 'mk', 'Откажи'), ('common.cancel', 'en', 'Cancel'),
        ('common.accept', 'sq', 'Prano'), ('common.accept', 'mk', 'Прифати'), ('common.accept', 'en', 'Accept'),
        ('common.reject', 'sq', 'Refuzo'), ('common.reject', 'mk', 'Одбиј'), ('common.reject', 'en', 'Reject'),
        ('common.student', 'sq', 'Nxënës'), ('common.student', 'mk', 'Ученик'), ('common.student', 'en', 'Student'),
        ('common.company', 'sq', 'Kompani'), ('common.company', 'mk', 'Компанија'), ('common.company', 'en', 'Company'),
        ('common.school', 'sq', 'Shkollë'), ('common.school', 'mk', 'Училиште'), ('common.school', 'en', 'School'),
        ('common.profession', 'sq', 'Profesion'), ('common.profession', 'mk', 'Професија'), ('common.profession', 'en', 'Profession'),
        ('common.year', 'sq', 'vjet'), ('common.year', 'mk', 'години'), ('common.year', 'en', 'years'),
        ('common.month', 'sq', 'muaj'), ('common.month', 'mk', 'месец'), ('common.month', 'en', 'month'),
        ('common.city', 'sq', 'Qyteti'), ('common.city', 'mk', 'Град'), ('common.city', 'en', 'City'),
        ('common.all', 'sq', 'Të gjitha'), ('common.all', 'mk', 'Сите'), ('common.all', 'en', 'All'),
        # Status
        ('status.pending', 'sq', 'Në pritje'), ('status.pending', 'mk', 'Во тек'), ('status.pending', 'en', 'Pending'),
        ('status.accepted', 'sq', 'Pranuar'), ('status.accepted', 'mk', 'Прифатено'), ('status.accepted', 'en', 'Accepted'),
        ('status.rejected', 'sq', 'Refuzuar'), ('status.rejected', 'mk', 'Одбиено'), ('status.rejected', 'en', 'Rejected'),
        ('status.active', 'sq', 'Aktive'), ('status.active', 'mk', 'Активен'), ('status.active', 'en', 'Active'),
        ('status.completed', 'sq', 'Përfunduar'), ('status.completed', 'mk', 'Завршено'), ('status.completed', 'en', 'Completed'),
        # Footer
        ('footer.students', 'sq', 'Per Nxenesit'), ('footer.students', 'mk', 'За Учениците'), ('footer.students', 'en', 'For Students'),
        ('footer.companies', 'sq', 'Per Kompanitë'), ('footer.companies', 'mk', 'За Компаниите'), ('footer.companies', 'en', 'For Companies'),
        ('footer.system', 'sq', 'Rreth Sistemit'), ('footer.system', 'mk', 'За Системот'), ('footer.system', 'en', 'About the System'),
        # Pages
        ('positions.title', 'sq', 'LENA — Databaza e Pozicioneve'), ('positions.title', 'mk', 'ЛЕНА — База на Позиции'), ('positions.title', 'en', 'LENA — Position Database'),
        ('positions.subtitle', 'sq', 'Gjej apprenticeship-in e duhur tek kompanitë partnere'), ('positions.subtitle', 'mk', 'Најди го вистинскиот практикант кај партнерските компании'), ('positions.subtitle', 'en', 'Find the right apprenticeship at partner companies'),
        ('how.it.works', 'sq', 'Si Funksionon Sistemi Dual'), ('how.it.works', 'mk', 'Како Функционира Дуалниот Систем'), ('how.it.works', 'en', 'How the Dual System Works'),
    ]
    db.executemany("INSERT OR IGNORE INTO translations (key, lang, value) VALUES (?,?,?)", translations)

    # Seed sample exam for IT-001 Year 1
    it_prof = db.execute("SELECT id FROM professions WHERE code='IT-001'").fetchone()
    if it_prof:
        mod1 = db.execute("SELECT id FROM curriculum_modules WHERE profession_id=? AND order_index=1", (it_prof[0],)).fetchone()
        if mod1:
            existing_exam = db.execute("SELECT id FROM exams WHERE module_id=?", (mod1[0],)).fetchone()
            if not existing_exam:
                db.execute("INSERT INTO exams (module_id, title, description, duration_minutes, pass_grade) VALUES (?,?,?,?,?)",
                    (mod1[0], 'Provimi: Bazat e Programimit', 'Provim teorik per modulin e vitit te pare', 45, 4.0))
                exam_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                questions = [
                    (exam_id, 'Cfare eshte nje variabel ne programim?', 'multiple_choice',
                     '["Nje vend ne memorie per ruajtjen e te dhenave", "Nje lloj kompjuteri", "Nje gjuhe programimi", "Nje sistem operativ"]',
                     '0', 1, 1),
                    (exam_id, 'Cili nga keta eshte nje lloj i te dhenave (data type)?', 'multiple_choice',
                     '["Integer", "Monitor", "Tastiere", "Printer"]', '0', 1, 2),
                    (exam_id, 'Cfare ben nje loop (cikel) ne programim?', 'multiple_choice',
                     '["Perserit nje bllok kodi", "Fshin te dhenat", "Printon dokumente", "Lidhte me internet"]', '0', 1, 3),
                    (exam_id, 'Cfare eshte nje funksion (function)?', 'multiple_choice',
                     '["Bllok kodi i riperdorshem", "Nje lloj database", "Nje pajisje hardware", "Nje protokoll rrjete"]', '0', 1, 4),
                    (exam_id, 'Cili operator perdoret per krahasim ne shumicen e gjuheve?', 'multiple_choice',
                     '["==", "++", "//", "<<"]', '0', 1, 5),
                    (exam_id, 'Cfare eshte nje array (varg)?', 'multiple_choice',
                     '["Koleksion i te dhenave te renditura", "Nje lloj printeri", "Nje protokoll sigurie", "Nje sistem operativ"]', '0', 1, 6),
                    (exam_id, 'Shpjego me fjalet e tua cfare eshte nje algoritem dhe jep nje shembull nga jeta e perditshme.', 'essay',
                     None, None, 4, 7),
                ]
                db.executemany("""INSERT INTO exam_questions (exam_id, question_text, question_type, options, correct_answer, points, order_index)
                    VALUES (?,?,?,?,?,?,?)""", questions)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

# ============================================================
# PAGE ROUTES
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/positions')
def positions_page():
    return render_template('positions.html')

@app.route('/professions')
def professions_page():
    return render_template('professions.html')

@app.route('/api-docs')
def api_docs_page():
    return render_template('api_docs.html')

# ============================================================
# API ROUTES
# ============================================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    db = get_db()

    try:
        db.execute(
            "INSERT INTO users (email, password_hash, role, full_name, phone, city, country) VALUES (?,?,?,?,?,?,?)",
            (data['email'], hash_password(data['password']), data['role'],
             data['full_name'], data.get('phone', ''), data.get('city', ''), data.get('country', 'North Macedonia'))
        )
        db.commit()

        user = db.execute("SELECT * FROM users WHERE email=?", (data['email'],)).fetchone()

        # Create role-specific profile
        if data['role'] == 'student':
            db.execute("INSERT INTO student_profiles (user_id) VALUES (?)", (user['id'],))
        elif data['role'] == 'company':
            db.execute("INSERT INTO company_profiles (user_id, company_name) VALUES (?,?)",
                      (user['id'], data.get('company_name', data['full_name'])))
        elif data['role'] == 'school':
            db.execute("INSERT INTO school_profiles (user_id, school_name) VALUES (?,?)",
                      (user['id'], data.get('school_name', data['full_name'])))

        db.commit()
        session['user_id'] = user['id']
        session['role'] = user['role']
        session['full_name'] = user['full_name']

        return jsonify({'success': True, 'user': {'id': user['id'], 'role': user['role'], 'name': user['full_name']}})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Email tashmë ekziston'}), 400

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    db = get_db()

    user = db.execute("SELECT * FROM users WHERE email=? AND password_hash=?",
                      (data['email'], hash_password(data['password']))).fetchone()

    if user:
        session['user_id'] = user['id']
        session['role'] = user['role']
        session['full_name'] = user['full_name']
        return jsonify({'success': True, 'user': {'id': user['id'], 'role': user['role'], 'name': user['full_name']}})

    return jsonify({'success': False, 'error': 'Email ose fjalëkalimi i gabuar'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/auth/me')
def get_current_user():
    if 'user_id' not in session:
        return jsonify({'authenticated': False})

    db = get_db()
    user = db.execute("SELECT id, email, role, full_name, city, country FROM users WHERE id=?",
                      (session['user_id'],)).fetchone()
    if user:
        return jsonify({'authenticated': True, 'user': dict(user)})
    return jsonify({'authenticated': False})

# --- Professions API ---
@app.route('/api/professions')
def get_professions():
    db = get_db()
    category = request.args.get('category')
    qualification = request.args.get('qualification')
    search = request.args.get('search', '')

    query = "SELECT * FROM professions WHERE is_active=1"
    params = []

    if category:
        query += " AND category=?"
        params.append(category)
    if qualification:
        query += " AND qualification_type=?"
        params.append(qualification)
    if search:
        query += " AND (name_sq LIKE ? OR name_en LIKE ? OR description LIKE ?)"
        params.extend([f'%{search}%'] * 3)

    professions = db.execute(query + " ORDER BY category, name_sq", params).fetchall()
    return jsonify([dict(p) for p in professions])

@app.route('/api/professions/<int:profession_id>')
def get_profession(profession_id):
    db = get_db()
    profession = db.execute("SELECT * FROM professions WHERE id=?", (profession_id,)).fetchone()
    if not profession:
        return jsonify({'error': 'Profesioni nuk u gjet'}), 404

    modules = db.execute("SELECT * FROM curriculum_modules WHERE profession_id=? ORDER BY year, order_index",
                         (profession_id,)).fetchall()

    positions = db.execute("""
        SELECT ap.*, cp.company_name
        FROM apprenticeship_positions ap
        JOIN company_profiles cp ON ap.company_id=cp.id
        WHERE ap.profession_id=? AND ap.is_active=1
    """, (profession_id,)).fetchall()

    return jsonify({
        'profession': dict(profession),
        'curriculum': [dict(m) for m in modules],
        'positions': [dict(p) for p in positions]
    })

@app.route('/api/professions/categories')
def get_categories():
    db = get_db()
    categories = db.execute("SELECT DISTINCT category FROM professions WHERE is_active=1 ORDER BY category").fetchall()
    return jsonify([c['category'] for c in categories])

# --- Positions API (LENA equivalent) ---
@app.route('/api/positions')
def get_positions():
    db = get_db()
    city = request.args.get('city')
    category = request.args.get('category')
    search = request.args.get('search', '')

    query = """
        SELECT ap.*, cp.company_name, cp.industry, p.name_sq as profession_name,
               p.category, p.duration_years, p.qualification_type
        FROM apprenticeship_positions ap
        JOIN company_profiles cp ON ap.company_id=cp.id
        JOIN professions p ON ap.profession_id=p.id
        WHERE ap.is_active=1
    """
    params = []

    if city:
        query += " AND ap.city=?"
        params.append(city)
    if category:
        query += " AND p.category=?"
        params.append(category)
    if search:
        query += " AND (ap.title LIKE ? OR cp.company_name LIKE ? OR p.name_sq LIKE ?)"
        params.extend([f'%{search}%'] * 3)

    # Sorting
    sort = request.args.get('sort', 'newest')
    sort_map = {
        'newest': 'ap.created_at DESC',
        'salary_high': 'COALESCE(ap.salary_monthly, 0) DESC',
        'salary_low': 'COALESCE(ap.salary_monthly, 0) ASC',
        'start_date': 'ap.start_date ASC',
        'available': '(ap.positions_available - COALESCE(ap.positions_filled, 0)) DESC'
    }
    order = sort_map.get(sort, 'ap.created_at DESC')

    # Pagination
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(50, max(1, int(request.args.get('per_page', 15))))
    offset = (page - 1) * per_page

    # Get total count
    count_query = query.replace(
        "SELECT ap.*, cp.company_name, cp.industry, p.name_sq as profession_name,\n               p.category, p.duration_years, p.qualification_type",
        "SELECT COUNT(*) as total"
    )
    total = db.execute(count_query, params).fetchone()['total']

    positions = db.execute(query + f" ORDER BY {order} LIMIT ? OFFSET ?", params + [per_page, offset]).fetchall()
    return jsonify({
        'positions': [dict(p) for p in positions],
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    })

@app.route('/api/positions/<int:position_id>')
def get_position(position_id):
    db = get_db()
    position = db.execute("""
        SELECT ap.*, cp.company_name, cp.description as company_description, cp.industry, cp.website,
               cp.user_id as company_user_id, cp.is_verified as company_verified,
               p.name_sq as profession_name, p.category, p.duration_years, p.qualification_type,
               p.school_days_per_week, p.company_days_per_week, p.description as profession_description
        FROM apprenticeship_positions ap
        JOIN company_profiles cp ON ap.company_id=cp.id
        JOIN professions p ON ap.profession_id=p.id
        WHERE ap.id=?
    """, (position_id,)).fetchone()

    if not position:
        return jsonify({'error': 'Pozicioni nuk u gjet'}), 404
    return jsonify(dict(position))

@app.route('/api/positions', methods=['POST'])
@login_required
def create_position():
    if session.get('role') != 'company':
        return jsonify({'error': 'Vetëm kompanitë mund të krijojnë pozicione'}), 403

    data = request.json
    db = get_db()

    company = db.execute("SELECT id FROM company_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
    if not company:
        return jsonify({'error': 'Profili i kompanisë nuk u gjet'}), 404

    db.execute("""INSERT INTO apprenticeship_positions
        (company_id, profession_id, title, description, requirements, positions_available, start_date, salary_monthly, city)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (company['id'], data['profession_id'], data['title'], data.get('description', ''),
         data.get('requirements', ''), data.get('positions_available', 1),
         data.get('start_date'), data.get('salary_monthly'), data.get('city', '')))
    db.commit()

    return jsonify({'success': True, 'message': 'Pozicioni u krijua me sukses'})

# --- Applications API ---
@app.route('/api/applications', methods=['POST'])
@login_required
def apply():
    if session.get('role') != 'student':
        return jsonify({'error': 'Vetëm nxënësit mund të aplikojnë'}), 403

    data = request.json
    db = get_db()

    cover_letter = (data.get('cover_letter') or '').strip()
    if len(cover_letter) < 10:
        return jsonify({'error': 'Letra motivuese duhet të ketë minimum 10 karaktere'}), 400

    position = db.execute("SELECT id, positions_available, positions_filled FROM apprenticeship_positions WHERE id=? AND is_active=1", (data.get('position_id'),)).fetchone()
    if not position:
        return jsonify({'error': 'Pozicioni nuk ekziston ose nuk është aktiv'}), 404
    if position['positions_filled'] >= position['positions_available']:
        return jsonify({'error': 'Nuk ka më vende të lira për këtë pozicion'}), 400

    student = db.execute("SELECT id FROM student_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
    if not student:
        return jsonify({'error': 'Profili i nxënësit nuk u gjet'}), 404

    try:
        db.execute("INSERT INTO applications (student_id, position_id, cover_letter) VALUES (?,?,?)",
                  (student['id'], data['position_id'], cover_letter))
        app_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("INSERT INTO application_history (application_id, old_status, new_status, changed_by, note) VALUES (?,?,?,?,?)",
                   (app_id, None, 'pending', session['user_id'], 'Aplikimi u dërgua'))
        db.commit()
        return jsonify({'success': True, 'message': 'Aplikimi u dërgua me sukses'})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Tashmë keni aplikuar për këtë pozicion'}), 400

@app.route('/api/applications')
@login_required
def get_applications():
    db = get_db()

    if session['role'] == 'student':
        student = db.execute("SELECT id FROM student_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
        apps = db.execute("""
            SELECT a.*, ap.title, cp.company_name, p.name_sq as profession_name
            FROM applications a
            JOIN apprenticeship_positions ap ON a.position_id=ap.id
            JOIN company_profiles cp ON ap.company_id=cp.id
            JOIN professions p ON ap.profession_id=p.id
            WHERE a.student_id=?
            ORDER BY a.applied_at DESC
        """, (student['id'],)).fetchall()
    elif session['role'] == 'company':
        company = db.execute("SELECT id FROM company_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
        apps = db.execute("""
            SELECT a.*, ap.title, u.full_name as student_name, p.name_sq as profession_name, sp.school_name
            FROM applications a
            JOIN apprenticeship_positions ap ON a.position_id=ap.id
            JOIN student_profiles sp ON a.student_id=sp.id
            JOIN users u ON sp.user_id=u.id
            JOIN professions p ON ap.profession_id=p.id
            WHERE ap.company_id=?
            ORDER BY a.applied_at DESC
        """, (company['id'],)).fetchall()
    else:
        return jsonify([])

    return jsonify([dict(a) for a in apps])

@app.route('/api/applications/<int:app_id>', methods=['PUT'])
@login_required
def update_application(app_id):
    data = request.json
    db = get_db()
    db.execute("UPDATE applications SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
              (data['status'], app_id))
    db.commit()
    return jsonify({'success': True})

# --- Dashboard Stats API ---
@app.route('/api/stats')
def get_stats():
    db = get_db()
    stats = {
        'total_professions': db.execute("SELECT COUNT(*) FROM professions WHERE is_active=1").fetchone()[0],
        'total_positions': db.execute("SELECT COUNT(*) FROM apprenticeship_positions WHERE is_active=1").fetchone()[0],
        'total_companies': db.execute("SELECT COUNT(*) FROM company_profiles").fetchone()[0],
        'total_students': db.execute("SELECT COUNT(*) FROM student_profiles").fetchone()[0],
        'total_contracts': db.execute("SELECT COUNT(*) FROM apprenticeship_contracts WHERE status='active'").fetchone()[0],
        'total_certificates': db.execute("SELECT COUNT(*) FROM certificates").fetchone()[0],
        'positions_by_city': [dict(r) for r in db.execute(
            "SELECT city, COUNT(*) as count FROM apprenticeship_positions WHERE is_active=1 GROUP BY city ORDER BY count DESC"
        ).fetchall()],
        'positions_by_category': [dict(r) for r in db.execute("""
            SELECT p.category, COUNT(*) as count
            FROM apprenticeship_positions ap
            JOIN professions p ON ap.profession_id=p.id
            WHERE ap.is_active=1 GROUP BY p.category ORDER BY count DESC
        """).fetchall()],
    }
    return jsonify(stats)

@app.route('/api/dashboard')
@login_required
def get_dashboard_data():
    db = get_db()
    role = session['role']
    user_id = session['user_id']

    data = {'role': role}

    if role == 'student':
        profile = db.execute("SELECT * FROM student_profiles WHERE user_id=?", (user_id,)).fetchone()
        if profile:
            data['profile'] = dict(profile)
            data['applications'] = [dict(a) for a in db.execute("""
                SELECT a.*, ap.title, cp.company_name
                FROM applications a
                JOIN apprenticeship_positions ap ON a.position_id=ap.id
                JOIN company_profiles cp ON ap.company_id=cp.id
                WHERE a.student_id=?
                ORDER BY a.applied_at DESC LIMIT 5
            """, (profile['id'],)).fetchall()]
            data['contracts'] = [dict(c) for c in db.execute("""
                SELECT ac.*, cp.company_name, p.name_sq as profession_name
                FROM apprenticeship_contracts ac
                JOIN company_profiles cp ON ac.company_id=cp.id
                JOIN professions p ON ac.profession_id=p.id
                WHERE ac.student_id=?
            """, (profile['id'],)).fetchall()]

    elif role == 'company':
        profile = db.execute("SELECT * FROM company_profiles WHERE user_id=?", (user_id,)).fetchone()
        if profile:
            data['profile'] = dict(profile)
            data['positions'] = [dict(p) for p in db.execute("""
                SELECT ap.*, pr.name_sq as profession_name
                FROM apprenticeship_positions ap
                JOIN professions pr ON ap.profession_id=pr.id
                WHERE ap.company_id=?
                ORDER BY ap.created_at DESC
            """, (profile['id'],)).fetchall()]
            data['applications_received'] = db.execute("""
                SELECT COUNT(*) FROM applications a
                JOIN apprenticeship_positions ap ON a.position_id=ap.id
                WHERE ap.company_id=? AND a.status='pending'
            """, (profile['id'],)).fetchone()[0]
            data['active_apprentices'] = db.execute("""
                SELECT COUNT(*) FROM apprenticeship_contracts
                WHERE company_id=? AND status='active'
            """, (profile['id'],)).fetchone()[0]

    elif role == 'school':
        profile = db.execute("SELECT * FROM school_profiles WHERE user_id=?", (user_id,)).fetchone()
        if profile:
            data['profile'] = dict(profile)

    return jsonify(data)

# --- Profile update API ---
@app.route('/api/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.json
    db = get_db()
    role = session['role']
    user_id = session['user_id']

    if role == 'student':
        db.execute("""UPDATE student_profiles SET
            date_of_birth=?, education_level=?, school_name=?, gpa=?,
            interests=?, skills=?, languages=?, bio=?, preferred_professions=?
            WHERE user_id=?""",
            (data.get('date_of_birth'), data.get('education_level'), data.get('school_name'),
             data.get('gpa'), json.dumps(data.get('interests', [])), json.dumps(data.get('skills', [])),
             json.dumps(data.get('languages', [])), data.get('bio'),
             json.dumps(data.get('preferred_professions', [])), user_id))
    elif role == 'company':
        db.execute("""UPDATE company_profiles SET
            company_name=?, industry=?, company_size=?, description=?, website=?, address=?
            WHERE user_id=?""",
            (data.get('company_name'), data.get('industry'), data.get('company_size'),
             data.get('description'), data.get('website'), data.get('address'), user_id))

    db.commit()
    return jsonify({'success': True})

# --- Password Change ---
@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.json
    db = get_db()
    old_pw = data.get('old_password', '')
    new_pw = data.get('new_password', '')
    if len(new_pw) < 6:
        return jsonify({'error': 'Fjalëkalimi i ri duhet të ketë minimum 6 karaktere'}), 400
    user = db.execute("SELECT password_hash FROM users WHERE id=?", (session['user_id'],)).fetchone()
    if not user or user['password_hash'] != hashlib.sha256(old_pw.encode()).hexdigest():
        return jsonify({'error': 'Fjalëkalimi aktual nuk është i saktë'}), 400
    db.execute("UPDATE users SET password_hash=? WHERE id=?",
               (hashlib.sha256(new_pw.encode()).hexdigest(), session['user_id']))
    db.commit()
    return jsonify({'success': True, 'message': 'Fjalëkalimi u ndryshua me sukses!'})

# --- CSV Export for Government ---
@app.route('/api/admin/export/<string:export_type>')
@login_required
def export_csv(export_type):
    if session.get('role') != 'government':
        return jsonify({'error': 'Vetëm qeveria ka akses'}), 403
    db = get_db()
    import csv
    output = io.StringIO()
    writer = csv.writer(output)

    if export_type == 'positions':
        writer.writerow(['ID', 'Titulli', 'Kompania', 'Profesioni', 'Qyteti', 'Vende', 'Rroga', 'Data fillimit', 'Aktiv'])
        rows = db.execute("""SELECT ap.id, ap.title, cp.company_name, p.name_sq, ap.city,
            ap.positions_available, ap.salary_monthly, ap.start_date, ap.is_active
            FROM apprenticeship_positions ap
            JOIN professions p ON ap.profession_id=p.id
            JOIN company_profiles cp ON ap.company_id=cp.user_id""").fetchall()
        for r in rows:
            writer.writerow([r['id'], r['title'], r['company_name'], r['name_sq'], r['city'],
                           r['positions_available'], r['salary_monthly'], r['start_date'], r['is_active']])
    elif export_type == 'contracts':
        writer.writerow(['ID', 'Nxënësi', 'Kompania', 'Profesioni', 'Fillimi', 'Fundi', 'Statusi'])
        rows = db.execute("""SELECT ac.id, u.full_name as student_name, cp.company_name, p.name_sq,
            ac.start_date, ac.end_date, ac.status
            FROM apprenticeship_contracts ac
            JOIN users u ON ac.student_id=u.id
            JOIN company_profiles cp ON ac.company_id=cp.user_id
            JOIN professions p ON ac.profession_id=p.id""").fetchall()
        for r in rows:
            writer.writerow([r['id'], r['student_name'], r['company_name'], r['name_sq'],
                           r['start_date'], r['end_date'], r['status']])
    elif export_type == 'students':
        writer.writerow(['ID', 'Emri', 'Email', 'Qyteti', 'Shkolla', 'GPA', 'Data regjistrimit'])
        rows = db.execute("""SELECT u.id, u.full_name, u.email, u.city, sp.school_name, sp.gpa, u.created_at
            FROM users u LEFT JOIN student_profiles sp ON u.id=sp.user_id
            WHERE u.role='student'""").fetchall()
        for r in rows:
            writer.writerow([r['id'], r['full_name'], r['email'], r['city'],
                           r['school_name'], r['gpa'], r['created_at']])
    else:
        return jsonify({'error': 'Lloji i eksportit nuk njihet'}), 400

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'berufsbildung_{export_type}_{datetime.now().strftime("%Y%m%d")}.csv'
    )

# --- Cities API ---
@app.route('/api/cities')
def get_cities():
    db = get_db()
    cities = db.execute("SELECT DISTINCT city FROM apprenticeship_positions WHERE is_active=1 AND city IS NOT NULL ORDER BY city").fetchall()
    return jsonify([c['city'] for c in cities])

# --- Notification System ---
def create_notification(db, user_id, title, message, ntype='info'):
    db.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (?,?,?,?)",
              (user_id, title, message, ntype))

def _auto_generate_schedule_for(db, contract_id, user_id):
    """Internal helper to auto-generate weekly schedule for a contract"""
    contract = db.execute("""
        SELECT ac.*, p.company_days_per_week, p.school_days_per_week, p.name_sq,
               cp.company_name, cp.address as company_addr
        FROM apprenticeship_contracts ac
        JOIN professions p ON ac.profession_id=p.id
        JOIN company_profiles cp ON ac.company_id=cp.id
        WHERE ac.id=?
    """, (contract_id,)).fetchone()
    if not contract:
        return
    db.execute("DELETE FROM schedule_events WHERE contract_id=? AND user_id=?", (contract_id, user_id))
    for i in range(contract['company_days_per_week']):
        db.execute("""INSERT INTO schedule_events (user_id, contract_id, title, event_type, day_of_week, start_time, end_time, location)
            VALUES (?,?,?,?,?,?,?,?)""",
            (user_id, contract_id, f"{contract['company_name']} - Praktike",
             'company', i, '08:00', '16:30', contract['company_addr'] or ''))
    for i in range(contract['school_days_per_week']):
        day = contract['company_days_per_week'] + i
        db.execute("""INSERT INTO schedule_events (user_id, contract_id, title, event_type, day_of_week, start_time, end_time, location)
            VALUES (?,?,?,?,?,?,?,?)""",
            (user_id, contract_id, f"Shkolla Profesionale - {contract['name_sq']}",
             'school', day, '08:00', '15:00', 'Shkolla e Mesme Profesionale'))

@app.route('/api/notifications')
@login_required
def get_notifications():
    db = get_db()
    notifs = db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
                        (session['user_id'],)).fetchall()
    unread = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0",
                        (session['user_id'],)).fetchone()[0]
    return jsonify({'notifications': [dict(n) for n in notifs], 'unread_count': unread})

@app.route('/api/notifications/read-all', methods=['POST'])
@login_required
def read_all_notifications():
    db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (session['user_id'],))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/notifications/<int:nid>/read', methods=['PUT'])
@login_required
def read_notification(nid):
    db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (nid, session['user_id']))
    db.commit()
    return jsonify({'success': True})

# --- Enhanced Application Management ---
@app.route('/api/applications/<int:app_id>/student')
@login_required
def get_application_student(app_id):
    """Company views student profile for an application"""
    db = get_db()
    company = db.execute("SELECT id FROM company_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
    if not company:
        return jsonify({'error': 'Jo kompani'}), 403

    student = db.execute("""
        SELECT u.full_name, u.email, u.phone, u.city, sp.*
        FROM applications a
        JOIN apprenticeship_positions ap ON a.position_id=ap.id
        JOIN student_profiles sp ON a.student_id=sp.id
        JOIN users u ON sp.user_id=u.id
        WHERE a.id=? AND ap.company_id=?
    """, (app_id, company['id'])).fetchone()

    if not student:
        return jsonify({'error': 'Nuk u gjet'}), 404
    return jsonify(dict(student))

@app.route('/api/applications/<int:app_id>/accept', methods=['POST'])
@login_required
def accept_application(app_id):
    """Accept application and create contract"""
    db = get_db()
    company = db.execute("SELECT id FROM company_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
    if not company:
        return jsonify({'error': 'Jo kompani'}), 403

    # Get full application details
    app_data = db.execute("""
        SELECT a.*, ap.company_id, ap.profession_id, ap.start_date, ap.salary_monthly, ap.positions_available, ap.positions_filled,
               p.duration_years, p.name_sq as profession_name, sp.user_id as student_user_id
        FROM applications a
        JOIN apprenticeship_positions ap ON a.position_id=ap.id
        JOIN professions p ON ap.profession_id=p.id
        JOIN student_profiles sp ON a.student_id=sp.id
        WHERE a.id=? AND ap.company_id=?
    """, (app_id, company['id'])).fetchone()

    if not app_data:
        return jsonify({'error': 'Aplikimi nuk u gjet'}), 404

    if app_data['status'] != 'pending' and app_data['status'] != 'interview':
        return jsonify({'error': 'Aplikimi tashmë është procesuar'}), 400

    # Update application status + history
    db.execute("INSERT INTO application_history (application_id, old_status, new_status, changed_by, note) VALUES (?,?,?,?,?)",
               (app_id, app_data['status'], 'accepted', session['user_id'], 'Aplikimi u pranua nga kompania'))
    db.execute("UPDATE applications SET status='accepted', updated_at=CURRENT_TIMESTAMP WHERE id=?", (app_id,))

    # Calculate end date
    start = app_data['start_date'] or datetime.now().strftime('%Y-%m-%d')
    try:
        start_dt = datetime.strptime(start, '%Y-%m-%d')
        end_dt = start_dt.replace(year=start_dt.year + app_data['duration_years'])
        end = end_dt.strftime('%Y-%m-%d')
    except:
        end = start

    # Create contract
    db.execute("""INSERT INTO apprenticeship_contracts
        (student_id, company_id, profession_id, start_date, end_date, salary_monthly, status)
        VALUES (?,?,?,?,?,?,?)""",
        (app_data['student_id'], company['id'], app_data['profession_id'],
         start, end, app_data['salary_monthly'], 'active'))

    contract_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Auto-create progress entries for all modules
    modules = db.execute("SELECT id FROM curriculum_modules WHERE profession_id=?",
                         (app_data['profession_id'],)).fetchall()
    for m in modules:
        db.execute("INSERT INTO student_progress (contract_id, module_id, status) VALUES (?,?,'not_started')",
                  (contract_id, m['id']))

    # Update positions filled
    db.execute("UPDATE apprenticeship_positions SET positions_filled=positions_filled+1 WHERE id=?",
              (app_data['position_id'],))

    # Auto-generate weekly schedule for student
    _auto_generate_schedule_for(db, contract_id, app_data['student_user_id'])

    # Notify student
    create_notification(db, app_data['student_user_id'],
        'Aplikimi u pranua!',
        f'Aplikimi juaj për "{app_data["profession_name"]}" u pranua. Kontrata dhe orari juaj janë krijuar.',
        'success')

    db.commit()
    return jsonify({'success': True, 'contract_id': contract_id, 'message': 'Aplikimi u pranua dhe kontrata u krijua!'})

@app.route('/api/applications/<int:app_id>/reject', methods=['POST'])
@login_required
def reject_application(app_id):
    db = get_db()
    company = db.execute("SELECT id FROM company_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
    if not company:
        return jsonify({'error': 'Jo kompani'}), 403

    app_data = db.execute("""
        SELECT a.student_id, sp.user_id as student_user_id, ap.title
        FROM applications a
        JOIN apprenticeship_positions ap ON a.position_id=ap.id
        JOIN student_profiles sp ON a.student_id=sp.id
        WHERE a.id=? AND ap.company_id=?
    """, (app_id, company['id'])).fetchone()

    if not app_data:
        return jsonify({'error': 'Nuk u gjet'}), 404

    db.execute("INSERT INTO application_history (application_id, old_status, new_status, changed_by, note) VALUES (?,?,?,?,?)",
               (app_id, 'pending', 'rejected', session['user_id'], 'Aplikimi u refuzua nga kompania'))
    db.execute("UPDATE applications SET status='rejected', updated_at=CURRENT_TIMESTAMP WHERE id=?", (app_id,))

    create_notification(db, app_data['student_user_id'],
        'Aplikimi u refuzua',
        f'Fatkeqësisht, aplikimi juaj për "{app_data["title"]}" nuk u pranua.',
        'warning')

    db.commit()
    return jsonify({'success': True})

# --- Contracts API ---
@app.route('/api/contracts')
@login_required
def get_contracts():
    db = get_db()
    if session['role'] == 'student':
        profile = db.execute("SELECT id FROM student_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
        contracts = db.execute("""
            SELECT ac.*, cp.company_name, p.name_sq as profession_name, p.duration_years
            FROM apprenticeship_contracts ac
            JOIN company_profiles cp ON ac.company_id=cp.id
            JOIN professions p ON ac.profession_id=p.id
            WHERE ac.student_id=?
        """, (profile['id'],)).fetchall()
    elif session['role'] == 'company':
        profile = db.execute("SELECT id FROM company_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
        contracts = db.execute("""
            SELECT ac.*, u.full_name as student_name, p.name_sq as profession_name, p.duration_years
            FROM apprenticeship_contracts ac
            JOIN student_profiles sp ON ac.student_id=sp.id
            JOIN users u ON sp.user_id=u.id
            JOIN professions p ON ac.profession_id=p.id
            WHERE ac.company_id=?
        """, (profile['id'],)).fetchall()
    else:
        return jsonify([])
    return jsonify([dict(c) for c in contracts])

# --- Progress Tracking API ---
@app.route('/api/contracts/<int:contract_id>/progress')
@login_required
def get_progress(contract_id):
    db = get_db()
    contract = db.execute("SELECT * FROM apprenticeship_contracts WHERE id=?", (contract_id,)).fetchone()
    if not contract:
        return jsonify({'error': 'Kontrata nuk u gjet'}), 404

    progress = db.execute("""
        SELECT sp.*, cm.module_name, cm.module_type, cm.year, cm.hours, cm.description as module_desc, cm.order_index
        FROM student_progress sp
        JOIN curriculum_modules cm ON sp.module_id=cm.id
        WHERE sp.contract_id=?
        ORDER BY cm.year, cm.order_index
    """, (contract_id,)).fetchall()

    total = len(progress)
    completed = sum(1 for p in progress if p['status'] == 'completed')

    return jsonify({
        'progress': [dict(p) for p in progress],
        'total_modules': total,
        'completed_modules': completed,
        'completion_percent': round((completed / total * 100) if total > 0 else 0, 1)
    })

@app.route('/api/progress/<int:progress_id>', methods=['PUT'])
@login_required
def update_progress(progress_id):
    """Company updates student's module progress"""
    data = request.json
    db = get_db()

    db.execute("""UPDATE student_progress SET
        status=?, grade=?, completion_date=?, evaluator_notes=?
        WHERE id=?""",
        (data.get('status'), data.get('grade'), data.get('completion_date'),
         data.get('evaluator_notes'), progress_id))
    db.commit()
    return jsonify({'success': True})

# --- Favorites / Bookmarks ---
@app.route('/api/favorites')
@login_required
def get_favorites():
    db = get_db()
    favs = db.execute("""
        SELECT f.id, f.position_id, f.created_at, ap.title, ap.city, ap.salary_monthly,
               cp.company_name, p.name_sq as profession_name, p.qualification_type, p.duration_years
        FROM favorites f
        JOIN apprenticeship_positions ap ON f.position_id=ap.id
        JOIN company_profiles cp ON ap.company_id=cp.id
        JOIN professions p ON ap.profession_id=p.id
        WHERE f.user_id=?
        ORDER BY f.created_at DESC
    """, (session['user_id'],)).fetchall()
    return jsonify([dict(f) for f in favs])

@app.route('/api/favorites', methods=['POST'])
@login_required
def toggle_favorite():
    data = request.json
    db = get_db()
    position_id = data.get('position_id')
    existing = db.execute("SELECT id FROM favorites WHERE user_id=? AND position_id=?",
                          (session['user_id'], position_id)).fetchone()
    if existing:
        db.execute("DELETE FROM favorites WHERE id=?", (existing['id'],))
        db.commit()
        return jsonify({'success': True, 'favorited': False, 'message': 'U hoq nga të ruajturat'})
    else:
        db.execute("INSERT INTO favorites (user_id, position_id) VALUES (?,?)",
                   (session['user_id'], position_id))
        db.commit()
        return jsonify({'success': True, 'favorited': True, 'message': 'U ruajt!'})

@app.route('/api/favorites/<int:position_id>/check')
@login_required
def check_favorite(position_id):
    db = get_db()
    fav = db.execute("SELECT id FROM favorites WHERE user_id=? AND position_id=?",
                     (session['user_id'], position_id)).fetchone()
    return jsonify({'favorited': fav is not None})

# --- Application Timeline ---
@app.route('/api/applications/<int:app_id>/timeline')
@login_required
def get_application_timeline(app_id):
    db = get_db()
    history = db.execute("""
        SELECT ah.*, u.full_name as changed_by_name
        FROM application_history ah
        LEFT JOIN users u ON ah.changed_by=u.id
        WHERE ah.application_id=?
        ORDER BY ah.created_at ASC
    """, (app_id,)).fetchall()
    return jsonify([dict(h) for h in history])

# --- Company Public Profile ---
@app.route('/api/companies/<int:company_user_id>/profile')
def get_company_public_profile(company_user_id):
    db = get_db()
    company = db.execute("""
        SELECT cp.*, u.full_name, u.city, u.phone
        FROM company_profiles cp
        JOIN users u ON cp.user_id=u.id
        WHERE cp.user_id=?
    """, (company_user_id,)).fetchone()
    if not company:
        return jsonify({'error': 'Kompania nuk u gjet'}), 404

    positions = db.execute("""
        SELECT ap.*, p.name_sq as profession_name, p.qualification_type
        FROM apprenticeship_positions ap
        JOIN professions p ON ap.profession_id=p.id
        WHERE ap.company_id=? AND ap.is_active=1
    """, (company['id'],)).fetchall()

    reviews = db.execute("""
        SELECT r.rating, r.review_text, r.created_at, u.full_name as reviewer_name
        FROM reviews r JOIN users u ON r.reviewer_id=u.id
        WHERE r.reviewed_id=? AND r.review_type='student_to_company'
        ORDER BY r.created_at DESC LIMIT 10
    """, (company_user_id,)).fetchall()

    avg_rating = db.execute("SELECT AVG(rating) as avg FROM reviews WHERE reviewed_id=? AND review_type='student_to_company'",
                            (company_user_id,)).fetchone()

    return jsonify({
        'company': dict(company),
        'positions': [dict(p) for p in positions],
        'reviews': [dict(r) for r in reviews],
        'avg_rating': round(avg_rating['avg'], 1) if avg_rating['avg'] else None,
        'total_reviews': len(reviews)
    })

# --- Company Verification (Government) ---
@app.route('/api/admin/verify-company/<int:company_id>', methods=['POST'])
@login_required
def verify_company(company_id):
    if session.get('role') != 'government':
        return jsonify({'error': 'Vetëm qeveria ka akses'}), 403
    db = get_db()
    db.execute("UPDATE company_profiles SET is_verified=1 WHERE id=?", (company_id,))
    company = db.execute("SELECT user_id FROM company_profiles WHERE id=?", (company_id,)).fetchone()
    if company:
        create_notification(db, company['user_id'], 'Kompania u verifikua!',
                          'Kompania juaj tani është e verifikuar nga Ministria e Arsimit.', 'success')
    db.commit()
    return jsonify({'success': True, 'message': 'Kompania u verifikua!'})

@app.route('/api/admin/unverify-company/<int:company_id>', methods=['POST'])
@login_required
def unverify_company(company_id):
    if session.get('role') != 'government':
        return jsonify({'error': 'Vetëm qeveria ka akses'}), 403
    db = get_db()
    db.execute("UPDATE company_profiles SET is_verified=0 WHERE id=?", (company_id,))
    db.commit()
    return jsonify({'success': True})

# --- Profession Comparison ---
@app.route('/api/professions/compare')
def compare_professions():
    ids = request.args.get('ids', '')
    id_list = [int(x) for x in ids.split(',') if x.strip().isdigit()]
    if len(id_list) < 2 or len(id_list) > 4:
        return jsonify({'error': 'Zgjidh 2-4 profesione për krahasim'}), 400
    db = get_db()
    placeholders = ','.join('?' * len(id_list))
    profs = db.execute(f"SELECT * FROM professions WHERE id IN ({placeholders})", id_list).fetchall()
    result = []
    for p in profs:
        modules = db.execute("SELECT COUNT(*) as cnt, SUM(hours) as total_hours FROM curriculum_modules WHERE profession_id=?", (p['id'],)).fetchone()
        positions = db.execute("SELECT COUNT(*) as cnt FROM apprenticeship_positions WHERE profession_id=? AND is_active=1", (p['id'],)).fetchone()
        result.append({
            **dict(p),
            'total_modules': modules['cnt'],
            'total_hours': modules['total_hours'] or 0,
            'open_positions': positions['cnt']
        })
    return jsonify(result)

# --- Contract PDF ---
@app.route('/api/contracts/<int:contract_id>/pdf')
@login_required
def download_contract_pdf(contract_id):
    db = get_db()
    contract = db.execute("""
        SELECT ac.*, p.name_sq as profession_name, p.qualification_type, p.duration_years,
               p.company_days_per_week, p.school_days_per_week,
               u.full_name as student_name, u.city as student_city, u.phone as student_phone,
               cp.company_name, cp.address as company_address, cu.phone as company_phone
        FROM apprenticeship_contracts ac
        JOIN professions p ON ac.profession_id=p.id
        JOIN student_profiles sp ON ac.student_id=sp.id
        JOIN users u ON sp.user_id=u.id
        JOIN company_profiles cp ON ac.company_id=cp.id
        JOIN users cu ON cp.user_id=cu.id
        WHERE ac.id=?
    """, (contract_id,)).fetchone()

    if not contract:
        return jsonify({'error': 'Kontrata nuk u gjet'}), 404

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(0, 15, 'KONTRATA E APPRENTICESHIP-IT', ln=True, align='C')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 8, 'Sipas modelit zviceran te arsimit profesional dual', ln=True, align='C')
    pdf.cell(0, 8, f'Nr. Kontrates: AP-{contract["id"]:04d}', ln=True, align='C')
    pdf.ln(10)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, '1. Palet Kontraktuese', ln=True)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f'Nxenesi: {contract["student_name"]}', ln=True)
    pdf.cell(0, 6, f'Qyteti: {contract["student_city"] or "N/A"} | Tel: {contract["student_phone"] or "N/A"}', ln=True)
    pdf.ln(3)
    pdf.cell(0, 6, f'Kompania: {contract["company_name"]}', ln=True)
    pdf.cell(0, 6, f'Adresa: {contract["company_address"] or "N/A"} | Tel: {contract["company_phone"] or "N/A"}', ln=True)
    pdf.ln(8)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, '2. Detajet e Apprenticeship-it', ln=True)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f'Profesioni: {contract["profession_name"]} ({contract["qualification_type"]})', ln=True)
    pdf.cell(0, 6, f'Kohezgjatja: {contract["duration_years"]} vjet', ln=True)
    pdf.cell(0, 6, f'Fillimi: {contract["start_date"]} | Fundi: {contract["end_date"]}', ln=True)
    pdf.cell(0, 6, f'Rroga mujore: {contract["salary_monthly"] or "Negociueshem"} MKD', ln=True)
    pdf.cell(0, 6, f'Orari: {contract["company_days_per_week"]} dite kompani + {contract["school_days_per_week"]} dite shkolla', ln=True)
    pdf.ln(8)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, '3. Kushtet', ln=True)
    pdf.set_font('Helvetica', '', 9)
    terms = [
        'Nxenesi obligohet te ndjeke orarin e punes dhe te shkollese.',
        'Kompania obligohet te siguroje kushte te pershtatshme pune dhe mentorim.',
        'Vleresimi behet sipas moduleve te kurrikules se profesionit.',
        'Kontrata mund te terminohet me marreveshje te dy paleve.',
        f'Pas perfundimit te suksesshem, nxenesi merr diplomen {contract["qualification_type"]}.',
    ]
    for t in terms:
        pdf.cell(0, 5, f'  - {t}', ln=True)
    pdf.ln(15)

    pdf.set_font('Helvetica', '', 10)
    pdf.cell(90, 6, 'Nenshkrimi i nxenesit:', border='B')
    pdf.cell(10, 6, '')
    pdf.cell(90, 6, 'Nenshkrimi i kompanise:', border='B', ln=True)
    pdf.ln(15)
    pdf.cell(90, 6, f'{contract["student_name"]}', align='C')
    pdf.cell(10, 6, '')
    pdf.cell(90, 6, f'{contract["company_name"]}', align='C', ln=True)

    pdf.ln(10)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.cell(0, 5, f'Gjeneruar nga BerufsbildungGlobal | Data: {datetime.now().strftime("%d.%m.%Y")}', ln=True, align='C')

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name=f'kontrata_AP-{contract["id"]:04d}.pdf')

# --- Contract Termination ---
@app.route('/api/contracts/<int:contract_id>/terminate', methods=['POST'])
@login_required
def terminate_contract(contract_id):
    db = get_db()
    contract = db.execute("""
        SELECT ac.*, ap.id as position_id, sp.user_id as student_user_id
        FROM apprenticeship_contracts ac
        JOIN apprenticeship_positions ap ON ap.profession_id=ac.profession_id AND ap.company_id=ac.company_id
        JOIN student_profiles sp ON ac.student_id=sp.id
        WHERE ac.id=? AND ac.status='active'
    """, (contract_id,)).fetchone()
    if not contract:
        return jsonify({'error': 'Kontrata nuk u gjet ose nuk është aktive'}), 404

    # Only company or government can terminate
    if session['role'] == 'company':
        company = db.execute("SELECT id FROM company_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
        if not company or company['id'] != contract['company_id']:
            return jsonify({'error': 'Nuk keni akses'}), 403
    elif session['role'] != 'government':
        return jsonify({'error': 'Nuk keni akses'}), 403

    reason = request.json.get('reason', '') if request.json else ''
    db.execute("UPDATE apprenticeship_contracts SET status='terminated' WHERE id=?", (contract_id,))
    db.execute("UPDATE apprenticeship_positions SET positions_filled=MAX(0, positions_filled-1) WHERE id=?",
               (contract['position_id'],))
    db.execute("DELETE FROM schedule_events WHERE contract_id=?", (contract_id,))

    create_notification(db, contract['student_user_id'],
        'Kontrata u terminua',
        f'Kontrata juaj e apprenticeship-it u terminua. {reason}',
        'warning')

    db.commit()
    return jsonify({'success': True, 'message': 'Kontrata u terminua'})

# --- Certificate API ---
@app.route('/api/contracts/<int:contract_id>/certificate', methods=['POST'])
@login_required
def create_certificate(contract_id):
    db = get_db()
    contract = db.execute("""
        SELECT ac.*, p.name_sq as profession_name, p.qualification_type, p.duration_years
        FROM apprenticeship_contracts ac
        JOIN professions p ON ac.profession_id=p.id
        WHERE ac.id=?
    """, (contract_id,)).fetchone()

    if not contract:
        return jsonify({'error': 'Kontrata nuk u gjet'}), 404

    # Check all modules are completed
    progress = db.execute("""
        SELECT status, grade FROM student_progress WHERE contract_id=?
    """, (contract_id,)).fetchall()

    incomplete = [p for p in progress if p['status'] != 'completed']
    if incomplete:
        return jsonify({'error': f'{len(incomplete)} module ende nuk janë përfunduar'}), 400

    # Calculate average grade
    grades = [p['grade'] for p in progress if p['grade'] is not None]
    avg_grade = round(sum(grades) / len(grades), 2) if grades else 0

    # Generate certificate number
    year = datetime.now().year
    count = db.execute("SELECT COUNT(*) FROM certificates").fetchone()[0] + 1
    cert_number = f"MK-{contract['qualification_type']}-{year}-{count:04d}"

    # NQF/EQF levels
    nqf = 4 if contract['qualification_type'] == 'EFZ' else 3
    eqf = nqf

    db.execute("""INSERT INTO certificates
        (contract_id, certificate_type, certificate_number, issue_date, profession_name, final_grade, nqf_level, eqf_level, is_verified)
        VALUES (?,?,?,?,?,?,?,?,1)""",
        (contract_id, contract['qualification_type'], cert_number,
         datetime.now().strftime('%Y-%m-%d'), contract['profession_name'],
         avg_grade, nqf, eqf))

    # Update contract status
    db.execute("UPDATE apprenticeship_contracts SET status='completed' WHERE id=?", (contract_id,))

    db.commit()
    return jsonify({'success': True, 'certificate_number': cert_number})

@app.route('/api/certificates')
@login_required
def get_certificates():
    db = get_db()
    if session['role'] == 'student':
        profile = db.execute("SELECT id FROM student_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
        certs = db.execute("""
            SELECT c.*, ac.start_date, ac.end_date, cp.company_name
            FROM certificates c
            JOIN apprenticeship_contracts ac ON c.contract_id=ac.id
            JOIN company_profiles cp ON ac.company_id=cp.id
            WHERE ac.student_id=?
        """, (profile['id'],)).fetchall()
    else:
        certs = []
    return jsonify([dict(c) for c in certs])

# --- Recommendations API ---
@app.route('/api/recommendations')
@login_required
def get_recommendations():
    if session['role'] != 'student':
        return jsonify([])

    db = get_db()
    profile = db.execute("SELECT * FROM student_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
    if not profile:
        return jsonify([])

    interests = json.loads(profile['interests'] or '[]')
    preferred = json.loads(profile['preferred_professions'] or '[]')

    # Get all active positions with details
    positions = db.execute("""
        SELECT ap.*, cp.company_name, cp.industry, p.name_sq as profession_name,
               p.category, p.duration_years, p.qualification_type, p.code as profession_code
        FROM apprenticeship_positions ap
        JOIN company_profiles cp ON ap.company_id=cp.id
        JOIN professions p ON ap.profession_id=p.id
        WHERE ap.is_active=1 AND (ap.positions_available - COALESCE(ap.positions_filled, 0)) > 0
    """).fetchall()

    # Score positions
    scored = []
    for pos in positions:
        score = 0
        if pos['profession_code'] in preferred:
            score += 10
        for interest in interests:
            if interest.lower() in (pos['profession_name'] or '').lower():
                score += 5
            if interest.lower() in (pos['category'] or '').lower():
                score += 3
            if interest.lower() in (pos['description'] or '').lower():
                score += 1
        scored.append((score, dict(pos)))

    scored.sort(key=lambda x: x[0], reverse=True)
    return jsonify([s[1] for s in scored[:5]])

# --- Admin/Government Stats ---
@app.route('/api/admin/stats')
@login_required
def admin_stats():
    db = get_db()
    stats = {
        'users_by_role': [dict(r) for r in db.execute(
            "SELECT role, COUNT(*) as count FROM users GROUP BY role").fetchall()],
        'applications_by_status': [dict(r) for r in db.execute(
            "SELECT status, COUNT(*) as count FROM applications GROUP BY status").fetchall()],
        'contracts_by_status': [dict(r) for r in db.execute(
            "SELECT status, COUNT(*) as count FROM apprenticeship_contracts GROUP BY status").fetchall()],
        'positions_by_company': [dict(r) for r in db.execute("""
            SELECT cp.company_name, COUNT(*) as count
            FROM apprenticeship_positions ap
            JOIN company_profiles cp ON ap.company_id=cp.id
            GROUP BY cp.company_name ORDER BY count DESC
        """).fetchall()],
        'professions_by_category': [dict(r) for r in db.execute(
            "SELECT category, COUNT(*) as count FROM professions WHERE is_active=1 GROUP BY category ORDER BY count DESC"
        ).fetchall()],
        'total_positions_available': db.execute(
            "SELECT COALESCE(SUM(positions_available - COALESCE(positions_filled,0)),0) FROM apprenticeship_positions WHERE is_active=1"
        ).fetchone()[0],
    }
    return jsonify(stats)

# ============================================================
# FEATURE 1: TRANSLATIONS / i18n
# ============================================================

@app.route('/api/translations')
def get_translations():
    lang = request.args.get('lang', 'sq')
    db = get_db()
    rows = db.execute("SELECT key, value FROM translations WHERE lang=?", (lang,)).fetchall()
    return jsonify({r['key']: r['value'] for r in rows})

@app.route('/api/translations', methods=['POST'])
@login_required
def set_language():
    lang = request.json.get('lang', 'sq')
    session['lang'] = lang
    return jsonify({'success': True, 'lang': lang})

# ============================================================
# FEATURE 2: PDF CERTIFICATE
# ============================================================

class CertificatePDF(FPDF):
    def header(self):
        pass
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, 'BerufsbildungGlobal - Platforma e Arsimit Profesional Dual', align='C')

@app.route('/api/certificates/<int:cert_id>/pdf')
def download_certificate_pdf(cert_id):
    db = get_db()
    cert = db.execute("""
        SELECT c.*, ac.start_date, ac.end_date,
               u.full_name as student_name, u.city as student_city,
               cp.company_name, cp.address as company_address
        FROM certificates c
        JOIN apprenticeship_contracts ac ON c.contract_id=ac.id
        JOIN student_profiles sp ON ac.student_id=sp.id
        JOIN users u ON sp.user_id=u.id
        JOIN company_profiles cp ON ac.company_id=cp.id
        WHERE c.id=?
    """, (cert_id,)).fetchone()

    if not cert:
        return jsonify({'error': 'Certifikata nuk u gjet'}), 404

    pdf = CertificatePDF(orientation='L', format='A4')
    pdf.add_page()

    # Border
    pdf.set_draw_color(26, 86, 219)
    pdf.set_line_width(3)
    pdf.rect(10, 10, 277, 190)
    pdf.set_line_width(1)
    pdf.rect(14, 14, 269, 182)

    # Header
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(26, 86, 219)
    pdf.set_y(25)
    pdf.cell(0, 10, 'BERUFSBILDUNG GLOBAL', align='C', new_x='LMARGIN', new_y='NEXT')

    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(0, 6, 'Sistemi i Arsimit Profesional Dual - Modeli Zviceran', align='C', new_x='LMARGIN', new_y='NEXT')

    # Certificate type
    pdf.ln(10)
    cert_type_name = 'Diplome e Plote Profesionale (EFZ)' if cert['certificate_type'] == 'EFZ' else 'Certifikate Baze Profesionale (EBA)'
    pdf.set_font('Helvetica', 'B', 22)
    pdf.set_text_color(5, 150, 105)
    pdf.cell(0, 12, cert_type_name, align='C', new_x='LMARGIN', new_y='NEXT')

    # Student name
    pdf.ln(8)
    pdf.set_font('Helvetica', 'B', 28)
    pdf.set_text_color(31, 41, 55)
    pdf.cell(0, 14, cert['student_name'], align='C', new_x='LMARGIN', new_y='NEXT')

    # Profession
    pdf.ln(5)
    pdf.set_font('Helvetica', '', 16)
    pdf.set_text_color(31, 41, 55)
    pdf.cell(0, 10, f"Profesioni: {cert['profession_name']}", align='C', new_x='LMARGIN', new_y='NEXT')

    # Details
    pdf.ln(5)
    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(0, 7, f"Kompania trajnuese: {cert['company_name']}", align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 7, f"Periudha: {cert['start_date']} - {cert['end_date']}", align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 7, f"Nota finale: {cert['final_grade']} | NQF Niveli {cert['nqf_level']} | EQF Niveli {cert['eqf_level']}", align='C', new_x='LMARGIN', new_y='NEXT')

    # Certificate number and QR placeholder
    pdf.ln(8)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(26, 86, 219)
    pdf.cell(0, 6, f"Nr. Certifikates: {cert['certificate_number']}", align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 8)
    pdf.cell(0, 5, f"Verifikim: https://berufsbildung.global/verify/{cert['certificate_number']}", align='C', new_x='LMARGIN', new_y='NEXT')

    # Date and signature line
    pdf.set_y(170)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(90, 5, f"Data: {cert['issue_date']}", align='C')
    pdf.cell(90, 5, '', align='C')
    pdf.cell(90, 5, 'Nenshkrimi dixhital i verifikuar', align='C')

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf',
                     download_name=f"Certifikate_{cert['certificate_number']}.pdf")

# ============================================================
# FEATURE 3: MESSAGING / CHAT
# ============================================================

@app.route('/api/messages')
@login_required
def get_messages():
    db = get_db()
    uid = session['user_id']
    # Get conversations (grouped by other person)
    messages = db.execute("""
        SELECT m.*,
               CASE WHEN m.sender_id=? THEN u2.full_name ELSE u1.full_name END as other_name,
               CASE WHEN m.sender_id=? THEN m.receiver_id ELSE m.sender_id END as other_id
        FROM messages m
        JOIN users u1 ON m.sender_id=u1.id
        JOIN users u2 ON m.receiver_id=u2.id
        WHERE m.sender_id=? OR m.receiver_id=?
        ORDER BY m.created_at DESC
    """, (uid, uid, uid, uid)).fetchall()

    unread = db.execute("SELECT COUNT(*) FROM messages WHERE receiver_id=? AND is_read=0", (uid,)).fetchone()[0]
    return jsonify({'messages': [dict(m) for m in messages], 'unread_count': unread})

@app.route('/api/messages/conversation/<int:other_id>')
@login_required
def get_conversation(other_id):
    db = get_db()
    uid = session['user_id']
    msgs = db.execute("""
        SELECT m.*, u.full_name as sender_name
        FROM messages m JOIN users u ON m.sender_id=u.id
        WHERE (m.sender_id=? AND m.receiver_id=?) OR (m.sender_id=? AND m.receiver_id=?)
        ORDER BY m.created_at ASC
    """, (uid, other_id, other_id, uid)).fetchall()

    # Mark as read
    db.execute("UPDATE messages SET is_read=1 WHERE sender_id=? AND receiver_id=?", (other_id, uid))
    db.commit()

    other = db.execute("SELECT full_name, role FROM users WHERE id=?", (other_id,)).fetchone()
    return jsonify({'messages': [dict(m) for m in msgs], 'other_user': dict(other) if other else {}})

@app.route('/api/messages', methods=['POST'])
@login_required
def send_message():
    data = request.json
    db = get_db()
    db.execute("INSERT INTO messages (sender_id, receiver_id, subject, body, related_application_id) VALUES (?,?,?,?,?)",
        (session['user_id'], data['receiver_id'], data.get('subject', ''),
         data['body'], data.get('application_id')))

    create_notification(db, data['receiver_id'], 'Mesazh i ri',
        f'Keni nje mesazh te ri nga {session["full_name"]}', 'info')
    db.commit()
    return jsonify({'success': True})

# ============================================================
# FEATURE 4: SCHEDULE / CALENDAR
# ============================================================

@app.route('/api/schedule')
@login_required
def get_schedule():
    db = get_db()
    events = db.execute("SELECT * FROM schedule_events WHERE user_id=? ORDER BY day_of_week, start_time",
                        (session['user_id'],)).fetchall()
    return jsonify([dict(e) for e in events])

@app.route('/api/schedule', methods=['POST'])
@login_required
def create_schedule_event():
    data = request.json
    db = get_db()
    db.execute("""INSERT INTO schedule_events
        (user_id, contract_id, title, description, event_type, day_of_week, start_time, end_time, location, recurring, specific_date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (session['user_id'], data.get('contract_id'), data['title'], data.get('description', ''),
         data.get('event_type', 'other'), data.get('day_of_week'), data.get('start_time'),
         data.get('end_time'), data.get('location', ''), data.get('recurring', 1), data.get('specific_date')))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/schedule/auto-generate/<int:contract_id>', methods=['POST'])
@login_required
def auto_generate_schedule(contract_id):
    """Auto-generate weekly schedule based on profession's company/school days"""
    db = get_db()
    contract = db.execute("""
        SELECT ac.*, p.company_days_per_week, p.school_days_per_week, p.name_sq,
               cp.company_name, cp.address as company_addr
        FROM apprenticeship_contracts ac
        JOIN professions p ON ac.profession_id=p.id
        JOIN company_profiles cp ON ac.company_id=cp.id
        WHERE ac.id=?
    """, (contract_id,)).fetchone()

    if not contract:
        return jsonify({'error': 'Kontrata nuk u gjet'}), 404

    # Delete old auto-generated
    db.execute("DELETE FROM schedule_events WHERE contract_id=? AND user_id=?", (contract_id, session['user_id']))

    days = ['E Hene', 'E Marte', 'E Merkure', 'E Enjte', 'E Premte']
    for i in range(contract['company_days_per_week']):
        db.execute("""INSERT INTO schedule_events (user_id, contract_id, title, event_type, day_of_week, start_time, end_time, location)
            VALUES (?,?,?,?,?,?,?,?)""",
            (session['user_id'], contract_id, f"{contract['company_name']} - Praktike",
             'company', i, '08:00', '16:30', contract['company_addr'] or ''))

    for i in range(contract['school_days_per_week']):
        day = contract['company_days_per_week'] + i
        db.execute("""INSERT INTO schedule_events (user_id, contract_id, title, event_type, day_of_week, start_time, end_time, location)
            VALUES (?,?,?,?,?,?,?,?)""",
            (session['user_id'], contract_id, f"Shkolla Profesionale - {contract['name_sq']}",
             'school', day, '08:00', '15:00', 'Shkolla e Mesme Profesionale'))

    db.commit()
    return jsonify({'success': True, 'message': 'Orari javor u gjenerua!'})

# ============================================================
# FEATURE 5: REVIEWS / RATINGS
# ============================================================

@app.route('/api/reviews/<int:company_user_id>')
def get_company_reviews(company_user_id):
    db = get_db()
    company = db.execute("SELECT id FROM company_profiles WHERE user_id=?", (company_user_id,)).fetchone()
    if not company:
        return jsonify({'error': 'Kompania nuk u gjet'}), 404

    reviews = db.execute("""
        SELECT r.*, u.full_name as reviewer_name
        FROM reviews r JOIN users u ON r.reviewer_id=u.id
        WHERE r.reviewed_id=? AND r.review_type='student_to_company'
        ORDER BY r.created_at DESC
    """, (company_user_id,)).fetchall()

    avg = db.execute("SELECT AVG(rating) FROM reviews WHERE reviewed_id=? AND review_type='student_to_company'",
                     (company_user_id,)).fetchone()[0]

    return jsonify({'reviews': [dict(r) for r in reviews], 'average_rating': round(avg, 1) if avg else None, 'count': len(reviews)})

@app.route('/api/reviews', methods=['POST'])
@login_required
def create_review():
    data = request.json
    db = get_db()

    try:
        db.execute("""INSERT INTO reviews (reviewer_id, reviewed_id, review_type, contract_id, rating, review_text)
            VALUES (?,?,?,?,?,?)""",
            (session['user_id'], data['reviewed_id'], data['review_type'],
             data.get('contract_id'), data['rating'], data.get('review_text', '')))
        db.commit()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Tashme keni lene vleresim per kete kontrate'}), 400

# ============================================================
# FEATURE 6: GOVERNMENT DASHBOARD (enhanced stats)
# ============================================================

@app.route('/api/admin/dashboard')
@login_required
def admin_dashboard():
    db = get_db()
    data = {
        'total_users': db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'total_students': db.execute("SELECT COUNT(*) FROM student_profiles").fetchone()[0],
        'total_companies': db.execute("SELECT COUNT(*) FROM company_profiles").fetchone()[0],
        'total_schools': db.execute("SELECT COUNT(*) FROM school_profiles").fetchone()[0],
        'total_professions': db.execute("SELECT COUNT(*) FROM professions WHERE is_active=1").fetchone()[0],
        'total_positions': db.execute("SELECT COUNT(*) FROM apprenticeship_positions WHERE is_active=1").fetchone()[0],
        'total_applications': db.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
        'total_contracts': db.execute("SELECT COUNT(*) FROM apprenticeship_contracts").fetchone()[0],
        'active_contracts': db.execute("SELECT COUNT(*) FROM apprenticeship_contracts WHERE status='active'").fetchone()[0],
        'total_certificates': db.execute("SELECT COUNT(*) FROM certificates").fetchone()[0],
        'applications_by_status': [dict(r) for r in db.execute(
            "SELECT status, COUNT(*) as count FROM applications GROUP BY status").fetchall()],
        'positions_by_city': [dict(r) for r in db.execute(
            "SELECT city, COUNT(*) as count FROM apprenticeship_positions WHERE is_active=1 GROUP BY city ORDER BY count DESC").fetchall()],
        'positions_by_category': [dict(r) for r in db.execute("""
            SELECT p.category, COUNT(*) as count FROM apprenticeship_positions ap
            JOIN professions p ON ap.profession_id=p.id WHERE ap.is_active=1
            GROUP BY p.category ORDER BY count DESC""").fetchall()],
        'companies_ranked': [dict(r) for r in db.execute("""
            SELECT cp.id, cp.company_name, cp.industry, cp.is_verified, COUNT(ap.id) as positions,
                   COALESCE(SUM(ap.positions_available),0) as total_slots
            FROM company_profiles cp
            LEFT JOIN apprenticeship_positions ap ON cp.id=ap.company_id
            GROUP BY cp.id ORDER BY positions DESC""").fetchall()],
        'monthly_registrations': [dict(r) for r in db.execute("""
            SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count
            FROM users GROUP BY month ORDER BY month""").fetchall()],
    }
    return jsonify(data)

# ============================================================
# FEATURE 7: EXAMS / TESTS
# ============================================================

@app.route('/api/exams/module/<int:module_id>')
def get_module_exams(module_id):
    db = get_db()
    exams = db.execute("SELECT * FROM exams WHERE module_id=? AND is_active=1", (module_id,)).fetchall()
    return jsonify([dict(e) for e in exams])

@app.route('/api/exams/<int:exam_id>')
@login_required
def get_exam(exam_id):
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
    if not exam:
        return jsonify({'error': 'Provimi nuk u gjet'}), 404

    questions = db.execute("SELECT id, question_text, question_type, options, points, order_index FROM exam_questions WHERE exam_id=? ORDER BY order_index",
                           (exam_id,)).fetchall()

    return jsonify({'exam': dict(exam), 'questions': [dict(q) for q in questions]})

@app.route('/api/exams/<int:exam_id>/submit', methods=['POST'])
@login_required
def submit_exam(exam_id):
    data = request.json  # { answers: { question_id: answer_value } }
    db = get_db()

    student = db.execute("SELECT id FROM student_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
    if not student:
        return jsonify({'error': 'Jo nxenes'}), 403

    questions = db.execute("SELECT * FROM exam_questions WHERE exam_id=?", (exam_id,)).fetchall()
    exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()

    total_points = 0
    earned_points = 0
    answers = data.get('answers', {})

    for q in questions:
        total_points += q['points']
        if q['question_type'] == 'multiple_choice':
            if str(answers.get(str(q['id']), '')) == str(q['correct_answer']):
                earned_points += q['points']
        elif q['question_type'] == 'essay':
            # Essay: give partial credit if non-empty
            if answers.get(str(q['id']), '').strip():
                earned_points += q['points'] * 0.5  # 50% for attempting

    score = round((earned_points / total_points * 6) if total_points > 0 else 0, 2)  # Scale to 1-6
    passed = 1 if score >= exam['pass_grade'] else 0

    db.execute("""INSERT INTO exam_attempts (exam_id, student_id, answers, score, passed, completed_at)
        VALUES (?,?,?,?,?,?)""",
        (exam_id, student['id'], json.dumps(answers), score, passed, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    db.commit()

    return jsonify({'success': True, 'score': score, 'passed': bool(passed),
                    'total_points': total_points, 'earned_points': earned_points})

@app.route('/api/exams/<int:exam_id>/results')
@login_required
def get_exam_results(exam_id):
    db = get_db()
    student = db.execute("SELECT id FROM student_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
    attempts = db.execute("SELECT * FROM exam_attempts WHERE exam_id=? AND student_id=? ORDER BY completed_at DESC",
                          (exam_id, student['id'])).fetchall()
    return jsonify([dict(a) for a in attempts])

# ============================================================
# FEATURE 8: FILE UPLOAD
# ============================================================

@app.route('/api/uploads', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Asnje skedar nuk u zgjodh'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Emri i skedarit eshte bosh'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'Lloji i skedarit nuk lejohet. Lejohen: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)

    db = get_db()
    category = request.form.get('category', 'other')
    db.execute("INSERT INTO uploads (user_id, file_name, original_name, file_type, file_size, category) VALUES (?,?,?,?,?,?)",
        (session['user_id'], filename, file.filename, ext, os.path.getsize(filepath), category))
    db.commit()

    return jsonify({'success': True, 'file_name': filename, 'original_name': file.filename})

@app.route('/api/uploads')
@login_required
def get_uploads():
    db = get_db()
    files = db.execute("SELECT * FROM uploads WHERE user_id=? ORDER BY created_at DESC", (session['user_id'],)).fetchall()
    return jsonify([dict(f) for f in files])

@app.route('/api/uploads/<filename>')
def serve_upload(filename):
    filepath = os.path.join(UPLOAD_DIR, secure_filename(filename))
    if os.path.exists(filepath):
        return send_file(filepath)
    return jsonify({'error': 'Skedari nuk u gjet'}), 404

@app.route('/api/uploads/<int:file_id>', methods=['DELETE'])
@login_required
def delete_upload(file_id):
    db = get_db()
    f = db.execute("SELECT * FROM uploads WHERE id=? AND user_id=?", (file_id, session['user_id'])).fetchone()
    if f:
        filepath = os.path.join(UPLOAD_DIR, f['file_name'])
        if os.path.exists(filepath):
            os.remove(filepath)
        db.execute("DELETE FROM uploads WHERE id=?", (file_id,))
        db.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Nuk u gjet'}), 404

# ============================================================
# FEATURE 9: MENTORING
# ============================================================

@app.route('/api/mentorships/<int:contract_id>')
@login_required
def get_mentorship(contract_id):
    db = get_db()
    mentorship = db.execute("""
        SELECT m.*, u.full_name as mentor_full_name
        FROM mentorships m JOIN users u ON m.mentor_user_id=u.id
        WHERE m.contract_id=?
    """, (contract_id,)).fetchone()

    if not mentorship:
        return jsonify({'mentorship': None, 'feedback': []})

    feedback = db.execute("SELECT * FROM mentor_feedback WHERE mentorship_id=? ORDER BY week_number DESC",
                          (mentorship['id'],)).fetchall()

    return jsonify({'mentorship': dict(mentorship), 'feedback': [dict(f) for f in feedback]})

@app.route('/api/mentorships', methods=['POST'])
@login_required
def assign_mentor():
    data = request.json
    db = get_db()
    db.execute("INSERT INTO mentorships (contract_id, mentor_user_id, mentor_name, mentor_role) VALUES (?,?,?,?)",
        (data['contract_id'], session['user_id'], data.get('mentor_name', session['full_name']),
         data.get('mentor_role', 'Mentor')))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/mentorships/<int:mentorship_id>/feedback', methods=['POST'])
@login_required
def add_mentor_feedback(mentorship_id):
    data = request.json
    db = get_db()
    db.execute("INSERT INTO mentor_feedback (mentorship_id, week_number, feedback_text, areas_of_improvement, rating) VALUES (?,?,?,?,?)",
        (mentorship_id, data.get('week_number'), data['feedback_text'],
         data.get('areas_of_improvement', ''), data.get('rating')))
    db.commit()
    return jsonify({'success': True})

# ============================================================
# FEATURE 10: PUBLIC API
# ============================================================

@app.route('/api/v1/professions')
def api_v1_professions():
    """Public API: List all professions"""
    db = get_db()
    profs = db.execute("SELECT code, name_sq, name_en, name_mk, category, duration_years, qualification_type, description FROM professions WHERE is_active=1").fetchall()
    return jsonify({'data': [dict(p) for p in profs], 'count': len(profs), 'api_version': '1.0'})

@app.route('/api/v1/positions')
def api_v1_positions():
    """Public API: List open positions"""
    db = get_db()
    positions = db.execute("""
        SELECT ap.id, ap.title, ap.description, ap.city, ap.start_date, ap.salary_monthly, ap.positions_available,
               cp.company_name, p.name_sq as profession, p.code as profession_code, p.category, p.qualification_type
        FROM apprenticeship_positions ap
        JOIN company_profiles cp ON ap.company_id=cp.id
        JOIN professions p ON ap.profession_id=p.id
        WHERE ap.is_active=1
    """).fetchall()
    return jsonify({'data': [dict(p) for p in positions], 'count': len(positions), 'api_version': '1.0'})

@app.route('/api/v1/stats')
def api_v1_stats():
    """Public API: Platform statistics"""
    db = get_db()
    return jsonify({
        'data': {
            'professions': db.execute("SELECT COUNT(*) FROM professions WHERE is_active=1").fetchone()[0],
            'positions': db.execute("SELECT COUNT(*) FROM apprenticeship_positions WHERE is_active=1").fetchone()[0],
            'companies': db.execute("SELECT COUNT(*) FROM company_profiles").fetchone()[0],
            'students': db.execute("SELECT COUNT(*) FROM student_profiles").fetchone()[0],
            'active_contracts': db.execute("SELECT COUNT(*) FROM apprenticeship_contracts WHERE status='active'").fetchone()[0],
            'certificates_issued': db.execute("SELECT COUNT(*) FROM certificates").fetchone()[0],
        },
        'api_version': '1.0'
    })

@app.route('/api/v1/docs')
def api_v1_docs():
    """Public API documentation"""
    return jsonify({
        'name': 'BerufsbildungGlobal Public API',
        'version': '1.0',
        'base_url': '/api/v1',
        'endpoints': [
            {'method': 'GET', 'path': '/api/v1/professions', 'description': 'List all professions'},
            {'method': 'GET', 'path': '/api/v1/positions', 'description': 'List open positions'},
            {'method': 'GET', 'path': '/api/v1/stats', 'description': 'Platform statistics'},
            {'method': 'GET', 'path': '/api/v1/docs', 'description': 'This documentation'},
        ]
    })

# ============================================================
# RUN
# ============================================================

# Initialize DB on import (needed for gunicorn in production)
init_db()

if __name__ == '__main__':
    print("\n" + "="*60)
    print("BerufsbildungGlobal - Swiss VET System Platform")
    print("="*60)
    print("Konfiguruar per: Maqedoni e Veriut")
    port = int(os.environ.get('PORT', 5050))
    print(f"Hap ne shfletues: http://localhost:{port}")
    print("="*60 + "\n")
    app.run(debug=os.environ.get('FLASK_ENV') != 'production', host='0.0.0.0', port=port)
