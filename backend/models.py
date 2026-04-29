"""SQLAlchemy ORM models for stock data."""
from sqlalchemy import Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class StockBasic(Base):
    __tablename__ = "stock_basic"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    market: Mapped[str] = mapped_column(Text, nullable=False)
    industry: Mapped[str] = mapped_column(Text, default="")
    list_date: Mapped[str] = mapped_column(Text, default="")
    is_st: Mapped[int] = mapped_column(Integer, default=0)


class StockConcept(Base):
    __tablename__ = "stock_concept"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    concept_name: Mapped[str] = mapped_column(Text, primary_key=True)


class StockDaily(Base):
    __tablename__ = "stock_daily"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    date: Mapped[str] = mapped_column(Text, primary_key=True)
    close: Mapped[float] = mapped_column(Float, default=0)
    volume: Mapped[float] = mapped_column(Float, default=0)
    turnover_rate: Mapped[float] = mapped_column(Float, default=0)
    pe_ttm: Mapped[float] = mapped_column(Float, default=0)
    pb: Mapped[float] = mapped_column(Float, default=0)
    roe: Mapped[float] = mapped_column(Float, default=0)
    revenue_growth_3y: Mapped[float] = mapped_column(Float, default=0)
    ma5: Mapped[float] = mapped_column(Float, default=0)
    ma20: Mapped[float] = mapped_column(Float, default=0)
    ma60: Mapped[float] = mapped_column(Float, default=0)
    macd_signal: Mapped[str] = mapped_column(Text, default="")
    market_cap: Mapped[float] = mapped_column(Float, default=0)
    nmc: Mapped[float] = mapped_column(Float, default=0)
    float_shares: Mapped[float] = mapped_column(Float, default=0)
    dividend_yield: Mapped[float] = mapped_column(Float, default=0)
    change_pct: Mapped[float] = mapped_column(Float, default=0)
    volume_ratio: Mapped[float] = mapped_column(Float, default=0)
