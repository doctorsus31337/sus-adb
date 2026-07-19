import unittest

from app.core.script_profile import FailurePolicy, ScriptProfile, ScriptStage


class ScriptProfileTests(unittest.TestCase):
    def test_order_serialization_digest_and_policy(self):
        profile = ScriptProfile("Chain", stages=(ScriptStage("a"), ScriptStage("b", failure_policy=FailurePolicy.CONTINUE)))
        self.assertEqual([item.script_id for item in profile.stages], ["a", "b"])
        self.assertEqual(profile.to_dict()["stages"][1]["failure_policy"], "continue")
        self.assertEqual(len(profile.digest), 64)
        self.assertEqual(ScriptProfile.from_dict(profile.to_dict()), profile)
    def test_negative_delay_rejected(self):
        with self.assertRaises(ValueError): ScriptStage("a", delay_seconds=-1)
