from swarmos.evaluation import evaluate


def test_paired_evaluation_has_failing_baseline_and_memory_hits(tmp_path):
    path, report = evaluate(tmp_path, trials=1)
    assert path.is_file()
    assert report['unpatched_baseline']['returncode'] == 1
    assert report['summary']['off']['successes'] == 1
    assert report['summary']['on']['successes'] == 1
    assert report['summary']['off']['memory_hits'] == 0
    assert report['summary']['on']['memory_hits'] == 1
    assert report['summary']['on']['mean_steps'] == report['summary']['off']['mean_steps'] == 5
