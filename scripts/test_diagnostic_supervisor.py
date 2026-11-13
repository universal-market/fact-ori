"""Actual local child faults; scaled caps are diagnostics, not 600s load proof."""
import json
import sys
import unittest
import tempfile
from pathlib import Path
from diagnostic_supervisor import supervise

PHASES = [('startup', .2), ('capital-paraphrase', .2), ('unknown-no-consent', .2)]
EVENTS = '\n'.join('print('+repr(json.dumps({'event':'phase_complete','phase':n}))+',flush=True)' for n,_ in PHASES)

class SupervisorTests(unittest.TestCase):
    def run_child(self, source, **kw):
        args = dict(total_seconds=1.2, cleanup_seconds=.2, exit_seconds=.1)
        args.update(kw)
        r = supervise([sys.executable, '-B', '-c', source], PHASES, **args)
        self.assertTrue(r['leader_reaped'])
        self.assertTrue(r['within_total_deadline'])
        return r

    def test_success(self):
        r=self.run_child(EVENTS);self.assertEqual(r['status'],'success')
        self.assertEqual(r['completed_phases'],[n for n,_ in PHASES])

    def test_startup_hang(self):
        r=self.run_child('import time;time.sleep(20)');self.assertEqual(r['status'],'phase_timeout')
        self.assertEqual(r['completed_phases'],[]);self.assertTrue(r['kill_signal_sent'])

    def test_case_hang_retains_partial(self):
        r=self.run_child(EVENTS.splitlines()[0]+'\nimport time;time.sleep(20)')
        self.assertEqual(r['status'],'phase_timeout');self.assertEqual(r['completed_phases'],['startup'])

    def test_child_cannot_restart_phase(self):
        r=self.run_child(EVENTS.splitlines()[0]+'\n'+EVENTS.splitlines()[0])
        self.assertEqual(r['status'],'invalid_event');self.assertEqual(r['completed_phases'],['startup'])

    def test_outer_cap_overrides_phase(self):
        r=self.run_child('import time;time.sleep(20)',total_seconds=.3,cleanup_seconds=.15)
        self.assertEqual(r['status'],'total_timeout')

    def test_completed_but_hung_exit(self):
        r=self.run_child(EVENTS+'\nimport time;time.sleep(20)');self.assertEqual(r['status'],'exit_timeout')

    def test_nonzero_not_success(self):
        r=self.run_child(EVENTS+'\nraise SystemExit(7)');self.assertEqual(r['status'],'child_failed')

    def test_incomplete_not_success(self):
        r=self.run_child(EVENTS.splitlines()[0]);self.assertEqual(r['status'],'incomplete')

    def test_child_text_is_not_published(self):
        marker='PRIVATE_TEST_MARKER'
        r=self.run_child('import sys;print('+repr(marker)+',file=sys.stderr)\n'+EVENTS)
        self.assertEqual(r['status'],'success');self.assertNotIn(marker,json.dumps(r))
        self.assertGreater(r['output']['stderr']['observed_bytes'],0)

    def test_output_flood_bounded(self):
        r=self.run_child('import sys;sys.stderr.write("x"*100000);sys.stderr.flush()',output_limit=128)
        self.assertEqual(r['status'],'output_limit');self.assertLessEqual(r['output']['stderr']['observed_bytes'],4096)

    def test_extra_payload_rejected(self):
        r=self.run_child('print(\'{"event":"phase_complete","phase":"startup","answer":"secret"}\',flush=True)')
        self.assertEqual(r['status'],'invalid_event');self.assertNotIn('secret',json.dumps(r))

    @unittest.skipUnless(sys.platform == 'linux', 'Linux process-state observation')
    def test_descendant_in_owned_group_stopped(self):
        with tempfile.TemporaryDirectory() as directory:
            pidfile=Path(directory)/'descendant.pid'
            descendant='import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(20)'
            source=('import subprocess,sys,time;from pathlib import Path;'
                    'p=subprocess.Popen([sys.executable,"-B","-c",'+repr(descendant)+']);'
                    'Path('+repr(str(pidfile))+').write_text(str(p.pid));time.sleep(20)')
            r=self.run_child(source)
            self.assertEqual(r['status'],'phase_timeout')
            pid=int(pidfile.read_text())
            stat=Path('/proc')/str(pid)/'stat'
            # A zombie awaits its OS reaper; it is not a running descendant.
            if stat.exists():self.assertIn(stat.read_text().split(') ')[1][0],['Z','X'])

    def test_invalid_limits_no_child(self):
        for total in [0,float('nan'),float('inf'),True]:
            with self.subTest(total=total),self.assertRaises(ValueError):
                supervise(['does-not-run'],PHASES,total_seconds=total)

if __name__=='__main__':unittest.main()
