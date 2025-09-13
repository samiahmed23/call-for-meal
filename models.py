from sqlalchemy import Column, String, Integer, Float, Time, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship

from database import Base

class Agency(Base):
    __tablename__ = 'agencies'
    id = Column(Integer, primary_key=True, autoincrement=True)
    agency_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # "market" or "shopping_partner"
    address = Column(String)
    phone = Column(String)
    latitude = Column(Float)  # Add this
    longitude = Column(Float)  # Add this

    hours_of_operation = relationship("HoursOfOperation", back_populates="agency", cascade="all, delete-orphan")
    wraparound_services = relationship("WraparoundService", back_populates="agency", cascade="all, delete-orphan")
    cultures_served = relationship("CultureServed", back_populates="agency", cascade="all, delete-orphan")

class HoursOfOperation(Base):
    __tablename__ = 'hours_of_operation'
    id = Column(Integer, primary_key=True, autoincrement=True)
    agency_id = Column(String, ForeignKey('agencies.id'))
    day_of_week = Column(String)
    start_time = Column(Time)
    end_time = Column(Time)
    frequency = Column(String)
    distribution_model = Column(String)
    food_format = Column(String)
    appointment_only = Column(Boolean)
    pantry_requirements = Column(String)

    agency = relationship("Agency", back_populates="hours_of_operation")

class WraparoundService(Base):
    __tablename__ = 'wraparound_services'
    id = Column(Integer, primary_key=True, autoincrement=True)
    agency_id = Column(String, ForeignKey('agencies.id'))
    service = Column(String)

    agency = relationship("Agency", back_populates="wraparound_services")

class CultureServed(Base):
    __tablename__ = 'cultures_served'
    id = Column(Integer, primary_key=True, autoincrement=True)
    agency_id = Column(String, ForeignKey('agencies.id'))
    cultures = Column(String)

    agency = relationship("Agency", back_populates="cultures_served")
