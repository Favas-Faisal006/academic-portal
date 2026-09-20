import csv
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, redirect, get_object_or_404
from .models import Student, LectureSession, AttendanceRecord, DutyLeave

# ==========================================
# 1. API VIEW (CALLED BY Run.py)
# ==========================================
@api_view(['POST'])
@permission_classes([AllowAny])
def sync_attendance_session(request):
    data = request.data
    session_date = data.get('session_date')
    subject_code = data.get('subject_code', 'CST306')
    subject_name = data.get('subject_name', 'Artificial Intelligence')
    records = data.get('records', [])

    if not records:
        return Response({"error": "No records found in payload"}, status=status.HTTP_400_BAD_REQUEST)

    # Fetch or create the active lecture session
    session, _ = LectureSession.objects.get_or_create(
        subject_code=subject_code,
        subject_name=subject_name,
        session_date=session_date
    )

    created_count = 0
    updated_count = 0

    for item in records:
        face_label = item.get('student_id')
        attendance_status = item.get('status', 'Absent')
        time_logged = item.get('time_logged', '-')
        liveness_passed = item.get('liveness_passed', False)
        engagement = item.get('engagement', {})

        # Find student by face_label or create a fallback profile
        student, _ = Student.objects.get_or_create(
            face_label=face_label,
            defaults={
                'register_number': face_label,
                'full_name': face_label.capitalize()
            }
        )

        record, created = AttendanceRecord.objects.update_or_create(
            session=session,
            student=student,
            defaults={
                'status': attendance_status,
                'time_logged': time_logged,
                'liveness_verified': liveness_passed,
                'attentive_rate': engagement.get('attentive_rate', 0.0),
                'neutral_rate': engagement.get('neutral_rate', 0.0),
                'non_attentive_rate': engagement.get('non_attentive_rate', 0.0),
            }
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    return Response({
        "message": "Attendance & Engagement session successfully synchronized",
        "created_records": created_count,
        "updated_records": updated_count,
        "session_id": session.id
    }, status=status.HTTP_200_OK)


# ==========================================
# 2. WEB DASHBOARD VIEWS (FACULTY & STUDENT)
# ==========================================
from django.db.models import Avg

def faculty_dashboard(request):
    attendance_records = AttendanceRecord.objects.select_related('student', 'session').order_by('-session__session_date')
    pending_leaves = DutyLeave.objects.filter(status='PENDING').select_related('student')

    # Calculate average affect across all recorded students in the session
    metrics = attendance_records.aggregate(
        avg_attentive=Avg('attentive_rate'),
        avg_neutral=Avg('neutral_rate'),
        avg_non_attentive=Avg('non_attentive_rate')
    )

    avg_attentive = round(metrics['avg_attentive'] or 0.0, 1)
    avg_neutral = round(metrics['avg_neutral'] or 0.0, 1)
    avg_non_attentive = round(metrics['avg_non_attentive'] or 0.0, 1)

    return render(request, 'academic_portal/faculty_dashboard.html', {
        'attendance_records': attendance_records,
        'pending_leaves': pending_leaves,
        'avg_attentive': avg_attentive,
        'avg_neutral': avg_neutral,
        'avg_non_attentive': avg_non_attentive,
    })

def toggle_attendance(request, record_id):
    if request.method == 'POST':
        record = get_object_or_404(AttendanceRecord, id=record_id)
        record.status = 'Absent' if record.status == 'Present' else 'Present'
        record.save()
    return redirect('faculty_dashboard')

def process_leave(request, leave_id, action):
    if request.method == 'POST':
        leave = get_object_or_404(DutyLeave, id=leave_id)
        if action == 'approve':
            leave.status = 'APPROVED'
            # Automatically update attendance logs on that date to "Duty Leave"
            AttendanceRecord.objects.filter(
                student=leave.student,
                session__session_date=leave.leave_date
            ).update(status='Duty Leave')
        elif action == 'reject':
            leave.status = 'REJECTED'
        leave.save()
    return redirect('faculty_dashboard')

from .models import InternalAssessment, ActivityPointLog

def student_dashboard(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    records = AttendanceRecord.objects.filter(student=student).select_related('session').order_by('-session__session_date')
    internals = InternalAssessment.objects.filter(student=student)
    activities = ActivityPointLog.objects.filter(student=student)

    # Compute overall attendance percentage
    total_sessions = records.count()
    present_sessions = records.filter(status__in=['Present', 'Duty Leave']).count()
    attendance_pct = round((present_sessions / total_sessions * 100), 1) if total_sessions > 0 else 0.0

    return render(request, 'academic_portal/student_dashboard.html', {
        'student': student,
        'attendance_records': records,
        'internals': internals,
        'activities': activities,
        'attendance_pct': attendance_pct,
    })

def apply_duty_leave(request, student_id):
    if request.method == 'POST':
        student = get_object_or_404(Student, id=student_id)
        leave_date = request.POST.get('leave_date')
        reason = request.POST.get('reason')
        DutyLeave.objects.create(student=student, leave_date=leave_date, reason=reason)
        return redirect('student_dashboard', student_id=student.id)


from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

def user_login_view(request):
    if request.user.is_authenticated:
        return redirect('role_redirect')

    error_message = None
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            return redirect('role_redirect')
        else:
            error_message = "Invalid username or password"

    return render(request, 'academic_portal/login.html', {'error': error_message})

@login_required
@login_required
def role_redirect(request):
    if hasattr(request.user, 'profile'):
        role = request.user.profile.role
        if role == 'HOD':
            return redirect('hod_dashboard')
        elif role == 'FACULTY':
            return redirect('faculty_dashboard')
        elif role == 'STUDENT':
            student = Student.objects.filter(user_profile=request.user.profile).first()
            if student:
                return redirect('student_dashboard', student_id=student.id)

    if request.user.is_staff or request.user.is_superuser:
        return redirect('hod_dashboard')

    return HttpResponseForbidden("User profile not configured with valid role.")

    # Superuser or unlinked user fallback
    if request.user.is_staff or request.user.is_superuser:
        return redirect('faculty_dashboard')

    return HttpResponseForbidden("User profile not configured with valid role.")

def user_logout_view(request):
    logout(request)
    return redirect('login')



def export_attendance_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Institutional_Attendance_Report.csv"'

    writer = csv.writer(response)
    writer.writerow(['Register Number', 'Student Name', 'Subject', 'Session Date', 'Status', 'Logged Time', 'Attentive %', 'Non-Attentive %'])

    records = AttendanceRecord.objects.select_related('student', 'session').all()
    for r in records:
        writer.writerow([
            r.student.register_number,
            r.student.full_name,
            r.session.subject_code,
            r.session.session_date,
            r.status,
            r.time_logged,
            f"{r.attentive_rate}%",
            f"{r.non_attentive_rate}%"
        ])

    return response

from django.db.models import Count, Q

def hod_dashboard(request):
    students = Student.objects.all().prefetch_related('attendance_records')

    total_students = students.count()
    total_records = AttendanceRecord.objects.count()
    present_records = AttendanceRecord.objects.filter(status__in=['Present', 'Duty Leave']).count()

    overall_attendance_pct = round((present_records / total_records * 100), 1) if total_records > 0 else 0.0

    # Identify students at shortage risk (< 75% attendance)
    shortage_students = []
    for s in students:
        s_total = s.attendance_records.count()
        if s_total > 0:
            s_present = s.attendance_records.filter(status__in=['Present', 'Duty Leave']).count()
            pct = round((s_present / s_total * 100), 1)
            if pct < 75.0:
                shortage_students.append({
                    'student': s,
                    'total': s_total,
                    'attended': s_present,
                    'percentage': pct
                })

    # Department affect summary
    affect_metrics = AttendanceRecord.objects.filter(status='Present').aggregate(
        dept_attentive=Avg('attentive_rate'),
        dept_neutral=Avg('neutral_rate'),
        dept_non_attentive=Avg('non_attentive_rate')
    )

    pending_duty_leaves = DutyLeave.objects.filter(status='PENDING').count()
    approved_duty_leaves = DutyLeave.objects.filter(status='APPROVED').count()

    return render(request, 'academic_portal/hod_dashboard.html', {
        'total_students': total_students,
        'overall_attendance_pct': overall_attendance_pct,
        'shortage_students': shortage_students,
        'shortage_count': len(shortage_students),
        'pending_leaves': pending_duty_leaves,
        'approved_leaves': approved_duty_leaves,
        'dept_attentive': round(affect_metrics['dept_attentive'] or 0.0, 1),
        'dept_neutral': round(affect_metrics['dept_neutral'] or 0.0, 1),
        'dept_non_attentive': round(affect_metrics['dept_non_attentive'] or 0.0, 1),
    })
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Student, ActivityPointLog

@csrf_exempt
def add_activity_points(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            reg_num = data.get('register_number')
            activity = data.get('activity_name')
            points = data.get('points_claimed', 0)

            # Look up student by KTU register number
            student = Student.objects.get(register_number=reg_num)

            # 1. Create entry in ActivityPointLog
            ActivityPointLog.objects.create(
                student=student,
                activity_name=activity,
                points_claimed=points,
                verified=True
            )

            # 2. Update cumulative KTU points on Student model
            student.ktu_activity_points += points
            student.save()

            return JsonResponse({
                "status": "success",
                "message": "Points updated",
                "total_points": student.ktu_activity_points
            }, status=201)

        except Student.DoesNotExist:
            return JsonResponse({"error": "Student register number not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Only POST requests are allowed"}, status=405)
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Student, ActivityPointLog

@csrf_exempt
def add_activity_points(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            reg_num = data.get('register_number')
            activity = data.get('activity_name')
            points = data.get('points_claimed', 0)

            student = Student.objects.get(register_number=reg_num)

            ActivityPointLog.objects.create(
                student=student,
                activity_name=activity,
                points_claimed=points,
                verified=True
            )

            student.ktu_activity_points += points
            student.save()

            return JsonResponse({
                "status": "success",
                "message": "Points updated successfully",
                "total_points": student.ktu_activity_points
            }, status=201)

        except Student.DoesNotExist:
            return JsonResponse({"error": "Student register number not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Only POST requests are allowed"}, status=405)