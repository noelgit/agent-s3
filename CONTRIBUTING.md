# Contributing

We welcome contributions that improve Agent-S3. Before opening a pull request, please ensure the following:

- **Testing and linting:**
  - Run `pytest` and confirm all tests pass.
  - Run `mypy agent_s3` for static type checking.
  - Run `ruff check agent_s3` for linting.
  - Write commit messages according to the [Conventional Commits](#commit-messages) specification.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/) with the format `<type>(<scope>): <description>`.
Keep the description concise and in the imperative mood.
Examples:

```
fix(security): sanitize header logs
docs(readme): mention Supabase secrets
```

For details on development workflows and project guidelines, see `.github/copilot-instructions.md` and `README.md`.


