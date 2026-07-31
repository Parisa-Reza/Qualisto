from unittest.mock import Mock
from django.test import SimpleTestCase
from evaluator.evaluators.prompt_alignment import PromptAlignmentEvaluator, PromptAlignmentLLMResult
from evaluator.extractor.schemas import Heading, Image, Link, WebsiteContent


class PromptAlignmentEvaluatorTest(SimpleTestCase):
    def create_content(self):
        return WebsiteContent(url="https://example.com", title="Bali Travel Guide", meta_description="Complete Bali travel information.", headings=Heading(h1=["Bali Travel Guide"], h2=["Beaches", "Hotels", "Food"]), paragraphs=["Bali has beautiful beaches and hotels."], links=[Link(text="Hotels", href="/hotels")], images=[Image(src="/bali.jpg", alt="Bali Beach")], plain_text="Bali has beautiful beaches, hotels and food.", soup=Mock())

    def create_llm(self, response):
        llm = Mock()
        structured_llm = Mock()
        structured_llm.invoke.return_value = response
        llm.with_structured_output.return_value = structured_llm
        return llm

    def test_fully_aligned_content(self):
        evaluator = PromptAlignmentEvaluator(self.create_llm(PromptAlignmentLLMResult(score=100)))
        result = evaluator.evaluate("Create a Bali travel guide covering beaches, hotels and food.", self.create_content())
        self.assertEqual(result.score, 100)
        self.assertEqual(result.issues, [])
        self.assertEqual(result.recommendations, [])

    def test_missing_requirement(self):
        evaluator = PromptAlignmentEvaluator(self.create_llm(PromptAlignmentLLMResult(score=75, missing_requirements=["Local food"], issues=["Local food is not sufficiently covered."], suggestions=["Add a section about local food."])))
        result = evaluator.evaluate("Create a Bali travel guide covering beaches, hotels and food.", self.create_content())
        self.assertEqual(result.score, 75)
        self.assertEqual(result.missing_requirements, ["Local food"])
        self.assertEqual(result.off_topic_sections, [])
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(len(result.recommendations), 1)

    def test_off_topic_content(self):
        evaluator = PromptAlignmentEvaluator(self.create_llm(PromptAlignmentLLMResult(score=70, off_topic_sections=["US Immigration"], issues=["US immigration is unrelated to Bali travel."], suggestions=["Remove unrelated immigration content."])))
        result = evaluator.evaluate("Create a Bali travel guide.", self.create_content())
        self.assertEqual(result.score, 70)
        self.assertEqual(result.missing_requirements, [])
        self.assertEqual(result.off_topic_sections, ["US Immigration"])

    def test_llm_called(self):
        llm = self.create_llm(PromptAlignmentLLMResult(score=95))
        evaluator = PromptAlignmentEvaluator(llm)
        evaluator.evaluate("Create a Bali travel guide.", self.create_content())
        llm.with_structured_output.assert_called_once_with(PromptAlignmentLLMResult)