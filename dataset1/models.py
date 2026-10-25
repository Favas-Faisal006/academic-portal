# models.py (Example using SQLAlchemy / SQLModel)
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    STUDENT = "student"
    FACULTY = "faculty"
    HOD = "hod"
    ADMIN = "admin"

class LeaveStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True)
    register_number = Column(String(20), unique=True, index=True)  # e.g., GIK23AIM006
    name = Column(String(100), nullable=False)
    face_label = Column(String(100), unique=True)                  # Maps to le.classes_
    ktu_activity_points = Column(Integer, default=0)

class LectureSession(Base):
    __tablename__ = "lecture_sessions"
    id = Column(Integer, primary_key=True)
    subject_code = Column(String(20), nullable=False)
    faculty_id = Column(Integer, ForeignKey("users.id"))
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("lecture_sessions.id"))
    student_id = Column(Integer, ForeignKey("students.id"))
    status = Column(String(20), default="Absent")                  # Present, Absent, Duty Leave
    timestamp = Column(DateTime)
    confidence = Column(Float)

class EngagementMetric(Base):
    __tablename__ = "engagement_metrics"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("lecture_sessions.id"))
    student_id = Column(Integer, ForeignKey("students.id"))
    attentive_score = Column(Float)                                # Calculated percentage
    neutral_score = Column(Float)
    non_attentive_score = Column(Float)

class DutyLeave(Base):
    __tablename__ = "duty_leaves"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    date = Column(DateTime, nullable=False)
    reason = Column(String(255))
    status = Column(Enum(LeaveStatus), default=LeaveStatus.PENDING)