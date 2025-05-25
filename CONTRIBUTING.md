# Contributing

We welcome contributions that improve Agent-S3. Before opening a pull request,
review the consolidated guidelines in
[docs/development_guidelines.md](docs/development_guidelines.md).
Then ensure the following:

- **Setup:** install runtime and development dependencies:
  ```bash
  pip install -r requirements.txt
  pip install -r requirements-dev.txt
  ```

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

For complete development guidelines, see
[docs/development_guidelines.md](docs/development_guidelines.md) and
[docs/debugging_and_error_handling.md](docs/debugging_and_error_handling.md).
Additional instructions reside in `.github/copilot-instructions.md` and
`README.md`.


