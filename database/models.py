# database/models.py
import os
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

Base = declarative_base()

# Database connection setup
DATABASE_URL = os.getenv("DATABASE_URL")


def get_engine():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set.")
    return create_engine(DATABASE_URL)


# Update SessionLocal to use the helper function.
def get_session():
    engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


# Update init_db to use the helper function.
def init_db():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True)
    player = Column(String, index=True)
    year = Column(Integer)
    set_name = Column(String)
    card_num = Column(String)
    attributes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint(
            "player",
            "year",
            "set_name",
            "card_num",
            "attributes",
            name="_card_uc",
        ),
    )


class Sale(Base):
    __tablename__ = "sales_history"
    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey("cards.id"))
    sold_at = Column(DateTime)
    price = Column(Float)
    grade = Column(String)
    company = Column(String)
    source = Column(String)
    source_item_id = Column(String)
    __table_args__ = (
        UniqueConstraint("source", "source_item_id", name="_sale_uc"),
    )
