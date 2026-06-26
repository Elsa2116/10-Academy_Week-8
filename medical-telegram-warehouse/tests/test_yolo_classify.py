"""
Unit tests for the YOLO classification logic.
Tests are pure-Python and do not require a GPU or model weights.
"""

import pytest

from src.yolo_detect import classify_image


class TestClassifyImage:
    def test_promotional_person_and_bottle(self):
        assert classify_image(["person", "bottle"]) == "promotional"

    def test_promotional_person_and_cup(self):
        assert classify_image(["person", "cup", "person"]) == "promotional"

    def test_product_display_bottle_only(self):
        assert classify_image(["bottle"]) == "product_display"

    def test_product_display_bowl(self):
        assert classify_image(["bowl", "vase"]) == "product_display"

    def test_lifestyle_person_only(self):
        assert classify_image(["person"]) == "lifestyle"

    def test_other_empty(self):
        assert classify_image([]) == "other"

    def test_other_unrelated_objects(self):
        assert classify_image(["car", "bus", "traffic light"]) == "other"

    def test_case_insensitive_not_required_but_handles_lowercase(self):
        # Our YOLO model returns lowercase labels from COCO
        result = classify_image(["person", "bottle"])
        assert result == "promotional"
