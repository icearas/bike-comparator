from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    sku = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    currency = Column(String, default="PLN")
    shop = Column(String, nullable=False)
    category = Column(String, nullable=False)
    url = Column(String, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("name", "shop", name="uq_name_shop"),
    )

class MatchedProduct(Base):
    __tablename__ = "matched_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name_normalized = Column(String, nullable=False)  # np. "Shimano XT RD-M8100"
    category = Column(String, nullable=False)

    # Produkt z centrumrowerowe.pl
    cr_product_id = Column(Integer, nullable=True)
    cr_name = Column(String, nullable=True)
    cr_price_pln = Column(Float, nullable=True)
    cr_url = Column(String, nullable=True)

    # Produkt z bike-discount.de
    bd_product_id = Column(Integer, nullable=True)
    bd_name = Column(String, nullable=True)
    bd_price_eur = Column(Float, nullable=True)
    bd_url = Column(String, nullable=True)

    # Meta
    match_method = Column(String, nullable=True)  # "code" albo "ai"
    match_confidence = Column(Float, nullable=True)  # 0.0 - 1.0
    matched_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("cr_product_id", "bd_product_id", name="uq_match"),
    )


class FilterRule(Base):
    __tablename__ = "filter_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String, nullable=False)
    brand = Column(String, nullable=False)
    model_keyword = Column(String, nullable=True)  # None = bierz wszystkie tej marki
    active = Column(Integer, default=1)

engine = create_engine("sqlite:///bike_comparator.db")
SessionLocal = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    init_db()
    print("Baza danych utworzona!")