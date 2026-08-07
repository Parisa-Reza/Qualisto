from unittest.mock import patch

from django.test import SimpleTestCase

from evaluator.llm.ollama import create_ollama_model


class OllamaModelTest(SimpleTestCase):

    @patch.dict(
        "os.environ",
        {
            "OLLAMA_MODEL": "qwen3:1.7b",
            "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        },
    )
    def test_create_ollama_model(self):

        model = create_ollama_model()

        self.assertIsNotNone(model)

        self.assertEqual(
            model.model,
            "qwen3:1.7b",
        )

        self.assertEqual(
            model.temperature,
            0,
        )



# import os
# from unittest.mock import patch

# from django.test import SimpleTestCase

# from evaluator.llm.gemini import create_gemini_model


# class GeminiModelTest(SimpleTestCase):

#     @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
#     def test_create_gemini_model(self):
#         model = create_gemini_model()

#         self.assertIsNotNone(model)
#         self.assertEqual(model.model, "gemini-3.1-flash-lite")
#         self.assertEqual(model.temperature, 0)

#     @patch.dict(os.environ, {}, clear=True)
#     def test_missing_api_key(self):
#         with self.assertRaises(ValueError):
#             create_gemini_model()