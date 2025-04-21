from setuptools import setup, find_packages

setup(
    name="agent_s3",
    version="0.1.0",
    description="Agent-S3: Ultimate all-inclusive AI coding agent scaffolder and runtime",
    author="Agent-S3",
    author_email="no-reply@example.com",
    url="https://github.com/agent-s3/agent-s3",
    packages=find_packages(include=["agent_s3", "agent_s3.*"]),
    install_requires=[
        "openai",  # OpenAI Python client
        "mistral",  # Mistral AI client
        "PyGithub",  # GitHub API client
        "faiss-cpu",  # FAISS vector store
        "flake8",  # Linting
        "requests"
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "agent_s3=agent_s3.cli:main"
        ]
    },
)
