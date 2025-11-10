# Contributing to Sentinel

Thank you for your interest in contributing to Sentinel!

## Development Workflow

### Prerequisites

- Python 3.11+
- Go 1.21+
- Docker & Docker Compose
- kubectl & kind/minikube
- Pre-commit hooks (optional but recommended)

### Setting Up Local Development

```bash
# Clone the repository
git clone https://github.com/<org>/sentinel.git
cd sentinel

# Set up pre-commit hooks (optional)
pip install pre-commit
pre-commit install

# Start local dev environment
make dev-up

# Run tests
make test
```

### Code Style

#### Python

- Follow PEP 8
- Use Black for formatting (100 char line length)
- Use Ruff for linting
- Type hints required (mypy strict mode)
- Docstrings in Google style

```bash
# Format and lint Python code
make format-python
make lint-python
```

#### Go

- Follow standard Go conventions
- Use `gofmt` for formatting
- Run `go vet` and `golangci-lint`

```bash
# Format and lint Go code
make format-go
make lint-go
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(api): add action plan validation endpoint
fix(controller): handle edge case in canary rollout
docs(readme): update installation instructions
```

### Testing

- Unit tests required for all new code
- Integration tests for critical paths
- Minimum 80% code coverage

```bash
# Run all tests
make test

# Run specific service tests
make test-control-api
make test-agent

# Run integration tests
make test-integration
```

### Pull Request Process

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. Make your changes with tests and documentation

3. Ensure all tests pass and code is formatted:
   ```bash
   make test
   make lint
   ```

4. Commit your changes following commit message conventions

5. Push to your fork and create a pull request

6. Address review feedback

### PR Requirements

- All CI checks must pass
- Code coverage should not decrease
- Documentation updated if needed
- Changelog entry for user-facing changes
- Signed commits (DCO)

### Branch Naming

- `feat/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation only
- `refactor/*` - Code refactoring
- `test/*` - Test improvements
- `chore/*` - Maintenance tasks

## Project Structure

See [README.md](README.md#repository-structure) for detailed structure.

## Architecture Decisions

For significant architectural changes:

1. Open an issue for discussion first
2. Create an Architecture Decision Record (ADR) in `docs/adr/`
3. Get consensus from maintainers before implementing

## Security

Report security vulnerabilities privately to security@sentinel.ai

Do not open public issues for security vulnerabilities.

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.

## Questions?

- Open a [Discussion](../../discussions)
- Check the [Documentation](docs/README.md)
- Browse [existing issues](../../issues)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior via GitHub Issues.
