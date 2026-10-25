import os
import cv2
import json
import urllib.request
import numpy as np
import pickle
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import SVC
from keras_facenet import FaceNet

# =========================
# CONFIGURATION
# =========================
DATASET_PATH = r"E:\Attendace Monitoring Project-1\Attendace Monitoring Project\dataset1"
MODEL_SAVE_PATH = "face_recognizer.pkl"
MAPPING_SAVE_PATH = "student_mapping.json"
IMG_SIZE = 160

YUNET_MODEL_PATH = "face_detection_yunet_2023mar.onnx"
YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

# =========================
# DOWNLOAD DETECTOR IF MISSING
# =========================
if not os.path.exists(YUNET_MODEL_PATH):
    print("[INFO] Downloading YuNet ONNX face detection model...")
    urllib.request.urlretrieve(YUNET_URL, YUNET_MODEL_PATH)
    print("[INFO] Download complete.")

print("[INFO] Initializing YuNet Detector & FaceNet...")
detector = cv2.FaceDetectorYN.create(
    model=YUNET_MODEL_PATH,
    config="",
    input_size=(320, 320),
    score_threshold=0.6,
    nms_threshold=0.3,
    top_k=5000
)

embedder = FaceNet()

def extract_and_align_face(image_bgr):
    """
    Detects face using OpenCV YuNet and crops the centered facial region.
    """
    h, w, _ = image_bgr.shape
    detector.setInputSize((w, h))
    _, faces = detector.detect(image_bgr)

    if faces is None or len(faces) == 0:
        return None

    # Pick detection with the highest confidence score (index 14)
    best_face = max(faces, key=lambda f: f[14])

    box_x = int(best_face[0])
    box_y = int(best_face[1])
    box_w = int(best_face[2])
    box_h = int(best_face[3])

    # Dynamic padding to keep forehead and chin intact
    pad_x = int(box_w * 0.1)
    pad_y = int(box_h * 0.1)

    x1 = max(0, box_x - pad_x)
    y1 = max(0, box_y - pad_y)
    x2 = min(w, box_x + box_w + pad_x)
    y2 = min(h, box_y + box_h + pad_y)

    face_crop = image_bgr[y1:y2, x1:x2]
    if face_crop.size == 0:
        return None

    face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
    face_resized = cv2.resize(face_rgb, (IMG_SIZE, IMG_SIZE))
    return face_resized

# =========================
# DATASET EXTRACTION
# =========================
embeddings = []
student_labels = []
label_metadata = {}

print("\n[INFO] Extracting facial features from dataset directory...")
print("=" * 60)

for folder_name in sorted(os.listdir(DATASET_PATH)):
    person_dir = os.path.join(DATASET_PATH, folder_name)
    if not os.path.isdir(person_dir):
        continue

    student_id = folder_name
    valid_face_count = 0
    image_files = [f for f in os.listdir(person_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    print(f"--> Scanning ID: '{student_id}' ({len(image_files)} source files)... ", end="", flush=True)

    for file_name in image_files:
        file_path = os.path.join(person_dir, file_name)
        img = cv2.imread(file_path)
        if img is None:
            continue

        aligned_face = extract_and_align_face(img)
        if aligned_face is not None:
            embedding = embedder.embeddings([aligned_face])[0]

            # L2 normalization for cosine/SVM separation
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            embeddings.append(embedding)
            student_labels.append(student_id)
            valid_face_count += 1

    print(f"Captured {valid_face_count} normalized embeddings.")

print("=" * 60)

if len(embeddings) == 0:
    print("[ERROR] No valid faces detected. Check dataset directory.")
    exit()

# =========================
# ENCODING & CLASSIFIER FIT
# =========================
label_encoder = LabelEncoder()
encoded_targets = label_encoder.fit_transform(student_labels)

for class_idx, student_id in enumerate(label_encoder.classes_):
    label_metadata[int(class_idx)] = {
        "student_id": str(student_id),
        "erp_synced": True
    }

print(f"\n[INFO] Training Linear Support Vector Machine on {len(embeddings)} vectors...")
classifier = SVC(kernel="linear", probability=True, C=1.0)
classifier.fit(embeddings, encoded_targets)

# =========================
# SERIALIZATION
# =========================
with open(MODEL_SAVE_PATH, "wb") as f:
    pickle.dump({"model": classifier, "encoder": label_encoder}, f)

with open(MAPPING_SAVE_PATH, "w") as f:
    json.dump(label_metadata, f, indent=4)

print(f"[SUCCESS] Model artifact saved -> '{MODEL_SAVE_PATH}'")
print(f"[SUCCESS] ERP label mapping saved -> '{MAPPING_SAVE_PATH}'")