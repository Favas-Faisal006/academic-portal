from django.urls import path
from .views import (
    sync_attendance_session,
    faculty_dashboard,
    toggle_attendance,
    process_leave,
    student_dashboard,
    apply_duty_leave,
    user_login_view,
    role_redirect,
    user_logout_view,
    hod_dashboard,
    export_attendance_csv,
    add_activity_points,
)

urlpatterns = [
    # Authentication & Navigation
    path('', user_login_view, name='login'),
    path('logout/', user_logout_view, name='logout'),
    path('redirect/', role_redirect, name='role_redirect'),

    # Faculty Dashboard & Actions
    path('dashboard/faculty/', faculty_dashboard, name='faculty_dashboard'),
    path('dashboard/faculty/toggle/<int:record_id>/', toggle_attendance, name='toggle_attendance'),
    path('dashboard/faculty/leave/<int:leave_id>/<str:action>/', process_leave, name='process_leave'),
    path('dashboard/faculty/export/', export_attendance_csv, name='export_attendance_csv'),

    # Student Dashboard & Actions
    path('dashboard/student/<int:student_id>/', student_dashboard, name='student_dashboard'),
    path('dashboard/student/<int:student_id>/apply-leave/', apply_duty_leave, name='apply_duty_leave'),

    # HOD Dashboard
    path('dashboard/hod/', hod_dashboard, name='hod_dashboard'),

    # APIs called by run.py backend
    path('api/attendance/sync/', sync_attendance_session, name='sync_attendance_session'),
    path('api/activity-points/add/', add_activity_points, name='add_activity_points'),
]