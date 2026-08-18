import unittest
import json
from unittest.mock import patch

import evaluator


class EvaluatorModelPriorityTests(unittest.TestCase):
    def tearDown(self):
        evaluator.MODEL_COOLDOWNS.clear()

    def test_configured_order_is_preserved_and_deduplicated(self):
        models = evaluator.get_model_priority({
            "evaluator_models": ["custom-first", "custom-second", "custom-first"],
        })

        self.assertEqual(models[:2], ["custom-first", "custom-second"])
        self.assertEqual(len(models), len(set(models)))
        self.assertIn("gemini-2.5-flash", models)

    def test_fallback_uses_list_order(self):
        attempted = []

        def fake_call(_api_key, model_name, _instruction, _prompt):
            attempted.append(model_name)
            if model_name == "first-model":
                raise RuntimeError("429 quota exceeded")
            return '{"eval_score": 42}'

        with patch.object(evaluator, "_call_gemini_single", side_effect=fake_call):
            result = evaluator._call_gemini(
                "key",
                ["first-model", "second-model"],
                "instruction",
                ["prompt"],
            )

        self.assertEqual(attempted, ["first-model", "second-model"])
        self.assertEqual(result, '{"eval_score": 42}')

    def test_unavailable_model_is_skipped_until_cooldown_expires(self):
        attempted = []

        def fake_call(_api_key, model_name, _instruction, _prompt):
            attempted.append(model_name)
            if model_name == "unavailable-model":
                raise RuntimeError("404 model not found")
            return '{"eval_score": 42}'

        with patch.object(evaluator, "_call_gemini_single", side_effect=fake_call):
            evaluator._call_gemini(
                "key",
                ["unavailable-model", "working-model"],
                "instruction",
                ["prompt"],
                model_cooldown_s=60,
            )
            evaluator._call_gemini(
                "key",
                ["unavailable-model", "working-model"],
                "instruction",
                ["prompt"],
                model_cooldown_s=60,
            )

        self.assertEqual(attempted, ["unavailable-model", "working-model", "working-model"])

    def test_evaluation_update_event_is_json_safe_for_url_links(self):
        messages = []
        job = {
            "link": "https://example.test/job?id=123:abc",
            "title": "Test job",
            "company": "Test company",
            "description": "Description",
        }
        response = json.dumps({
            "eval_score": 85,
            "eval_reason": "Good match",
            "selected_cv": "cv.pdf",
            "cover_letter": "Hallo\nWelt",
        })

        with patch.object(evaluator, "_call_gemini", return_value=response), \
             patch.object(evaluator.database, "update_job_eval"), \
             patch.object(evaluator, "emit_log", side_effect=lambda message, *_: messages.append(message)):
            result = evaluator.evaluate_job_data(
                job,
                "key",
                ["working-model"],
                "instruction",
                [],
            )

        event = next(message for message in messages if message.startswith("EVAL_UPDATE:"))
        payload = json.loads(event.split(":", 1)[1])
        self.assertEqual(payload["link"], job["link"])
        self.assertEqual(payload["eval_score"], result["eval_score"])
        self.assertEqual(payload["cover_letter"], "Hallo\nWelt")


if __name__ == "__main__":
    unittest.main()
