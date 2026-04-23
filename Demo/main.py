import time
import cv2
import mediapipe as mp

from core.draw_mediapipe import draw_scene, load_violin_profile_safe
from core.models.mediapipe_holistic_state import HolisticState


def main() -> None:
    mp_holistic = mp.solutions.holistic
    violin_profile = load_violin_profile_safe("config/instrument_profiles.unity.json")

    capture = cv2.VideoCapture(0)
    if not capture.isOpened():
        raise RuntimeError("Could not open camera 0")
    showing_image = True
    # showing_image = False
    image = cv2.imread("images/image.png")
    try:
        with mp_holistic.Holistic(
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        ) as holistic:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if showing_image:
                    frame = cv2.resize(image, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_AREA)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = holistic.process(rgb_frame)
                state = HolisticState.from_mediapipe_results(results, timestamp=time.time())
                draw_scene(frame, state, violin_profile=violin_profile)

                status = f"pose={len(state.pose or [])} left={len(state.left_hand or [])} right={len(state.right_hand or [])}"
                cv2.putText(frame, status, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                # resized_frame = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA)
                # cv2.imshow("Holistic Tracking", resized_frame)
                cv2.imshow("Holistic Tracking", frame)

                if showing_image:
                    cv2.waitKey(0)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
