# Sentinel Documentation

Welcome to the Sentinel documentation!

## Documentation Structure

- **[Architecture](architecture/)** - System architecture, design decisions, and component interactions
- **[API Reference](api/)** - REST API and gRPC specifications
- **[Runbooks](runbooks/)** - Operational guides and troubleshooting
- **[Guides](guides/)** - How-to guides and tutorials
- **[ADR](adr/)** - Architecture Decision Records

## Quick Links

- [Getting Started](guides/getting-started.md)
- [Development Guide](guides/development.md)
- [API Documentation](api/openapi.yaml)
- [Operator Guide](runbooks/operator-guide.md)
- [Security Model](security.md)

## Contributing to Documentation

Documentation is written in Markdown and follows the [Divio documentation system](https://documentation.divio.com/):

- **Tutorials** - Learning-oriented lessons
- **How-to guides** - Problem-oriented directions
- **Reference** - Information-oriented technical descriptions
- **Explanation** - Understanding-oriented discussions

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## Building Documentation

To serve documentation locally:

```bash
make docs-serve
# Visit http://localhost:8001
```

## Documentation Standards

- Use clear, concise language
- Include code examples where appropriate
- Keep diagrams up-to-date using Mermaid
- Cross-reference related documents
- Update changelog when making significant changes
