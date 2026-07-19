# ⚽ Football Hub

A modern football blogging platform built with **Django**, **PostgreSQL**, **Bootstrap 5**, and **HTMX**.

![Python](https://img.shields.io/badge/Python-3.13-blue)
![Django](https://img.shields.io/badge/Django-6.0-success)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-blue)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5-purple)
![HTML](https://img.shields.io/badge/HTML-5-orange)
![CSS](https://img.shields.io/badge/CSS-3-blue)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6-yellow)
![HTMX](https://img.shields.io/badge/HTMX-1.9-blueviolet)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📖 Overview

Football Hub is a full-stack web application that enables football enthusiasts to read, search, and interact with football news and articles.

The application provides secure authentication, article management, commenting, bookmarking, search functionality, and an administrative dashboard.

---

## ✨ Features

- User Registration & Authentication
- Custom User Model
- Football News Articles
- Categories
- Rich Text Editor (CKEditor)
- Article Search
- Comments
- Likes
- Bookmarks
- User Dashboard
- Admin Dashboard
- Responsive Bootstrap UI
- Dark Mode
- PostgreSQL Database
- Secure Authentication
- Logging & Error Handling

---

## 🛠️ Tech Stack

### Backend

- Python
- Django
- PostgreSQL

### Frontend

- HTML5
- CSS3
- Bootstrap 5
- JavaScript
- HTMX

### Libraries

- django-crispy-forms
- django-taggit
- django-ckeditor
- WhiteNoise
- python-decouple

---

## 📂 Project Structure

```text
football-hub-django/

blog/
users/
config/
templates/
static/
media/
docs/
manage.py
```

---

## 🚀 Installation

Clone the repository

```bash
git clone https://github.com/Babilalewis20004/football-hub-django.git
```

Move into the project

```bash
cd football-hub-django
```

Create virtual environment

```bash
python -m venv venv
```

Activate

Windows

```bash
venv\Scripts\activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Create `.env`

```env
SECRET_KEY=your-secret-key
DEBUG=True

DB_NAME=football_blog
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

ALLOWED_HOSTS=127.0.0.1,localhost
```

Run migrations

```bash
python manage.py migrate
```

Create superuser

```bash
python manage.py createsuperuser
```

Run server

```bash
python manage.py runserver
```

---

## 🧪 Testing

Run the test suite

```bash
python manage.py test
```

---

## 📸 Screenshots

Add screenshots after completing the UI redesign.

Example:

```
docs/screenshots/homepage.png
docs/screenshots/dashboard.png
docs/screenshots/article.png
```

---

## 📚 Documentation

The repository includes:

- System Design Document (SDD)
- UML Diagrams
- Wireframes
- Final Project Report

Located in:

```
docs/
```

---

## 🔒 Security

- Environment variables stored in `.env`
- Custom User Model
- CSRF Protection
- XSS Protection
- HTTPOnly Cookies
- Secure Password Validation

---

/* ========================================================================
   FOOTBALL HUB — MASTER STYLESHEET
   ------------------------------------------------------------------------
   This project currently uses a SINGLE stylesheet (style.css).

   OPTIONAL MODULAR ARCHITECTURE (recommended for scaling):
   --------------------------------------------------------
   /css/core/
       variables.css      → global color palette, shadows, gradients
       global.css         → body, typography, resets
       layout.css         → containers, spacing, responsive grid
       utilities.css      → reusable helpers (glass, glow, spacing)

   /css/components/
       navbar.css         → navigation bar styles
       sidebar.css        → sidebar glass cards
       slider.css         → homepage slider
       hero.css           → homepage hero grid
       match-block.css    → match fixtures block
       bullet-links.css   → bullet link list
       article-card.css   → article cards

   /css/pages/
       home.css           → homepage layout
       post.css           → post detail page
       category.css       → category listing page
       dashboard.css      → user dashboard
       login.css          → login page
       register.css       → register page

   HOW TO USE THIS FILE:
   ---------------------
   - All styles are currently combined here.
   - Each section below is labeled with its modular category.
   - If you ever want to split into modules, simply copy each section
     into the corresponding file listed above.

   ======================================================================== */


   
### Why modular CSS?
- Easier to maintain  
- Faster debugging  
- Cleaner separation of concerns  
- Scales better for large projects  
- Matches professional design‑system architecture  

---

## 🧩 How `style.css` Is Structured Today

To prepare for future modularisation, `style.css` is organised into clearly labelled sections:

### **CORE**
- Global resets  
- Body styles  
- Typography  
- Layout helpers  
- Animations  

### **COMPONENTS**
- Navbar  
- Sidebar  
- Hero grid  
- Slider  
- Match block  
- Bullet links  
- Article cards  

### **PAGES**
- Home page  
- Post detail page  
- Category listing page  
- Dashboard  
- Login  
- Register  

Each section includes a comment header showing **where it would live** if modularised.

Example:

```css
/* ========================================================================
   COMPONENT → NAVBAR
   (Would live in: css/components/navbar.css)
========================================================================= */



## 👨‍💻 Author

**Your Name**

Computer Science Graduate

Python | Django | PostgreSQL | Full-Stack Developer

GitHub:

LinkedIn:

---

## 📄 License

This project is licensed under the MIT License.
