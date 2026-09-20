from django.contrib import admin
from .models import UserProfile, Student, LectureSession, AttendanceRecord, DutyLeave

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('register_number', 'full_name', 'face_label', 'ktu_activity_points')
    search_fields = ('register_number', 'full_name', 'face_label')

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'session', 'status', 'time_logged', 'liveness_verified', 'attentive_rate', 'non_attentive_rate')
    list_filter = ('status', 'session__subject_code', 'liveness_verified')
    search_fields = ('student__register_number', 'student__full_name')

@admin.register(DutyLeave)
class DutyLeaveAdmin(admin.ModelAdmin):
    list_display = ('student', 'leave_date', 'status', 'applied_date')
    list_filter = ('status',)

admin.site.register(UserProfile)
admin.site.register(LectureSession)

from .models import InternalAssessment, ActivityPointLog

admin.site.register(InternalAssessment)
admin.site.register(ActivityPointLog)