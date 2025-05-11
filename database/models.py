# database/models.py
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
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

# Update the DATABASE_URL to use psycopg driver explicitly
DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")

_engine = None  # Module-level variable to store the engine


def get_engine():
    global _engine
    if _engine is None:  # Initialize engine only once
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is not set.")
        _engine = create_engine(DATABASE_URL)
    return _engine


# Define SessionLocal for consistent session management
# Bind SessionLocal once using the engine
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


# Update SessionLocal to use the helper function.
def get_session():
    # Simply return a new session from the globally configured SessionLocal
    return SessionLocal()


# Update init_db to use the helper function.
def init_db():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def current_utc_time():
    return datetime.now(timezone.utc)


class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True)
    player = Column(String, index=True)
    year = Column(Integer)
    set_name = Column(String)
    card_num = Column(String)
    attributes = Column(Text)
    created_at = Column(DateTime, default=current_utc_time)
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


class ScrapeTracker(Base):
    __tablename__ = "scrape_tracker"
    id = Column(Integer, primary_key=True)
    site_name = Column(String, nullable=False)
    data_type = Column(String, nullable=False)
    last_run_timestamp = Column(String, nullable=False)
    __table_args__ = (
        UniqueConstraint("site_name", "data_type", name="_site_datatype_uc"),
    )


class CardValuation(Base):
    __tablename__ = "card_valuations"
    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey("cards.id"))
    estimated_value = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    valuation_date = Column(String, nullable=False)
    source = Column(String, nullable=False)
    valuation_type = Column(String)
    source_url_to_valuation_info = Column(String)
    grade = Column(String)
    grading_company = Column(String)
    raw_card_name_from_source = Column(String)
    scraped_at = Column(DateTime, default=current_utc_time)
    __table_args__ = (
        UniqueConstraint(
            "card_id",
            "source",
            "valuation_date",
            "valuation_type",
            "grade",
            "grading_company",
            name="_valuation_uc",
        ),
    )


# Refactored database models to separate ActiveListing and SoldListing
class ActiveListing(Base):
    __tablename__ = "active_listings"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, index=True)
    listing_price = Column(Float)
    currency = Column(String)
    listing_date = Column(DateTime)
    source = Column(String)
    source_item_id = Column(String, unique=True, index=True)
    source_url = Column(String)
    grade = Column(String)
    grading_company = Column(String)
    last_seen_at = Column(DateTime)
    comp_value = Column(Float)  # Median or average comp value
    is_undervalued = Column(Boolean)  # Indicates if the listing is undervalued


class SoldListing(Base):
    __tablename__ = "sold_listings"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, index=True)
    sale_price = Column(Float)
    currency = Column(String)
    sale_date = Column(DateTime)
    source = Column(String)
    source_item_id = Column(String, unique=True, index=True)
    source_url = Column(String)
    grade = Column(String)
    grading_company = Column(String)


def add_card_definition(listing):
    """
    Add or retrieve a card definition based on the listing details.
    Returns the card_id.
    """
    session = get_session()
    try:
        # Extract card details from the listing
        player = listing.get("player_name")
        year = listing.get("card_year")
        set_name = listing.get("card_set")
        card_num = listing.get("card_number")
        attributes = listing.get("attributes")

        # Check if the card already exists
        card = (
            session.query(Card)
            .filter_by(
                player=player,
                year=year,
                set_name=set_name,
                card_num=card_num,
                attributes=attributes,
            )
            .first()
        )

        if not card:
            # Create a new card entry if it doesn't exist
            card = Card(
                player=player,
                year=year,
                set_name=set_name,
                card_num=card_num,
                attributes=attributes,
            )
            session.add(card)
            session.commit()

        return card.id

    except Exception as e:
        session.rollback()
        raise e

    finally:
        session.close()


# New function to add or update an active listing
def add_active_listing_to_db(session, card_id, listing_data):
    try:
        listing = (
            session.query(ActiveListing)
            .filter_by(source_item_id=listing_data["source_item_id"])
            .first()
        )
        if listing:
            # Update existing listing
            listing.listing_price = listing_data["listing_price"]
            listing.currency = listing_data["currency"]
            listing.listing_date = listing_data["listing_date"]
            listing.source = listing_data["source"]
            listing.source_url = listing_data["source_url"]
            listing.grade = listing_data["grade"]
            listing.grading_company = listing_data["grading_company"]
            listing.last_seen_at = current_utc_time()
        else:
            # Insert new listing
            listing = ActiveListing(
                card_id=card_id,
                listing_price=listing_data["listing_price"],
                currency=listing_data["currency"],
                listing_date=listing_data["listing_date"],
                source=listing_data["source"],
                source_item_id=listing_data["source_item_id"],
                source_url=listing_data["source_url"],
                grade=listing_data["grade"],
                grading_company=listing_data["grading_company"],
                last_seen_at=current_utc_time(),
            )
            session.add(listing)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e


# New function to add a sold listing
def add_sold_listing_to_db(session, card_id, sale_data):
    try:
        sold_listing = SoldListing(
            card_id=card_id,
            sale_price=sale_data["sale_price"],
            currency=sale_data["currency"],
            sale_date=sale_data["sale_date"],
            source=sale_data["source"],
            source_item_id=sale_data["source_item_id"],
            source_url=sale_data["source_url"],
            grade=sale_data["grade"],
            grading_company=sale_data["grading_company"],
        )
        session.add(sold_listing)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e


def get_last_run_timestamp(site_name, data_type):
    session = get_session()
    try:
        tracker = (
            session.query(ScrapeTracker)
            .filter_by(site_name=site_name, data_type=data_type)
            .first()
        )
        return tracker.last_run_timestamp if tracker else None
    finally:
        session.close()


def update_last_run_timestamp(site_name, data_type, timestamp_iso):
    session = get_session()
    try:
        tracker = (
            session.query(ScrapeTracker)
            .filter_by(site_name=site_name, data_type=data_type)
            .first()
        )
        if tracker:
            tracker.last_run_timestamp = timestamp_iso
        else:
            tracker = ScrapeTracker(
                site_name=site_name,
                data_type=data_type,
                last_run_timestamp=timestamp_iso,
            )
            session.add(tracker)
        session.commit()
    finally:
        session.close()


def add_valuation(
    card_id,
    estimated_value,
    currency,
    valuation_date,
    source,
    valuation_type=None,
    source_url_to_valuation_info=None,
    grade=None,
    grading_company=None,
    raw_card_name_from_source=None,
):
    session = get_session()
    try:
        exists = (
            session.query(CardValuation)
            .filter_by(
                card_id=card_id,
                source=source,
                valuation_date=valuation_date,
                valuation_type=valuation_type,
                grade=grade,
                grading_company=grading_company,
            )
            .first()
        )
        if exists:
            return False
        record = CardValuation(
            card_id=card_id,
            estimated_value=estimated_value,
            currency=currency,
            valuation_date=valuation_date,
            source=source,
            valuation_type=valuation_type,
            source_url_to_valuation_info=source_url_to_valuation_info,
            grade=grade,
            grading_company=grading_company,
            raw_card_name_from_source=raw_card_name_from_source,
        )
        session.add(record)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
