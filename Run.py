import os
import cv2
import json
import urllib.request
import numpy as np
import pickle
import time
from datetime import datetime
from keras_facenet import FaceNet

# =========================
# CONFIGURATION
# =========================
IMG_SIZE = 160
CONFIDENCE_THRESHOLD = 0.55
SESSION_DURATION_SECONDS = 180   # 3-minute capture window
REQUIRED_SEEN_SECONDS = 2.0      # Required visibility duration to mark present
GRACE_PERIOD = 1.0

MODEL_FILE = "face_recognizer.pkl"
MAPPING_FILE = "student_mapping.json"
YUNET_MODEL_PATH = "face_detection_yunet_2023mar.onnx"
YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

# =========================
# DOWNLOAD YUNET IF MISSING
# =========================
if not os.path.exists(YUNET_MODEL_PATH):
    print("[INFO] Downloading YuNet ONNX face detection model...")
    urllib.request.urlretrieve(YUNET_URL, YUNET_MODEL_PATH)
    print("[INFO] Model downloaded successfully.")

# =========================
# LOAD MODELS & REGISTRY
# =========================
print("[INFO] Loading trained recognition artifacts...")
with open(MODEL_FILE, "rb") as f:
    saved_data = pickle.load(f)
    model = saved_data["model"]
    le = saved_data["encoder"]

embedder = FaceNet()

detector = cv2.FaceDetectorYN.create(
    model=YUNET_MODEL_PATH,
    config="",
    input_size=(320, 320),
    score_threshold=0.6,
    nms_threshold=0.3,
    top_k=5000
)

# =========================
# HELPER FUNCTIONS
# =========================
def evaluate_affect_and_liveness(face_meta):
    """
    face_meta contains: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rcm, y_rcm, x_lcm, y_lcm, score]
    Uses 5 facial landmarks (eyes, nose, mouth corners) to assess pose and attention.
    """
    re_x, re_y = face_meta[4], face_meta[5]
    le_x, le_y = face_meta[6], face_meta[7]
    nose_x, nose_y = face_meta[8], face_meta[9]

    # Inter-pupillary distance
    eye_dist = np.hypot(le_x - re_x, le_y - re_y)
    eye_center_x = (re_x + le_x) / 2.0

    # Yaw deviation: distance from nose tip to eye center
    yaw_offset = abs(nose_x - eye_center_x) / (eye_dist + 1e-6)

    # Affect scoring
    if yaw_offset > 0.40:
        affect = "Non-Attentive"  # Head turned away
    elif yaw_offset < 0.15:
        affect = "Attentive"      # Directly facing camera/board
    else:
        affect = "Neutral"

    return affect, eye_dist

# =========================
# SESSION TRACKING SETUP
# =========================
master_students = list(le.classes_)
attendance_record = {
    sid: {
        "status": "Absent",
        "time": "-",
        "liveness_verified": False,
        "engagement_samples": []
    }
    for sid in master_students
}

verification_tracker = {
    sid: {
        "first_seen": 0.0,
        "last_seen": 0.0,
        "prev_eye_dist": 0.0,
        "motion_variance": 0.0
    }
    for sid in master_students
}

# =========================
# VIDEO PIPELINE
# =========================
cap = cv2.VideoCapture(0)
session_start_time = time.time()

print(f"[INFO] Lecture Attendance Session Started. Automated window: {SESSION_DURATION_SECONDS}s")

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_time = time.time()
        elapsed_time = current_time - session_start_time
        remaining_session = max(0, SESSION_DURATION_SECONDS - elapsed_time)

        if remaining_session <= 0:
            print("[INFO] Attendance capture window expired. Finalizing data...")
            break

        h, w, _ = frame.shape
        detector.setInputSize((w, h))
        _, faces = detector.detect(frame)

        if faces is not None:
            for face_data in faces:
                box_x, box_y = int(face_data[0]), int(face_data[1])
                box_w, box_h = int(face_data[2]), int(face_data[3])

                # 10% Dynamic padding
                pad_x, pad_y = int(box_w * 0.1), int(box_h * 0.1)
                x1, y1 = max(0, box_x - pad_x), max(0, box_y - pad_y)
                x2, y2 = min(w, box_x + box_w + pad_x), min(h, box_y + box_h + pad_y)

                face_crop = frame[y1:y2, x1:x2]
                if face_crop.size == 0:
                    continue

                affect_state, current_eye_dist = evaluate_affect_and_liveness(face_data)

                # FaceNet Embedding
                face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
                face_resized = cv2.resize(face_rgb, (IMG_SIZE, IMG_SIZE))
                embedding = embedder.embeddings([face_resized])[0]
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

                preds = model.predict_proba([embedding])[0]
                best_idx = np.argmax(preds)
                confidence = preds[best_idx]
                student_id = le.classes_[best_idx]

                if confidence < CONFIDENCE_THRESHOLD:
                    box_color = (0, 0, 255)
                    display_tag = f"Unknown ({confidence:.2f})"
                else:
                    record = attendance_record[student_id]
                    tracker = verification_tracker[student_id]

                    # Active micro-motion tracking for anti-spoofing
                    if tracker["prev_eye_dist"] > 0:
                        dist_delta = abs(current_eye_dist - tracker["prev_eye_dist"])
                        tracker["motion_variance"] += dist_delta
                        if tracker["motion_variance"] > 1.5:  # Confirms organic live subject movement
                            record["liveness_verified"] = True

                    tracker["prev_eye_dist"] = current_eye_dist

                    # Only accumulate engagement history once marked present
                    if record["status"] == "Present":
                        record["engagement_samples"].append(affect_state)
                        box_color = (0, 255, 0)
                        display_tag = f"{student_id} | {affect_state}"
                    else:
                        if tracker["first_seen"] == 0.0:
                            tracker["first_seen"] = current_time
                            tracker["last_seen"] = current_time
                        else:
                            if (current_time - tracker["last_seen"]) > GRACE_PERIOD:
                                tracker["first_seen"] = current_time

                            tracker["last_seen"] = current_time
                            time_visible = current_time - tracker["first_seen"]

                            # Require presence duration and active liveness verification
                            if time_visible >= REQUIRED_SEEN_SECONDS and record["liveness_verified"]:
                                log_time = datetime.now().strftime("%I:%M:%S %p")
                                record["status"] = "Present"
                                record["time"] = log_time
                                record["engagement_samples"].append(affect_state)
                                print(f" Marked {student_id} as PRESENT at {log_time}")
                                box_color = (0, 255, 0)
                                display_tag = f"{student_id} (Verified)"
                            else:
                                box_color = (0, 255, 255)
                                display_tag = f"Verifying {student_id}... Move slightly"

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, display_tag, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)

        # Header status
        cv2.putText(frame, f"Session Time Left: {int(remaining_session)}s", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        cv2.imshow("Automated Attendance & Engagement Engine", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break

finally:
    cap.release()
    try:
        cv2.destroyAllWindows()
    except cv2.error:
        pass

    date_str = datetime.now().strftime("%Y-%m-%d")
    erp_payload = {
        "session_date": date_str,
        "subject_code": "CST306",
        "subject_name": "Artificial Intelligence",
        "records": []
    }

    print("\n" + "=" * 60)
    print("SESSION COMPLETE: COMPUTING ENGAGEMENT INDICES")
    print("=" * 60)

    for sid, data in attendance_record.items():
        # Absent students have engagement metrics zeroed out
        if data["status"] != "Present":
            attentive_pct = 0.0
            neutral_pct = 0.0
            non_attentive_pct = 0.0
        else:
            samples = data["engagement_samples"]
            total_samples = len(samples)
            attentive_pct = (samples.count("Attentive") / total_samples * 100) if total_samples > 0 else 0.0
            neutral_pct = (samples.count("Neutral") / total_samples * 100) if total_samples > 0 else 0.0
            non_attentive_pct = (samples.count("Non-Attentive") / total_samples * 100) if total_samples > 0 else 0.0

        student_summary = {
            "student_id": sid,
            "status": data["status"],
            "time_logged": data["time"],
            "liveness_passed": data["liveness_verified"],
            "engagement": {
                "attentive_rate": round(attentive_pct, 2),
                "neutral_rate": round(neutral_pct, 2),
                "non_attentive_rate": round(non_attentive_pct, 2)
            }
        }
        erp_payload["records"].append(student_summary)

        print(f"-> {sid:15} | Status: {data['status']:7} | Attentive: {attentive_pct:.1f}% | Non-Attentive: {non_attentive_pct:.1f}%")

    # Local backup
    with open(f"ERP_Session_Payload_{date_str}.json", "w") as out_file:
        json.dump(erp_payload, out_file, indent=4)

    # Automated Sync to Django ERP
    ERP_API_URL = "http://127.0.0.1:8000/api/attendance/sync/"
    print(f"\n[INFO] Transmitting session records to ERP backend ({ERP_API_URL})...")

    try:
        import requests
        response = requests.post(ERP_API_URL, json=erp_payload, timeout=5)
        if response.status_code == 200:
            print(" Database synced successfully! Attendance & engagement records are live.")
        else:
            print(f"[WARNING] ERP Server returned status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[ERROR] Could not connect to Django server: {e}")