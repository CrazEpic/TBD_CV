import cv2
import numpy as np
import socket
import struct
from mediapipe.python.solutions import drawing_utils, drawing_styles, holistic


# NETWORK CONFIGS
UDP_IP = "127.0.0.1"
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


# For webcam input:
cap = cv2.VideoCapture(0)
with holistic.Holistic(
    min_detection_confidence=0.5, min_tracking_confidence=0.5
) as holistic_var:
    while cap.isOpened():
        success, image = cap.read()
        if not success:
            print("Ignoring empty camera frame.")
            # If loading a video, use 'break' instead of 'continue'.
            continue

        # To improve performance, optionally mark the image as not writeable to
        # pass by reference.
        image.flags.writeable = False
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = holistic_var.process(image)

        # Draw landmark annotation on the image.
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        drawing_utils.draw_landmarks(
            image,
            results.face_landmarks,
            holistic.FACEMESH_CONTOURS,
            landmark_drawing_spec=None,
            connection_drawing_spec=drawing_styles.get_default_face_mesh_contours_style(),
        )
        drawing_utils.draw_landmarks(
            image,
            results.left_hand_landmarks,
            holistic.HAND_CONNECTIONS,
            landmark_drawing_spec=drawing_styles.get_default_hand_landmarks_style(),
            connection_drawing_spec=drawing_styles.get_default_hand_connections_style(),
        )
        drawing_utils.draw_landmarks(
            image,
            results.right_hand_landmarks,
            holistic.HAND_CONNECTIONS,
            landmark_drawing_spec=drawing_styles.get_default_hand_landmarks_style(),
            connection_drawing_spec=drawing_styles.get_default_hand_connections_style(),
        )
        drawing_utils.draw_landmarks(
            image,
            results.pose_landmarks,
            holistic.POSE_CONNECTIONS,
            landmark_drawing_spec=drawing_styles.get_default_pose_landmarks_style(),
        )

        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            # landmarks = results.pose_world_landmarks.landmark
            joints = [[lm.x, lm.y, lm.z, lm.visibility] for lm in landmarks]
            
            joints_array = np.array(joints, dtype=np.float32)
            data_flat = joints_array.flatten()

            data_bytes = struct.pack(f'{len(data_flat)}f', *data_flat)
            sock.sendto(data_bytes, (UDP_IP, UDP_PORT))

        # Flip the image horizontally for a selfie-view display.
        cv2.imshow("MediaPipe Holistic", cv2.flip(image, 1))
        if cv2.waitKey(5) & 0xFF == 27:
            break

cap.release()
