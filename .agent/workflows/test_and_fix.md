---
description: Run tests and fix errors iteratively
---

1. Run the tests using pytest inside the container
// turbo
2. run_command: docker-compose exec bot pytest tests/core/services/test_memory.py

3. If the tests fail, analyze the traceback.
4. Modify the code to fix the specific error.
5. Re-run the tests (step 2).
6. Repeat up to 3 times until success.
