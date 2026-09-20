from django.db import models
from django.contrib.auth.models import User

# =========================
# USER PROFILES & ROLES
# =========================
class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('STUDENT', 'Student'),
        ('FACULTY', 'Faculty'),
        ('HOD', 'Head of Department'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='STUDENT')
    department = models.CharField(max_length=50, default='AI & ML')

    def __str__(self):
        return f"{self.user.username} ({self.role})"

# =========================
# STUDENT MASTER REGISTRY
# =========================
class Student(models.Model):
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE, null=True, blank=True)
    register_number = models.CharField(max_length=30, unique=True)  # e.g. GIK23AIM006
    full_name = models.CharField(max_length=100)
    semester = models.IntegerField(default=6)
    face_label = models.CharField(max_length=100, unique=True)      # Folder name used in Train.py
    ktu_activity_points = models.IntegerField(default=0)            # KTU Activity Points ledger

    def __str__(self):
        return f"{self.register_number} - {self.full_name}"

# =========================
# LECTURE SESSIONS
# =========================
class LectureSession(models.Model):
    subject_code = models.CharField(max_length=20)                  # e.g. CST306
    subject_name = models.CharField(max_length=100)
    faculty = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    session_date = models.DateField(auto_now_add=True)
    start_time = models.TimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject_code} ({self.session_date})"

# =========================
# ATTENDANCE & ENGAGEMENT
# =========================
class AttendanceRecord(models.Model):
    STATUS_CHOICES = (
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Duty Leave', 'Duty Leave'),
    )
    session = models.ForeignKey(LectureSession, on_delete=models.CASCADE, related_name='attendance_logs')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Absent')
    time_logged = models.CharField(max_length=20, default='-')
    liveness_verified = models.BooleanField(default=False)

    # Affect / Engagement Metrics (Percentages calculated from Run.py)
    attentive_rate = models.FloatField(default=0.0)
    neutral_rate = models.FloatField(default=0.0)
    non_attentive_rate = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('session', 'student')

    def __str__(self):
        return f"{self.student.register_number} | {self.session.subject_code} | {self.status}"

# =========================
# DUTY LEAVE MANAGEMENT
# =========================
class DutyLeave(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='duty_leaves')
    applied_date = models.DateField(auto_now_add=True)
    leave_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Duty Leave: {self.student.register_number} - {self.leave_date} ({self.status})"


# =========================
# ACADEMIC MARKS & ASSESSMENTS
# =========================
class InternalAssessment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='internal_marks')
    subject_code = models.CharField(max_length=20)
    series_1_marks = models.FloatField(default=0.0)
    series_2_marks = models.FloatField(default=0.0)
    assignment_marks = models.FloatField(default=0.0)
    attendance_marks = models.FloatField(default=0.0)

    @property
    def total_internal(self):
        return round(self.series_1_marks + self.series_2_marks + self.assignment_marks + self.attendance_marks, 2)

    def __str__(self):
        return f"{self.student.register_number} - {self.subject_code} (Internal: {self.total_internal})"

class ActivityPointLog(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='activity_logs')
    activity_name = models.CharField(max_length=150)  # e.g., NPTEL Course, Hackathon Winner, Sports
    points_claimed = models.IntegerField(default=0)
    date_awarded = models.DateField(auto_now_add=True)
    verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student.register_number} - {self.activity_name} ({self.points_claimed} pts)"