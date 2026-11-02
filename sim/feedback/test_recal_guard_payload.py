"""Verify the exact A payload at C's packaging boundary; never access a board."""
import ast
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import freeze_recal_guard as freeze


def load_probe(source):
    path=ROOT/'report/verification/audio-replay/guard-2026-11-02/probe_baseline.py'
    spec=importlib.util.spec_from_file_location('a_baseline_probe',path)
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    probe.ROOT=ROOT;probe.SRC=source
    return probe


class GuardPayloadTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        folder=tempfile.TemporaryDirectory(dir=ROOT/'tmp');self.addCleanup(folder.cleanup)
        self.stage=Path(folder.name)/'payload';freeze.stage(self.stage)
        self.source=self.stage/'a/hw_api.py'

    def test_source_manifest_and_all_five_arm_callbacks(self):
        meta=json.loads((self.stage/'a/product-adapter.json').read_text())
        self.assertEqual(meta['expected_identity']['helper_sha256'],freeze.HELPER)
        self.assertTrue(meta['adapter_check_allowed']);self.assertEqual(meta['blockers'],[])
        for name,digest in meta['hashes'].items():
            self.assertEqual(freeze.sha((self.stage/'a'/name).read_bytes()),digest,name)
        self.assertEqual((self.stage/'a/manifest.json').read_bytes(),freeze.blob(freeze.A,'board/audio_replay/v3-io/manifest.json'))
        tree=ast.parse(self.source.read_bytes())
        callbacks=[kw.value for node in ast.walk(tree) if isinstance(node,ast.Call)
                   for kw in node.keywords if kw.arg=='before_start']
        self.assertEqual(len(callbacks),5)
        for node in callbacks:
            self.assertIsInstance(node,ast.Lambda)
            self.assertEqual(ast.unparse(node.body),'self._arm_baseline(cancel_event)')

    def test_original_A_sequence_detects_repeated_fault_and_preserves_cancel(self):
        probe=load_probe(self.source);output=io.StringIO()
        with contextlib.redirect_stdout(output):probe.main()
        text=output.getvalue();self.assertIn('VERDICT PASS',text)
        reply=json.JSONDecoder().raw_decode(text)[0]
        self.assertFalse(reply['without_rebaseline']['new_fault_in_run']['protected'])
        self.assertTrue(reply['with_rebaseline']['new_fault_in_run']['protected'])
        self.assertTrue(reply['cancel_still_refuses'])

    def test_cached_raw_words_are_marked_and_cancel_does_not_read(self):
        probe=load_probe(self.source);hw=probe.load();mm={'control':probe.Reg(),'status':probe.Reg()}
        p=hw.create_product({'package_dir':str(self.stage/'a')})
        p._ensure_mmio=lambda **kw:mm;p.identity=lambda:{}
        mm['control'].v=1631<<16;p.poll()
        hw._MM_HOLD=1
        try:
            mm['status'].v=1<<18;mm['control'].v|=1
            cached=p.poll()
            self.assertTrue(cached['mmio_held']);self.assertEqual(cached['capture_status'],0)
            self.assertEqual(cached['control_word'],1631<<16)
        finally:hw._MM_HOLD=0
        fresh=p.poll();self.assertFalse(fresh['mmio_held'])
        self.assertEqual(fresh['capture_status'],1<<18);self.assertEqual(fresh['control_word'],(1631<<16)|1)
        cancel=threading.Event();cancel.set();baseline=p._protect_baseline
        def forbidden():raise AssertionError('cancelled arm must not read or refresh baseline')
        p._status_word=forbidden
        self.assertFalse(p._arm_baseline(cancel));self.assertEqual(p._protect_baseline,baseline)


if __name__=='__main__':unittest.main()
