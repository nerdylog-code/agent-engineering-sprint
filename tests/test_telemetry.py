import unittest

from agent_lab.telemetry import Telemetry


class TelemetryTests(unittest.TestCase):
    def test_in_memory_records_spans_and_sdk_exports(self):
        telemetry = Telemetry()
        with telemetry.span("request", {"tenant_id": "tenant-a"}), telemetry.span(
            "tool.call", {"tool": "calculator"}
        ):
            pass
        self.assertEqual([span.name for span in telemetry.records], ["tool.call", "request"])
        self.assertTrue(all(span.status == "ok" for span in telemetry.records))
        self.assertGreaterEqual(len(telemetry.finished_sdk_spans()), 2)

    def test_error_span_is_recorded_and_rethrown(self):
        telemetry = Telemetry()
        with self.assertRaises(RuntimeError), telemetry.span("failure"):
            raise RuntimeError("boom")
        self.assertEqual(telemetry.records[-1].status, "error")


if __name__ == "__main__":
    unittest.main()
