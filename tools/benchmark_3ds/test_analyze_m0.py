import unittest
from analyze_m0 import compare, summarize


def sample(tick, racers=30):
    return dict(tick=str(tick), mode="1", course="0", racers=str(racers),
                state_hash="01020304", rng_hash="05060708",
                update_us="1000", draw_us="2000", gfx_us="9000", tasks="1")


class AnalysisTests(unittest.TestCase):
    def test_changed_timing_does_not_count_as_state_divergence(self):
        a, b = sample(1), sample(1)
        b["gfx_us"] = "0"
        self.assertTrue(compare([a], [b])["match"])

    def test_detects_first_changed_racer_state(self):
        left = [sample(1), sample(2)]
        right = [sample(1), sample(2)]
        right[1]["state_hash"] = "deadbeef"
        result = compare(left, right)
        self.assertEqual((result["index"], result["field"]), (1, "state_hash"))

    def test_rejects_missing_frames_instead_of_matching_prefix(self):
        self.assertFalse(compare([sample(1)], [sample(1), sample(2)])["match"])

    def test_gp_summary_excludes_other_racer_counts_and_converts_units(self):
        result = summarize([sample(1), sample(2, racers=1)])
        self.assertEqual(result["gp_30_racers"]["samples"], 1)
        self.assertEqual(result["all"]["update_ms"]["mean"], 1)

    def test_detailed_fingerprint_localizes_motion_divergence(self):
        a, b = sample(1), sample(1)
        a["position_hash"], b["position_hash"] = "00000000", "00000001"
        self.assertEqual(compare([a], [b])["field"], "position_hash")

    def test_different_capture_schemas_fail_explicitly(self):
        a, b = sample(1), sample(1)
        a["position_hash"] = "00000000"
        self.assertEqual(compare([a], [b])["reason"], "capture schemas differ")


if __name__ == "__main__":
    unittest.main()
