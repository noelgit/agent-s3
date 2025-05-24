"""
SummaryValidationConfig: Configurable thresholds and settings for summary validation.
"""
class SummaryValidationConfig:
    def __init__(self, faithfulness_threshold=0.85, detail_preservation_threshold=0.90,
         structural_coherence_threshold=0.90, max_refinement_attempts=3):        self.faithfulness_threshold = faithfulness_threshold
        self.detail_preservation_threshold = detail_preservation_threshold
        self.structural_coherence_threshold = structural_coherence_threshold
        self.max_refinement_attempts = max_refinement_attempts
