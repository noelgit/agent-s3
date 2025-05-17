"""
Script for running benchmark tests and measuring summary quality metrics.
"""
import os
from agent_s3.tools.summarization.summary_validator import SummaryValidator
from agent_s3.tools.summarization.validation_config import SummaryValidationConfig

def evaluate_benchmark(benchmark_dir):
    config = SummaryValidationConfig()
    validator = SummaryValidator(config)
    results = []
    for fname in os.listdir(benchmark_dir):
        if fname.endswith('.py'):
            with open(os.path.join(benchmark_dir, fname)) as f:
                source = f.read()
            summary_file = fname.replace('.py', '.summary.txt')
            summary_path = os.path.join(benchmark_dir, summary_file)
            if os.path.exists(summary_path):
                with open(summary_path) as f:
                    summary = f.read()
                valid, metrics = validator.validate(source, summary, language="python")
                results.append((fname, valid, metrics))
    return results

if __name__ == "__main__":
    benchmark_dir = "tests/data/summarization_benchmark"
    results = evaluate_benchmark(benchmark_dir)
    for fname, valid, metrics in results:
        print(f"{fname}: valid={valid}, metrics={metrics}")
