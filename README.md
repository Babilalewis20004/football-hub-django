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

## 👨‍💻 Author

**Your Name**

Computer Science Graduate

Python | Django | PostgreSQL | Full-Stack Developer

GitHub:

LinkedIn:

---

## 📄 License

This project is licensed under the MIT License.
