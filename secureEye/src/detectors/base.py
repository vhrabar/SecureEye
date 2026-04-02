class FaceDetector:
    """
    Interface for face detection
    """

    def detect(self, frame):
        """
        Returns list of bounding boxes
        """
        raise NotImplementedError

    def encode(self, frame, face_box):
        """
        Returns face encoding vector
        """
        raise NotImplementedError
