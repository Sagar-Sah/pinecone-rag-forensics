from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import settings

Path("data").mkdir(exist_ok=True)

engine = create_engine(settings.sqlite_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), index=True, nullable=True
    )
    doc_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    namespace: Mapped[str] = mapped_column(String(100), index=True)
    source_file: Mapped[str] = mapped_column(String(255))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), index=True, nullable=True
    )
    question: Mapped[str] = mapped_column(Text)
    expected_source: Mapped[str] = mapped_column(String(255))
    expected_terms: Mapped[str] = mapped_column(Text, default="")
    namespace: Mapped[str] = mapped_column(String(100), default="demo")
    category: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    # Migrate existing tables: add user_id column if missing
    with engine.connect() as conn:
        for table, col_def in [
            ("documents", "user_id INTEGER REFERENCES users(id)"),
            ("eval_cases", "user_id INTEGER REFERENCES users(id)"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_def}"))
                conn.commit()
            except Exception:
                pass  # column already exists


def get_session() -> Session:
    return SessionLocal()


# ── User ──────────────────────────────────────────────────────────────────────

def create_user(username: str, email: str, hashed_password: str) -> User:
    with get_session() as db:
        user = User(username=username, email=email, hashed_password=hashed_password)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def get_user_by_username(username: str) -> Optional[User]:
    with get_session() as db:
        return db.query(User).filter(User.username == username).first()


def get_user_by_email(email: str) -> Optional[User]:
    with get_session() as db:
        return db.query(User).filter(User.email == email).first()


def get_user_by_id(user_id: int) -> Optional[User]:
    with get_session() as db:
        return db.query(User).filter(User.id == user_id).first()


# ── Document ──────────────────────────────────────────────────────────────────

def save_document(
    doc_id: str,
    title: str,
    category: str,
    namespace: str,
    source_file: str,
    chunk_count: int,
    user_id: int,
) -> Document:
    with get_session() as db:
        existing = db.query(Document).filter(Document.doc_id == doc_id).first()

        if existing:
            existing.title = title
            existing.category = category
            existing.namespace = namespace
            existing.source_file = source_file
            existing.chunk_count = chunk_count
            existing.uploaded_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(existing)
            return existing

        document = Document(
            doc_id=doc_id,
            title=title,
            category=category,
            namespace=namespace,
            source_file=source_file,
            chunk_count=chunk_count,
            user_id=user_id,
        )

        db.add(document)
        db.commit()
        db.refresh(document)
        return document


def list_documents(limit: int = 25, user_id: Optional[int] = None) -> list[Document]:
    with get_session() as db:
        q = db.query(Document)
        if user_id is not None:
            q = q.filter(Document.user_id == user_id)
        return q.order_by(Document.uploaded_at.desc()).limit(limit).all()


def document_count(user_id: Optional[int] = None) -> int:
    with get_session() as db:
        q = db.query(func.count(Document.id))
        if user_id is not None:
            q = q.filter(Document.user_id == user_id)
        return int(q.scalar() or 0)


def chunk_count(user_id: Optional[int] = None) -> int:
    with get_session() as db:
        q = db.query(func.coalesce(func.sum(Document.chunk_count), 0))
        if user_id is not None:
            q = q.filter(Document.user_id == user_id)
        return int(q.scalar() or 0)


def namespaces(user_id: Optional[int] = None) -> list[str]:
    with get_session() as db:
        q = db.query(Document.namespace).distinct().order_by(Document.namespace.asc())
        if user_id is not None:
            q = q.filter(Document.user_id == user_id)
        rows = q.all()

    values = [row[0] for row in rows if row[0]]
    return values or ([f"user-{user_id}"] if user_id else ["demo"])


def categories(user_id: Optional[int] = None) -> list[str]:
    with get_session() as db:
        q = db.query(Document.category).distinct().order_by(Document.category.asc())
        if user_id is not None:
            q = q.filter(Document.user_id == user_id)
        rows = q.all()

    return [row[0] for row in rows if row[0]]


# ── EvalCase ──────────────────────────────────────────────────────────────────

def add_eval_case(
    question: str,
    expected_source: str,
    expected_terms: Iterable[str],
    namespace: str,
    category: str = "",
    user_id: Optional[int] = None,
) -> EvalCase:
    with get_session() as db:
        case = EvalCase(
            question=question,
            expected_source=expected_source,
            expected_terms="\n".join(
                [term.strip() for term in expected_terms if term.strip()]
            ),
            namespace=namespace,
            category=category or "",
            user_id=user_id,
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        return case


def list_eval_cases(user_id: Optional[int] = None) -> list[EvalCase]:
    with get_session() as db:
        q = db.query(EvalCase).order_by(EvalCase.created_at.desc())
        if user_id is not None:
            q = q.filter(EvalCase.user_id == user_id)
        return q.all()
