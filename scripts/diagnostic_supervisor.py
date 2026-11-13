"""Offline POSIX child supervisor component. No Docker/model/production entry point.

Trusted caller supplies argv and fixed ordered phases. Child completion events are
untrusted timing signals, never evidence that a model result is correct.
"""
import hashlib
import json
import math
import os
import selectors
import signal
import subprocess
import time


def supervise(argv, phases, *, total_seconds=600, cleanup_seconds=2,
              exit_seconds=1, output_limit=65536):
    """Return bounded metadata only; never publish child stdout/stderr/error text."""
    phases = tuple(phases)
    durations = [total_seconds, cleanup_seconds, exit_seconds] + [s for _, s in phases]
    if (os.name != 'posix' or not phases or
            any(not isinstance(n, str) or not n or len(n) > 80 for n, _ in phases) or
            len({n for n, _ in phases}) != len(phases) or
            any(not isinstance(s, (int, float)) or isinstance(s, bool) or
                not math.isfinite(s) or s <= 0 for s in durations) or
            cleanup_seconds >= total_seconds or
            not isinstance(output_limit, int) or output_limit < 128):
        raise ValueError('Invalid supervisor limits')
    started = time.monotonic()
    outer = started + total_seconds
    work_end = outer - cleanup_seconds
    phase_end = min(work_end, started + phases[0][1])
    receipt = {'schema_version': 1, 'status': 'failed', 'completed_phases': [],
               'raw_output_published': False, 'cleanup_scope': 'own child process group only'}
    hashes = {k: hashlib.sha256() for k in ('stdout', 'stderr')}
    sizes = {k: 0 for k in hashes}
    pending = b''
    index = 0
    child = None
    selector = selectors.DefaultSelector()
    try:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 start_new_session=True, close_fds=True)
        for name in hashes:
            pipe = getattr(child, name)
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        while selector.get_map():
            now = time.monotonic()
            if now >= work_end:
                receipt['status'] = 'total_timeout'
                break
            if now >= phase_end:
                receipt['status'] = 'phase_timeout' if index < len(phases) else 'exit_timeout'
                break
            events = selector.select(min(work_end, phase_end) - now)
            for key, _ in events:
                data = os.read(key.fileobj.fileno(), 4096)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                name = key.data
                sizes[name] += len(data)
                hashes[name].update(data)
                if sum(sizes.values()) > output_limit:
                    receipt['status'] = 'output_limit'
                    raise _Stop
                if name == 'stderr':
                    continue
                pending += data
                if len(pending) > 4096:
                    receipt['status'] = 'invalid_event'
                    raise _Stop
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    try:
                        event = json.loads(line)
                    except (ValueError, UnicodeDecodeError):
                        receipt['status'] = 'invalid_event'
                        raise _Stop
                    if (index >= len(phases) or event != {
                            'event': 'phase_complete', 'phase': phases[index][0]}):
                        receipt['status'] = 'invalid_event'
                        raise _Stop
                    # Ordered, one-time transitions: child cannot reset a phase.
                    now = time.monotonic()
                    if now >= work_end or now >= phase_end:
                        receipt['status'] = 'total_timeout' if now >= work_end else 'phase_timeout'
                        raise _Stop
                    receipt['completed_phases'].append(phases[index][0])
                    index += 1
                    phase_end = min(work_end, now + (
                        phases[index][1] if index < len(phases) else exit_seconds))
        else:
            remaining = min(work_end, phase_end) - time.monotonic()
            if remaining <= 0:
                receipt['status'] = 'total_timeout' if time.monotonic() >= work_end else 'phase_timeout'
            else:
                try:
                    code = child.wait(timeout=remaining)
                    receipt['status'] = ('success' if code == 0 and index == len(phases)
                                         and not pending else 'incomplete' if code == 0 else 'child_failed')
                except subprocess.TimeoutExpired:
                    receipt['status'] = 'total_timeout' if time.monotonic() >= work_end else 'exit_timeout'
    except _Stop:
        pass
    except (OSError, ValueError):
        receipt['status'] = 'supervisor_error'
    finally:
        selector.close()
        receipt['kill_signal_sent'] = False
        if child is not None:
            # PGID is created by this Popen; no caller-supplied PID or resource names.
            try:
                os.killpg(child.pid, signal.SIGKILL)
                receipt['kill_signal_sent'] = True
            except ProcessLookupError:
                pass
            except OSError:
                receipt['status'] = 'cleanup_failed'
            try:
                child.wait(timeout=max(0.001, outer - time.monotonic()))
                receipt['leader_reaped'] = True
            except subprocess.TimeoutExpired:
                receipt['leader_reaped'] = False
                receipt['status'] = 'cleanup_failed'
            for name in hashes:
                getattr(child, name).close()
        else:
            receipt['leader_reaped'] = None
        receipt['output'] = {k: {'observed_bytes': sizes[k], 'observed_sha256': hashes[k].hexdigest()}
                             for k in hashes}
        receipt['within_total_deadline'] = time.monotonic() <= outer
        if not receipt['within_total_deadline']:
            receipt['status'] = 'cleanup_deadline_exceeded'
    return receipt


class _Stop(Exception):
    pass
