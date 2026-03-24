"""Tests for MediaPipeDetector."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import numpy as np

# Path setup
src_dir = str(Path(__file__).parent.parent.parent / "secureEye" / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

sys.modules["keras"] = MagicMock()
sys.modules["keras.models"] = MagicMock()
sys.modules["mediapipe"] = MagicMock()

from detectors.mediapipe_detector import MediaPipeDetector  # noqa: E402

FRAME_480 = np.zeros((480, 640, 3), dtype=np.uint8)


def _make_detection(xmin, ymin, width, height):
    bbox = Mock(xmin=xmin, ymin=ymin, width=width, height=height)
    det = Mock()
    det.location_data.relative_bounding_box = bbox
    return det


def _bbox_to_pixels(xmin, ymin, w, h, frame):
    fh, fw = frame.shape[:2]
    return (int(xmin * fw), int(ymin * fh), int(w * fw), int(h * fh))


@patch("keras.models.load_model")
@patch("detectors.mediapipe_detector.mp")
class TestMediaPipeDetector(unittest.TestCase):

    def _make_detector(self, mock_mp, mock_load_model):
        mock_mp.solutions.face_detection.FaceDetection.return_value = Mock()
        mock_load_model.return_value = Mock()
        return MediaPipeDetector()

    # --- init ---

    def test_initialization(self, mock_mp, mock_load_model):
        # Reset mock to clear calls from module import
        mock_mp.solutions.face_detection.FaceDetection.reset_mock()

        detector = self._make_detector(mock_mp, mock_load_model)
        # Verify MediaPipe FaceDetection was configured correctly
        mock_mp.solutions.face_detection.FaceDetection.assert_called_once_with(
            model_selection=1, min_detection_confidence=0.5
        )
        # Verify detector has the required attributes
        self.assertIsNotNone(detector.facenet_model)
        self.assertIsNotNone(detector.mp_detector)

    # --- detect ---

    def test_no_faces_returns_empty(self, mock_mp, mock_load_model):
        detector = self._make_detector(mock_mp, mock_load_model)
        detector.mp_detector.process.return_value = Mock(detections=None)

        self.assertEqual(detector.detect(FRAME_480), [])

    def test_single_face(self, mock_mp, mock_load_model):
        detector = self._make_detector(mock_mp, mock_load_model)
        coords = (0.1, 0.1, 0.2, 0.3)
        detector.mp_detector.process.return_value = Mock(
            detections=[_make_detection(*coords)]
        )

        result = detector.detect(FRAME_480)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], _bbox_to_pixels(*coords, FRAME_480))

    def test_multiple_faces(self, mock_mp, mock_load_model):
        detector = self._make_detector(mock_mp, mock_load_model)
        all_coords = [(0.1, 0.1, 0.2, 0.3), (0.5, 0.4, 0.2, 0.3)]
        detector.mp_detector.process.return_value = Mock(
            detections=[_make_detection(*c) for c in all_coords]
        )

        result = detector.detect(FRAME_480)

        self.assertEqual(len(result), 2)
        for i, coords in enumerate(all_coords):
            self.assertEqual(result[i], _bbox_to_pixels(*coords, FRAME_480))

    def test_face_at_origin(self, mock_mp, mock_load_model):
        detector = self._make_detector(mock_mp, mock_load_model)
        detector.mp_detector.process.return_value = Mock(
            detections=[_make_detection(0.0, 0.0, 0.1, 0.1)]
        )

        result = detector.detect(FRAME_480)

        self.assertEqual(result[0][:2], (0, 0))

    def test_detect_result_types(self, mock_mp, mock_load_model):
        detector = self._make_detector(mock_mp, mock_load_model)
        detector.mp_detector.process.return_value = Mock(
            detections=[_make_detection(0.1, 0.2, 0.3, 0.4)]
        )

        result = detector.detect(FRAME_480)

        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], tuple)
        self.assertTrue(all(isinstance(v, int) for v in result[0]))

    def test_detect_scales_with_frame_size(self, mock_mp, mock_load_model):
        detector = self._make_detector(mock_mp, mock_load_model)
        coords = (0.25, 0.25, 0.5, 0.5)

        for h, w in [(480, 640), (720, 1280), (1080, 1920)]:
            with self.subTest(size=(h, w)):
                frame = np.zeros((h, w, 3), dtype=np.uint8)
                detector.mp_detector.process.return_value = Mock(
                    detections=[_make_detection(*coords)]
                )
                result = detector.detect(frame)
                self.assertEqual(result[0], _bbox_to_pixels(*coords, frame))

    # --- encode ---

    @patch("detectors.mediapipe_detector.preprocess_face")
    def test_encode_output_shape(self, mock_preprocess, mock_mp, mock_load_model):
        detector = self._make_detector(mock_mp, mock_load_model)
        mock_preprocess.return_value = np.zeros((1, 160, 160, 3), dtype=np.float32)
        detector.facenet_model.predict.return_value = np.zeros((1, 128))

        result = detector.encode(FRAME_480, (100, 100, 150, 150))

        self.assertEqual(result.shape, (128,))
        self.assertIsInstance(result, np.ndarray)

    @patch("detectors.mediapipe_detector.cv2.cvtColor")
    @patch("detectors.mediapipe_detector.preprocess_face")
    def test_encode_crops_correct_region(self, mock_preprocess, mock_cvtColor, mock_mp, mock_load_model):
        detector = self._make_detector(mock_mp, mock_load_model)
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 100

        # Make cvtColor return the right shape (same as input but with conversion applied)
        def cvtColor_side_effect(img, code):
            # Just return a modified version to simulate color conversion
            return np.ones_like(img)

        mock_cvtColor.side_effect = cvtColor_side_effect
        mock_preprocess.return_value = np.zeros((1, 160, 160, 3), dtype=np.float32)
        detector.facenet_model.predict.return_value = np.zeros((1, 128))

        detector.encode(frame, (100, 100, 150, 150))

        # Verify cvtColor was called
        mock_cvtColor.assert_called()
        # Check the first call (should be with the cropped region)
        first_call_arg = mock_cvtColor.call_args_list[0][0][0]
        self.assertEqual(first_call_arg.shape, (150, 150, 3))
        np.testing.assert_array_equal(first_call_arg, frame[100:250, 100:250])

    @patch("detectors.mediapipe_detector.cv2.cvtColor")
    @patch("detectors.mediapipe_detector.preprocess_face")
    def test_encode_converts_bgr_to_rgb(self, mock_preprocess, mock_cvtColor, mock_mp, mock_load_model):
        detector = self._make_detector(mock_mp, mock_load_model)
        mock_cvtColor.return_value = np.zeros((150, 150, 3), dtype=np.uint8)
        mock_preprocess.return_value = np.zeros((1, 160, 160, 3), dtype=np.float32)
        detector.facenet_model.predict.return_value = np.zeros((1, 128))

        detector.encode(FRAME_480, (100, 100, 150, 150))

        # Verify cvtColor was called at least once with the correct color conversion flag
        mock_cvtColor.assert_called()
        # Find the call with the color conversion flag
        found_bgr_to_rgb = False
        for call in mock_cvtColor.call_args_list:
            if call[0][1] == 4:  # cv2.COLOR_BGR2RGB = 4
                found_bgr_to_rgb = True
                break
        self.assertTrue(found_bgr_to_rgb, "BGR to RGB conversion was not found in cvtColor calls")


if __name__ == "__main__":
    unittest.main()
