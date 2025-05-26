# Merge Conflict Resolution

This document outlines recommended steps to resolve merge conflicts when updating the repository.

1. **Fetch Latest Changes**
   ```bash
   git fetch origin
   ```
2. **Switch to your feature branch**
   ```bash
   git checkout work
   ```
3. **Merge or Rebase**
   ```bash
   git merge origin/main
   # or
   git rebase origin/main
   ```
4. **Resolve Conflicts**
   - Open conflicting files indicated by Git.
   - Edit the files to keep the desired code and remove conflict markers.
   - For example, lines around `DebuggingManager` have changed. Ensure any removed helper methods are not referenced elsewhere.
5. **Run Tests**
   ```bash
   ruff check agent_s3
   mypy agent_s3
   pytest -q
   ```
6. **Commit and Continue**
   ```bash
   git add <files>
   git commit -m "fix: resolve merge conflicts"
   git rebase --continue  # if rebasing
   ```
7. **Push the branch**
   ```bash
   git push origin work
   ```
