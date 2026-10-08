import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid

from live_eval import run_live


class LiveBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / 'run'
        self.bank = Path(__file__).parent / 'cases.json'
        self.reference = Path(__file__).parent / 'annotations.json'
        self.calls = []

    def capture(self, runner, **kwargs):
        self.calls.append(kwargs)
        response = {'novelty_class': 'unclear', 'nearest_prior_work': [], 'delta_statement': 'Evidence is insufficient.',
                    'pseudo_diversity': None, 'confidence': .2, 'rationale': 'Source coverage is limited.', 'refutations': []}
        return SimpleNamespace(raw_output=json.dumps(response).encode(), run_id=str(uuid.uuid4()),
                               context_id=str(uuid.uuid4()), model_revision=kwargs['model_revision'], telemetry=None)

    def run_case(self, **kwargs):
        options = dict(model='test-model', family='test-family', max_cases=1, max_calls=2, capture_fn=self.capture)
        options.update(kwargs)
        with contextlib.redirect_stdout(io.StringIO()):
            return run_live(self.bank, self.reference, self.output, **options)

    def test_insufficient_pair_budget_makes_zero_calls(self):
        result = self.run_case(max_cases=2)
        self.assertEqual('NOT RUN', result['status'])
        self.assertEqual([], self.calls)

    def test_injected_capture_stays_synthetic_and_unknown(self):
        result = self.run_case()
        self.assertEqual('COMPLETED', result['status'])
        report = json.loads((self.output / 'evaluation.json').read_text())
        self.assertTrue(report['synthetic'])
        self.assertFalse(report['auto_promotion_eligible'])
        self.assertIsNone(report['cases'][0]['predicted_class'])
        self.assertEqual(2, len(self.calls))

    def test_failure_preserves_attempt_and_missing_order(self):
        def failed(*args, **kwargs):
            raise ValueError('host unavailable')
        result = self.run_case(capture_fn=failed)
        self.assertEqual('INCOMPLETE', result['status'])
        self.assertEqual(1, result['attempted_calls'])
        self.assertEqual(1, len(result['not_started_request_ids']))
        self.assertTrue((self.output / 'responses.json').exists())

    def test_interrupt_is_retained_as_incomplete(self):
        def interrupted(*args, **kwargs):
            raise KeyboardInterrupt()
        result = self.run_case(capture_fn=interrupted)
        self.assertEqual('INCOMPLETE', result['status'])
        self.assertEqual('KeyboardInterrupt', result['attempts'][0]['error'])

    def test_invalid_model_bytes_preserve_raw_output_and_provenance(self):
        for raw in (b'not JSON', b'\xff'):
            with self.subTest(raw=raw):
                self.output = self.output.parent / ('invalid-' + raw.hex())
                def invalid(*args, **kwargs):
                    return SimpleNamespace(raw_output=raw, run_id='actual-run', context_id='actual-context',
                                           model_revision='test-model', telemetry=None)
                result = self.run_case(capture_fn=invalid)
                self.assertEqual('INCOMPLETE', result['status'])
                self.assertEqual(raw, (self.output / 'capture-001.raw').read_bytes())
                metadata = json.loads((self.output / 'capture-001-metadata.json').read_text())
                self.assertEqual('actual-context', metadata['context_id'])

    def test_changed_reference_prevents_model_call(self):
        reference = json.loads(self.reference.read_text(encoding='utf-8'))
        reference['cases_sha256'] = '0' * 64
        self.reference = Path(self.directory.name) / 'wrong-reference.json'
        self.reference.write_text(json.dumps(reference), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'before execution'):
            self.run_case()
        self.assertEqual([], self.calls)

    def test_same_family_secondary_prevents_model_call(self):
        with self.assertRaisesRegex(ValueError, 'different model family'):
            self.run_case(secondary_model='another-model', secondary_family='test-family', secondary_runner='codex')
        self.assertEqual([], self.calls)

    def test_secondary_stays_within_total_budget_and_preserves_uncertainty(self):
        result = self.run_case(max_calls=4, secondary_model='second-model',
                               secondary_family='second-family', secondary_runner='codex')
        self.assertEqual(4, result['attempted_calls'])
        self.assertEqual(4, len(self.calls))
        report = json.loads((self.output / 'evaluation.json').read_text())
        self.assertIsNone(report['cases'][0]['predicted_class'])
        self.assertFalse(report['auto_promotion_eligible'])

    def test_failed_secondary_makes_whole_execution_incomplete(self):
        def secondary_failure(runner, **kwargs):
            if kwargs['model_revision'] == 'second-model':
                raise ValueError('secondary unavailable')
            return self.capture(runner, **kwargs)
        result = self.run_case(max_calls=4, capture_fn=secondary_failure, secondary_model='second-model',
                               secondary_family='second-family', secondary_runner='codex')
        self.assertEqual('INCOMPLETE', result['status'])
        self.assertEqual(3, result['attempted_calls'])


if __name__ == '__main__':
    unittest.main()
