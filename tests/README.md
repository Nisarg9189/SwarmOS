# Tests & Benchmarks

Automated test suite and performance benchmarking.

## Structure

- `collision_checker.py` — Detect collisions in simulation log (to be implemented)
- `test_collision_avoidance.py` — Unit test for collision detection (to be implemented)
- `test_deadlock_recovery.py` — Unit test for deadlock resolution (to be implemented)
- `test_task_assignment.py` — Unit test for task claiming (to be implemented)
- `benchmark_runner.py` — Main benchmark harness (to be implemented)
- `baseline_stop_wait.py` — Stop-and-wait baseline algorithm (to be implemented)

## Running Tests

```bash
cd tests
python3 test_collision_avoidance.py
python3 test_deadlock_recovery.py
python3 test_task_assignment.py
```

## Running Full Benchmark

```bash
cd tests
python3 benchmark_runner.py \
    --num_agents 3 \
    --num_tasks 10 \
    --duration_sec 60 \
    --output_file benchmark_result.json
```

## Expected Metrics

- **Collisions:** 0 (hard requirement)
- **Task completion time:** ≥20% faster than baseline
- **Communication latency:** p99 < 150ms
- **Agent CPU:** < 20% per core

## CI/CD Integration

Tests run automatically on every commit:
```bash
docker-compose up -d
sleep 10
docker-compose exec test-runner python3 benchmark_runner.py
```
