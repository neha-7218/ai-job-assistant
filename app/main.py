"""FastAPI app — upload resume, analyze with AI, return job prep insights."""

import logging
import time
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fpdf import FPDF

from app.analyzer import analyze_resume_text
from app.config import (
    ALLOWED_RESUME_EXTENSIONS,
    ROLE_GROUPS,
    STATIC_DIR,
    TARGET_ROLES,
    get_settings,
)
from app.db import get_latest, init_db, save_analysis
from app.models import (
    AnalyzeResponse,
    HealthResponse,
    RoleGroup,
    RolesResponse,
)
from app.resume_parser import extract_text, file_extension


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


app = FastAPI(
    title="AI Job Assistant",
    description="Upload resume → ATS score, skill gaps, projects, mock interview prep",
    version="1.0.0",
)


if STATIC_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )


_rate_limit: dict[str, float] = {}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")

    if forwarded:
        return forwarded.split(",")[0].strip()

    if request.client:
        return request.client.host

    return "unknown"


def _check_rate_limit(request: Request):
    settings = get_settings()

    ip = _client_ip(request)
    now = time.time()

    last = _rate_limit.get(ip, 0)

    if now - last < settings.rate_limit_seconds:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many requests. Please wait "
                f"{settings.rate_limit_seconds} seconds and try again."
            ),
        )

    _rate_limit[ip] = now


@app.on_event("startup")
def startup():
    init_db()

    settings = get_settings()

    log.info(
        "AI Job Assistant started (LLM: %s)",
        settings.llm_provider,
    )


@app.get("/")
def index():
    index_path = STATIC_DIR / "index.html"

    if not index_path.exists():
        raise HTTPException(
            status_code=404,
            detail="UI not found",
        )

    return FileResponse(index_path)


@app.get("/api/health", response_model=HealthResponse)
def health():
    settings = get_settings()

    has_key = bool(
        settings.gemini_api_key
        if settings.llm_provider == "gemini"
        else settings.openai_api_key
    )

    return HealthResponse(
        status="ok" if has_key else "degraded",
        llm=(
            settings.llm_provider
            if has_key
            else f"{settings.llm_provider} (missing API key)"
        ),
    )


@app.get("/api/roles", response_model=RolesResponse)
def roles():
    return RolesResponse(
        roles=TARGET_ROLES,
        groups=[
            RoleGroup(
                label=group["label"],
                roles=group["roles"],
            )
            for group in ROLE_GROUPS
        ],
    )


@app.get("/api/recent")
def recent():
    return {
        "recent": get_latest()
    }


# ============================================================
# PDF REPORT
# ============================================================

@app.post("/api/report")
async def generate_report(data: AnalyzeResponse):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --------------------------------------------------------
    # PDF-safe text
    # --------------------------------------------------------

    def safe_text(value):
        text = str(value if value is not None else "")

        replacements = {
            "–": "-",
            "—": "-",
            "’": "'",
            "‘": "'",
            "“": '"',
            "”": '"',
            "•": "-",
            "→": "->",
            "←": "<-",
            "₹": "Rs.",
            "©": "(c)",
            "™": "(TM)",
            "…": "...",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        text = (
            text
            .encode("latin-1", errors="replace")
            .decode("latin-1")
        )

        # Break extremely long strings.
        result = []

        for word in text.split(" "):
            if len(word) > 40:
                chunks = [
                    word[i:i + 35]
                    for i in range(0, len(word), 35)
                ]
                result.append(" ".join(chunks))
            else:
                result.append(word)

        return " ".join(result)

    # --------------------------------------------------------
    # Safe multi-line writer
    # --------------------------------------------------------

    def write_text(text, height=6):
        text = safe_text(text)

        # IMPORTANT:
        # Always reset the cursor to the left margin.
        pdf.set_x(pdf.l_margin)

        # Explicitly calculate available page width.
        width = (
            pdf.w
            - pdf.l_margin
            - pdf.r_margin
        )

        # Never allow an invalid width.
        if width <= 0:
            width = 170

        pdf.multi_cell(
            width,
            height,
            text,
        )

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    pdf.set_font(
        "Helvetica",
        "B",
        18,
    )

    pdf.set_x(pdf.l_margin)

    pdf.cell(
        0,
        10,
        "AI Job Assistant - Resume Analysis",
        ln=True,
    )

    pdf.ln(5)

    # --------------------------------------------------------
    # BASIC INFO
    # --------------------------------------------------------

    pdf.set_font(
        "Helvetica",
        size=11,
    )

    write_text(
        f"Candidate: {data.candidate_name}",
        7,
    )

    write_text(
        f"Target Role: {data.target_role}",
        7,
    )

    write_text(
        f"ATS Score: {data.ats_score}/100",
        7,
    )

    pdf.ln(5)

    # --------------------------------------------------------
    # SECTION HELPER
    # --------------------------------------------------------

    def section(title, content):
        pdf.set_font(
            "Helvetica",
            "B",
            13,
        )

        pdf.set_x(pdf.l_margin)

        pdf.cell(
            0,
            8,
            safe_text(title),
            ln=True,
        )

        pdf.set_font(
            "Helvetica",
            size=10,
        )

        if isinstance(content, list):
            for item in content:
                write_text(
                    f"- {item}",
                    6,
                )
        else:
            write_text(
                content,
                6,
            )

        pdf.ln(3)

    # --------------------------------------------------------
    # ANALYSIS
    # --------------------------------------------------------

    section(
        "ATS Feedback",
        data.ats_feedback,
    )

    section(
        "Skills Found",
        data.skills_found,
    )

    section(
        "Skill Gaps",
        data.skill_gaps,
    )

    section(
        "Strengths",
        data.strengths,
    )

    # --------------------------------------------------------
    # PROJECT IDEAS
    # --------------------------------------------------------

    pdf.ln(3)

    pdf.set_font(
        "Helvetica",
        "B",
        13,
    )

    pdf.set_x(pdf.l_margin)

    pdf.cell(
        0,
        8,
        "Portfolio Project Ideas",
        ln=True,
    )

    for project in data.project_suggestions:

        pdf.ln(2)

        pdf.set_font(
            "Helvetica",
            "B",
            11,
        )

        write_text(
            project.title,
            6,
        )

        pdf.set_font(
            "Helvetica",
            size=10,
        )

        write_text(
            f"Why: {project.why}",
            6,
        )

        stack = ", ".join(
            str(item)
            for item in project.stack
        )

        write_text(
            f"Stack: {stack}",
            6,
        )

        write_text(
            f"Difficulty: {project.difficulty}",
            6,
        )

    # --------------------------------------------------------
    # MOCK INTERVIEW
    # --------------------------------------------------------

    pdf.add_page()

    pdf.set_font(
        "Helvetica",
        "B",
        13,
    )

    pdf.set_x(pdf.l_margin)

    pdf.cell(
        0,
        8,
        "Mock Interview Questions",
        ln=True,
    )

    for index, question in enumerate(
        data.mock_interview,
        1,
    ):

        pdf.ln(3)

        pdf.set_font(
            "Helvetica",
            "B",
            11,
        )

        write_text(
            f"{index}. {question.question}",
            6,
        )

        pdf.set_font(
            "Helvetica",
            size=10,
        )

        write_text(
            f"Sample Answer: {question.sample_answer}",
            6,
        )

        write_text(
            f"Explanation: {question.explanation}",
            6,
        )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    output_path = (
        Path(tempfile.gettempdir())
        / "AI-Resume-Analysis.pdf"
    )

    pdf.output(
        str(output_path)
    )

    return FileResponse(
        path=str(output_path),
        filename="AI-Resume-Analysis.pdf",
        media_type="application/pdf",
    )


# ============================================================
# RESUME ANALYSIS
# ============================================================

@app.post(
    "/api/analyze",
    response_model=AnalyzeResponse,
)
async def analyze(
    request: Request,
    file: UploadFile = File(...),
    target_role: str = Form(...),
):
    _check_rate_limit(request)

    settings = get_settings()

    # --------------------------------------------------------
    # Validate role
    # --------------------------------------------------------

    if target_role not in TARGET_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Invalid target role.",
        )

    # --------------------------------------------------------
    # Validate file extension
    # --------------------------------------------------------

    filename = file.filename or ""

    ext = file_extension(filename)

    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF or DOCX file only.",
        )

    # --------------------------------------------------------
    # Read uploaded file
    # --------------------------------------------------------

    file_bytes = await file.read()

    max_bytes = (
        settings.max_upload_mb
        * 1024
        * 1024
    )

    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File is too large. Maximum size is "
                f"{settings.max_upload_mb} MB."
            ),
        )

    # --------------------------------------------------------
    # Extract resume text
    # --------------------------------------------------------

    try:
        resume_text = extract_text(
            file_bytes,
            filename=filename,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    # --------------------------------------------------------
    # AI ANALYSIS
    # --------------------------------------------------------

    try:
        result = analyze_resume_text(
            resume_text,
            target_role,
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error

    except Exception as error:
        log.exception(
            "Analysis failed"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "AI analysis failed. "
                "Please try again in a moment."
            ),
        ) from error

    # --------------------------------------------------------
    # Save analysis
    # --------------------------------------------------------

    response_dict = result.model_dump(
        mode="json"
    )

    save_analysis(
        response_dict
    )

    return result