# Contributing to LLM Walkie-Talkie

First off, thank you for considering contributing to LLM Walkie-Talkie! Contributions make open-source projects an amazing place to learn, inspire, and create.

## How Can I Contribute?

### Reporting Bugs
- Use GitHub Issues to submit reports.
- Provide a clear, detailed description of the problem, including the command executed, the logs output, and your operating system / python version environment setup.

### Proposing Enhancements
- Open a GitHub Issue explaining the feature request, why it is needed, and any implementation details.

### Submitting Pull Requests
1. Fork the repository and check out your branch from `main`.
2. Install the package in editable mode with development dependencies:
   ```bash
   pip install -e .
   ```
3. Implement your changes, following clean coding practices.
4. Keep modifications modular, avoiding monolithic additions to `walkie.py`.
5. Ensure your code is syntactically correct and format it cleanly.
6. Commit your changes with concise commit messages.
7. Open a Pull Request referencing the related Issue.

## Coding Style & Standards
- Keep CLI stdout/stderr printouts clean. Stderr should be used for background status logs (`click.secho(..., err=True)`) and stdout reserved for query responses.
- Respect configured API key pattern checks. Ensure no private tokens are printed to logs or standard error streams.
- Document new methods or configurations.
