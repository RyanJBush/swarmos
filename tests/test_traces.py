from swarmos.controller import BoundedController, Operation, Role
from swarmos.run_history import RunHistory
from swarmos.evidence import payload
from swarmos.timeline import render


def test_trace_records_rejected_attempt_and_successful_prefix():
    result = BoundedController().run([Operation(Role.PLANNER, 'inspect_workspace'),
                                     Operation(Role.PLANNER, 'run_tests')])
    assert [t['status'] for t in result.traces] == ['succeeded', 'rejected', 'unauthorized_tool']
    assert result.traces[1]['tool'] == 'run_tests'
    assert result.traces[0]['duration_ms'] >= 0
    assert len(result.steps) == 1


def test_timeline_escapes_untrusted_details(tmp_path):
    result = BoundedController().run([Operation(Role.PLANNER, '<script>alert(1)</script>')])
    with RunHistory(tmp_path / 'db') as h:
        run = h.start()
        h.finish(run, result, payload(run, result))
        page = render(h, run.id, tmp_path).read_text()
        assert '<script>' not in page
        assert '&lt;script&gt;' in page
        assert 'unauthorized_tool' in page
