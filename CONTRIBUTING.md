# Contributing to Job Hunter

Thanks for your interest in contributing!

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/job-hunter.git
   cd job-hunter
   ```
3. Install in development mode:
   ```bash
   pip install -e .
   pip install -r requirements.txt
   ```
4. Copy the environment config:
   ```bash
   cp .env.example .env
   # Add your ANTHROPIC_API_KEY
   ```

## Development

### Code Style
- Python 3.11+
- Type hints on all functions
- snake_case for variables and functions, PascalCase for classes
- Keep code modular and testable

### Running Tests
```bash
pytest              # Run all 374 tests
pytest -x           # Stop on first failure
pytest -k "test_onboarding"  # Run matching tests
```

### Making Changes
1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass: `pytest`
5. Commit with a clear message: `git commit -m "add: description of change"`
6. Push and open a Pull Request

## Reporting Issues

Use the GitHub issue templates for:
- **Bug reports** — include steps to reproduce and expected vs actual behavior
- **Feature requests** — describe the use case and proposed solution

## Questions?

Open an issue or reach out via the contact info in the README.
