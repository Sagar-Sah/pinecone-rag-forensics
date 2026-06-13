from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth import create_token, get_current_user, hash_password, verify_password
from app.config import settings
from app.database import (
    add_eval_case,
    categories,
    chunk_count,
    create_user,
    document_count,
    get_user_by_email,
    get_user_by_username,
    init_db,
    list_documents,
    list_eval_cases,
    namespaces,
)
from app.evals import run_eval_case
from app.pinecone_client import get_index_stats
from app.rag import answer_question, ingest_document

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

UPLOAD_DIR = PROJECT_DIR / settings.upload_dir
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Pinecone RAG Forensics Lab")

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


@app.on_event("startup")
def startup() -> None:
    init_db()


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.get("/register")
def register_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "register.html", {})


@app.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    errors = []

    if len(username) < 3:
        errors.append("Username must be at least 3 characters.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if password != confirm_password:
        errors.append("Passwords do not match.")

    if not errors:
        if get_user_by_username(username):
            errors.append("Username already taken.")
        if get_user_by_email(email):
            errors.append("Email already registered.")

    if errors:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"errors": errors, "username": username, "email": email},
            status_code=400,
        )

    user = create_user(
        username=username,
        email=email,
        hashed_password=hash_password(password),
    )
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token",
        value=create_token(user.id),
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
    )
    return response


@app.get("/login")
def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = get_user_by_username(username)
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid username or password.", "username": username},
            status_code=401,
        )

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token",
        value=create_token(user.id),
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/")
def home(request: Request):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    uid = current_user.id
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "current_user": current_user,
            "documents": list_documents(limit=10, user_id=uid),
            "document_count": document_count(user_id=uid),
            "chunk_count": chunk_count(user_id=uid),
            "namespaces": namespaces(user_id=uid),
            "categories": categories(user_id=uid),
            "pinecone_stats": get_index_stats(),
        },
    )


# ── Upload ────────────────────────────────────────────────────────────────────

@app.get("/upload")
def upload_page(request: Request):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    uid = current_user.id
    return templates.TemplateResponse(
        request,
        "upload.html",
        {
            "current_user": current_user,
            "namespaces": namespaces(user_id=uid),
            "categories": categories(user_id=uid),
            "default_namespace": f"user-{uid}",
        },
    )


@app.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile,
    title: str = Form(...),
    category: str = Form(...),
    namespace: str = Form(...),
):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    uid = current_user.id
    effective_ns = namespace.strip() or f"user-{uid}"

    try:
        if not file.filename:
            raise ValueError("No file was uploaded.")

        safe_name = Path(file.filename).name
        saved_path = UPLOAD_DIR / safe_name

        with saved_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = ingest_document(
            file_path=saved_path,
            title=title.strip(),
            category=category.strip(),
            namespace=effective_ns,
            original_filename=safe_name,
            user_id=uid,
        )

        return templates.TemplateResponse(
            request,
            "upload.html",
            {
                "current_user": current_user,
                "message": "Document uploaded and indexed successfully.",
                "result": result,
                "namespaces": namespaces(user_id=uid),
                "categories": categories(user_id=uid),
                "default_namespace": f"user-{uid}",
            },
        )

    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "upload.html",
            {
                "current_user": current_user,
                "error": str(exc),
                "namespaces": namespaces(user_id=uid),
                "categories": categories(user_id=uid),
                "default_namespace": f"user-{uid}",
            },
            status_code=400,
        )


# ── Ask ───────────────────────────────────────────────────────────────────────

@app.get("/ask")
def ask_page(request: Request):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    uid = current_user.id
    return templates.TemplateResponse(
        request,
        "ask.html",
        {
            "current_user": current_user,
            "namespaces": namespaces(user_id=uid),
            "categories": categories(user_id=uid),
            "top_k": 5,
        },
    )


@app.post("/ask")
async def ask(
    request: Request,
    question: str = Form(...),
    namespace: str = Form(...),
    category: str = Form(""),
    top_k: int = Form(5),
):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    uid = current_user.id

    try:
        result = answer_question(
            question=question.strip(),
            namespace=namespace.strip() or f"user-{uid}",
            category=category.strip() or None,
            top_k=max(1, min(top_k, 20)),
        )

        return templates.TemplateResponse(
            request,
            "ask.html",
            {
                "current_user": current_user,
                "namespaces": namespaces(user_id=uid),
                "categories": categories(user_id=uid),
                **result,
            },
        )

    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "ask.html",
            {
                "current_user": current_user,
                "error": str(exc),
                "question": question,
                "namespace": namespace,
                "category": category,
                "top_k": top_k,
                "namespaces": namespaces(user_id=uid),
                "categories": categories(user_id=uid),
            },
            status_code=400,
        )


# ── Eval ──────────────────────────────────────────────────────────────────────

@app.get("/eval")
def eval_page(request: Request):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    uid = current_user.id
    return templates.TemplateResponse(
        request,
        "eval.html",
        {
            "current_user": current_user,
            "cases": list_eval_cases(user_id=uid),
            "namespaces": namespaces(user_id=uid),
            "categories": categories(user_id=uid),
        },
    )


@app.post("/eval/add")
async def eval_add(
    request: Request,
    question: str = Form(...),
    expected_source: str = Form(...),
    expected_terms: str = Form(""),
    namespace: str = Form("demo"),
    category: str = Form(""),
):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    add_eval_case(
        question=question.strip(),
        expected_source=expected_source.strip(),
        expected_terms=expected_terms.splitlines(),
        namespace=namespace.strip() or f"user-{current_user.id}",
        category=category.strip(),
        user_id=current_user.id,
    )

    return RedirectResponse(url="/eval", status_code=303)


@app.post("/eval/run")
async def eval_run(
    request: Request,
    top_k: int = Form(5),
):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    uid = current_user.id
    cases = list_eval_cases(user_id=uid)

    results = [
        run_eval_case(case, top_k=max(1, min(top_k, 20)))
        for case in cases
    ]

    passed = sum(1 for r in results if r["passed"])

    return templates.TemplateResponse(
        request,
        "eval.html",
        {
            "current_user": current_user,
            "cases": cases,
            "results": results,
            "passed": passed,
            "total": len(results),
            "namespaces": namespaces(user_id=uid),
            "categories": categories(user_id=uid),
        },
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}
