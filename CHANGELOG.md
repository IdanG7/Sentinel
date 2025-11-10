# Changelog

All notable changes to Sentinel will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project scaffolding
- Repository structure for microservices architecture
- Control API skeleton with FastAPI
- Node Agent skeleton with Go
- Pipeline Controller structure
- InfraMind Adapter structure
- Shared libraries (policy-engine, k8s-driver, sentinel-common)
- gRPC protobuf definitions for InfraMind integration
- Development tooling (Makefile, pre-commit hooks)
- Documentation structure

## [0.1.0] - TBD

### Phase 0 - Scaffolding
- Project initialization
- Basic service structures
- Development environment setup

---

## Release Guidelines

### Version Numbering

- **MAJOR**: Breaking changes in API or architecture
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### Release Process

1. Update version in all `pyproject.toml` and `go.mod` files
2. Update CHANGELOG.md with release notes
3. Create git tag: `git tag -a v1.0.0 -m "Release v1.0.0"`
4. Push tag: `git push origin v1.0.0`
5. CI/CD will build and publish artifacts

### Deprecation Policy

- Deprecated features are marked in documentation and emit warnings
- Deprecated features are removed after **one minor version**
- Breaking changes require MAJOR version bump
