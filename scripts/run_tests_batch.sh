#!/bin/zsh
# Run each test file individually with timeout and log results
cd "$(dirname "$0")/.."

TEST_DIR="test"
LOG="test_batch_results.log"
PYTEST=".venv/bin/pytest"
MAXTIME=60

rm -f "$LOG"
echo "Batch test run started: $(date)" | tee -a "$LOG"

for f in $TEST_DIR/test_*.py; do
  echo "\n===== Running $f =====" | tee -a "$LOG"
  (gtimeout $MAXTIME $PYTEST "$f" -q --tb=short > /tmp/test_out.log 2>&1)
  exit_code=$?
  if [[ $exit_code -eq 124 ]]; then
    echo "TIMEOUT: $f (exceeded ${MAXTIME}s)" | tee -a "$LOG"
  elif [[ $exit_code -ne 0 ]]; then
    echo "FAILED: $f" | tee -a "$LOG"
    tail -20 /tmp/test_out.log | tee -a "$LOG"
  else
    echo "PASSED: $f" | tee -a "$LOG"
  fi
  rm -f /tmp/test_out.log
  sleep 1
  # Optional: break on first hang/failure
  # [[ $exit_code -ne 0 ]] && break
done

echo "\nBatch test run complete: $(date)" | tee -a "$LOG"
