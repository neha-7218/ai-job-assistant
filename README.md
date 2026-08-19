# AI Job Assistant

An AI-powered web application that helps students and junior developers evaluate their resumes against a target job role and prepare for interviews.

Upload a PDF or DOCX resume, select a target role, and get an **ATS score, matched skills, skill gaps, portfolio project ideas, and mock interview questions**.

### 🚀 Live Demo

[Try AI Job Assistant](https://ai-job-assistant-akpt.onrender.com/)

## Features

* Upload resumes in PDF or DOCX format
* Choose from 20 job roles
* Generate an ATS score out of 100
* Identify skills found in the resume
* Identify skill gaps for the selected role
* Generate 3 portfolio project ideas
* Generate 10 mock interview questions with sample answers
* Generate a PDF analysis report
* Store previous analyses using SQLite

## How It Works

1. Upload your resume.
2. Select the role you are preparing for.
3. The application extracts text from the resume.
4. Gemini analyzes the resume against the selected role.
5. The results are displayed in the web application.
6. A PDF report can be generated from the analysis.

## Tech Stack

**Backend**

* Python
* FastAPI

**AI**

* Gemini API

**Resume Parsing**

* pdfplumber
* python-docx

**Database**

* SQLite

**Frontend**

* HTML
* CSS
* JavaScript

**Deployment & Tools**

* Docker
* Git
* GitHub
* Render

## Screenshots

### Home

![Home](screenshots/ai-job-assistant-home.png)

### Resume Analysis

![ATS Score & Resume Analysis](screenshots/analysis-1.png)

### Analysis Results

![Analysis Results](screenshots/analysis-2.png)

### Mock Interview Preparation

![Mock Interview Prep](screenshots/analysis-3.png)

### Available Roles

![Available Roles](screenshots/available-roles.png)

## Run Locally

Clone the repository:

```bash
git clone https://github.com/neha-7218/ai-job-assistant-clean.git
cd ai-job-assistant-clean
```

Create and activate a virtual environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file and add your Gemini API configuration:

```env
GEMINI_API_KEY=your-key
LLM_PROVIDER=gemini
MODEL=gemini-3.5-flash
```

Start the application:

```bash
python -m uvicorn app.main:app --reload
```

Open:

```text
http://localhost:8000
```

## API Endpoints

| Method | Endpoint       | Purpose                         |
| ------ | -------------- | ------------------------------- |
| GET    | `/`            | Web application                 |
| GET    | `/api/health`  | Check application and AI status |
| GET    | `/api/roles`   | Get available job roles         |
| GET    | `/api/recent`  | Get recent analyses             |
| POST   | `/api/analyze` | Upload and analyze a resume     |
| POST   | `/api/report`  | Generate the PDF report         |

## Deployment

The application is packaged with Docker and deployed as a web service on Render.

**Live application:**
https://ai-job-assistant-akpt.onrender.com/

## Project Structure

```text
ai-job-assistant-clean/
├── app/
│   ├── main.py
│   ├── analyzer.py
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── resume_parser.py
│   ├── llm/
│   │   ├── client.py
│   │   └── prompts.py
│   └── static/
├── data/
├── scripts/
├── tests/
├── Dockerfile
├── requirements.txt
└── run.sh
```

## What I Learned

Building this project gave me hands-on experience with:

* FastAPI backend development
* Resume file uploads and validation
* PDF and DOCX text extraction
* LLM API integration
* Structured AI responses
* SQLite database operations
* PDF report generation
* Docker-based deployment
* Debugging and deploying a production web application

## Notes

* Resume uploads are limited to 5 MB.
* A Gemini API key is required for AI analysis.
* Avoid uploading resumes or documents containing information you do not want sent to an external AI service.
