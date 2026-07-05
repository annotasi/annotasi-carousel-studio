from __future__ import annotations

import unittest

from annotasi_carousel_studio.ai.client import extract_ai_response_payload
from annotasi_carousel_studio.utils.text import extract_first_json_value, strip_json_fence


class JsonExtractionTests(unittest.TestCase):
    def test_plain_json_object(self) -> None:
        self.assertEqual(extract_first_json_value('{"title":"Test","slides":[]}')["title"], "Test")

    def test_plain_json_array(self) -> None:
        self.assertEqual(extract_first_json_value('[{"title":"Test"}]')[0]["title"], "Test")

    def test_fenced_json_block(self) -> None:
        text = '```json\n{"title":"Test","slides":[]}\n```'
        self.assertEqual(extract_first_json_value(text)["title"], "Test")

    def test_generic_fenced_block(self) -> None:
        text = '```\n{"title":"Test","slides":[]}\n```'
        self.assertEqual(strip_json_fence(text), '{"title":"Test","slides":[]}')
        self.assertEqual(extract_first_json_value(text)["title"], "Test")

    def test_leading_text(self) -> None:
        text = 'Berikut JSON-nya:\n{"title":"Test","slides":[]}'
        self.assertEqual(extract_first_json_value(text)["title"], "Test")

    def test_trailing_text(self) -> None:
        text = '{"title":"Test","slides":[]}\nSemoga membantu.'
        self.assertEqual(extract_first_json_value(text)["title"], "Test")

    def test_leading_and_trailing_text(self) -> None:
        text = 'Berikut JSON yang diminta:\n{"title":"Test","slides":[]}\nSilakan dicek.'
        self.assertEqual(extract_first_json_value(text)["title"], "Test")

    def test_braces_inside_string(self) -> None:
        text = """
        {
          "title": "Belajar sabar {bukan berarti diam}",
          "slides": [
            {"body": "Gunakan tanda { dan } sebagai teks biasa"}
          ]
        }
        """
        parsed = extract_first_json_value(text)
        self.assertIn("{bukan berarti diam}", parsed["title"])
        self.assertIn("{ dan }", parsed["slides"][0]["body"])

    def test_invalid_text_raises(self) -> None:
        with self.assertRaises(ValueError):
            extract_first_json_value("ini bukan json")

    def test_chat_completion_wrapper(self) -> None:
        envelope = {"choices": [{"message": {"content": '{"title":"Test","slides":[]}'}}]}
        payload = extract_ai_response_payload(envelope)
        self.assertEqual(extract_first_json_value(payload)["title"], "Test")

    def test_completion_text_wrapper(self) -> None:
        envelope = {"choices": [{"text": '{"title":"Test","slides":[]}'}]}
        payload = extract_ai_response_payload(envelope)
        self.assertEqual(extract_first_json_value(payload)["title"], "Test")

    def test_output_text_wrapper(self) -> None:
        envelope = {"output_text": '{"title":"Test","slides":[]}'}
        payload = extract_ai_response_payload(envelope)
        self.assertEqual(extract_first_json_value(payload)["title"], "Test")

    def test_direct_content_wrapper(self) -> None:
        envelope = {"content": '{"title":"Test","slides":[]}'}
        payload = extract_ai_response_payload(envelope)
        self.assertEqual(extract_first_json_value(payload)["title"], "Test")

    def test_already_parsed_json_object(self) -> None:
        envelope = {"title": "Test", "slides": []}
        self.assertEqual(extract_ai_response_payload(envelope)["title"], "Test")


if __name__ == "__main__":
    unittest.main()
