import easyocr
import re
import requests
import json

# Initialize EasyOCR reader for English
reader = easyocr.Reader(['en'])

def extract_ktu_points(image_path):
    # Step 1: Perform OCR on the certificate image
    results = reader.readtext(image_path, detail=0)
    text_content = " ".join(results)
    print("\n--- Extracted Text from Certificate ---")
    print(text_content)

    # Step 2: Rule-based point assignment logic
    text_lower = text_content.lower()
    points = 0
    activity_name = "Generic Activity Certificate"

    if "nptel" in text_lower or "swayam" in text_lower:
        activity_name = "NPTEL / SWAYAM Online Course"
        points = 50
    elif "hackathon" in text_lower or "winner" in text_lower:
        activity_name = "Hackathon Winner / Project Competition"
        points = 30
    elif "workshop" in text_lower or "participation" in text_lower:
        activity_name = "Technical Workshop / Seminar"
        points = 10
    elif "sports" in text_lower or "event" in text_lower:
        activity_name = "Sports / Cultural Participation"
        points = 15

    print(f"\n[DETECTED] Activity: {activity_name} | Points: {points}")
    return activity_name, points

def send_points_to_erp(register_number, activity_name, points):
    # Step 3: Transmit data to Django API Endpoint
    api_url = "http://127.0.0.1:8000/api/activity-points/add/"
    payload = {
        "register_number": register_number,
        "activity_name": activity_name,
        "points_claimed": points
    }

    try:
        response = requests.post(api_url, json=payload)
        if response.status_code == 200 or response.status_code == 201:
            print("Successfully updated KTU Activity Points in ERP!")
        else:
            print(f"Failed to update ERP. Server returned: {response.status_code}")
    except Exception as e:
        print(f"Error connecting to Django server: {e}")

if __name__ == "__main__":
    # Test with a sample certificate image and student register number
    sample_cert_image = "sample_certificate.jpg"
    student_reg_no = "GIK23AIM006"

    activity, pts = extract_ktu_points(sample_cert_image)
    if pts > 0:
        send_points_to_erp(student_reg_no, activity, pts)