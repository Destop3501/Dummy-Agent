import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent_observability.phase1_agent_host import ToolSchema, ToolParameter
from agent_observability.phase2_tracing import (
    ExecutionTraceSpan,
    SpanStatus,
    SpanType,
    ErrorPayload,
)
from agent_observability.phase3_observer import (
    EvaluationNode,
    EvaluationVerdict,
    FailureCategory,
)


class TestPhase3ObservingAndDetectingFailures(unittest.TestCase):
    def setUp(self):
        self.weather_schema = ToolSchema(
            name="get_weather",
            description="Fetches current weather for a specified city.",
            parameters=[
                ToolParameter(name="city", type="string", required=True),
                ToolParameter(name="days", type="integer", required=False, default=1),
            ],
            expected_output_type="dict",
        )
        self.routed_failures = []
        self.node = EvaluationNode(
            tool_schemas={"get_weather": self.weather_schema},
            recovery_router=lambda verdict, span: self.routed_failures.append((verdict, span)),
        )

    def test_missing_parameter_detection(self):
        # Missing required parameter "city"
        span = ExecutionTraceSpan(
            span_type=SpanType.TOOL,
            name="get_weather",
            inputs={"days": 3},  # missing "city"
            outputs={"temp": 72},
            status=SpanStatus.SUCCESS,
        )

        verdict = self.node.ingest_trace(span)
        self.assertFalse(verdict.is_valid)
        self.assertEqual(verdict.failure_category, FailureCategory.MISSING_PARAMETERS)
        self.assertIn("Missing required parameter: city", verdict.deviations)
        self.assertEqual(len(self.routed_failures), 1)

    def test_type_mismatch_detection(self):
        # "city" should be string, but integer passed
        span = ExecutionTraceSpan(
            span_type=SpanType.TOOL,
            name="get_weather",
            inputs={"city": 12345, "days": 1},
            outputs={"temp": 72},
            status=SpanStatus.SUCCESS,
        )

        verdict = self.node.ingest_trace(span)
        self.assertFalse(verdict.is_valid)
        self.assertEqual(verdict.failure_category, FailureCategory.TYPE_MISMATCH)
        self.assertTrue(any("expected type 'string'" in d for d in verdict.deviations))

    def test_syntax_error_detection_unparsed_template(self):
        # Unparsed mustache template string
        span = ExecutionTraceSpan(
            span_type=SpanType.TOOL,
            name="get_weather",
            inputs={"city": "{{fetch_api.output.city_name}}", "days": 1},
            outputs={"temp": 72},
            status=SpanStatus.SUCCESS,
        )

        verdict = self.node.ingest_trace(span)
        self.assertFalse(verdict.is_valid)
        self.assertEqual(verdict.failure_category, FailureCategory.SYNTAX_ERROR)
        self.assertTrue(any("unparsed template" in d for d in verdict.deviations))

    def test_api_rejection_detection_from_status_code(self):
        # Output contains HTTP 404 error response
        span = ExecutionTraceSpan(
            span_type=SpanType.TOOL,
            name="get_weather",
            inputs={"city": "San Francisco", "days": 1},
            outputs={"status_code": 404, "error": "Endpoint not found"},
            status=SpanStatus.SUCCESS,
        )

        verdict = self.node.ingest_trace(span)
        self.assertFalse(verdict.is_valid)
        self.assertEqual(verdict.failure_category, FailureCategory.API_REJECTION)
        self.assertTrue(any("HTTP 404" in d for d in verdict.deviations))
        self.assertEqual(len(self.routed_failures), 1)

    def test_api_rejection_detection_from_exception(self):
        # Exception was caught with 404 in message
        span = ExecutionTraceSpan(
            span_type=SpanType.TOOL,
            name="get_weather",
            inputs={"city": "San Francisco"},
            status=SpanStatus.FAILED,
            error=ErrorPayload(
                error_type="HTTPError",
                message="404 Client Error: Not Found for url: https://api.weather.com/data",
                stack_trace="Traceback ... in requests.get",
            ),
        )

        verdict = self.node.ingest_trace(span)
        self.assertFalse(verdict.is_valid)
        self.assertEqual(verdict.failure_category, FailureCategory.API_REJECTION)
        self.assertEqual(len(self.routed_failures), 1)

    def test_clean_trace_passes_and_not_routed_to_recovery(self):
        span = ExecutionTraceSpan(
            span_type=SpanType.TOOL,
            name="get_weather",
            inputs={"city": "San Francisco", "days": 2},
            outputs={"temp": 68, "condition": "sunny"},
            status=SpanStatus.SUCCESS,
        )

        verdict = self.node.ingest_trace(span)
        self.assertTrue(verdict.is_valid)
        self.assertIsNone(verdict.failure_category)
        self.assertEqual(len(self.routed_failures), 0)


if __name__ == "__main__":
    unittest.main()
