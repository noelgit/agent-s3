"""
Complexity analysis module for assessing task implementation complexity.

This module provides tools to analyze and score the complexity of implementation tasks
based on multiple weighted factors including feature count, impacted files,
requirements complexity, security sensitivity, and external integrations.
"""
import logging
import re
from typing import Any
from typing import Dict
from typing import Optional

logger = logging.getLogger(__name__)

class ComplexityAnalyzer:
    """Analyzes and scores the complexity of implementation tasks."""

    def __init__(self):
        # Complexity factor weights
        self.weights = {
            "feature_count": 20,
            "impacted_files": 15,
            "requirements": 20,
            "technical_terms": 10,
            "dependencies": 15,
            "security_factors": 20
        }

        # Technical term patterns for complexity assessment
        self.technical_patterns = [
            r'\bdatabase\b', r'\bapi\b', r'\bsecurity\b', r'\bthreads?\b',
            r'\basync\b', r'\bconcurrency\b', r'\btransaction\b', r'\boptimiz\w+\b',
            r'\bcache\b', r'\bscale\b', r'\bcluster\b', r'\bdistributed\b',
            r'\bencrypt\w*\b', r'\bhash\w*\b', r'\bauthenticat\w*\b', r'\bauthoriz\w*\b'
        ]

        # Security-sensitive patterns
        self.security_patterns = [
            r'\bauth\w*\b', r'\blogin\b', r'\bpassword\b', r'\bcredential\b',
            r'\btoken\b', r'\bjwt\b', r'\bsecret\b', r'\bprivate\b', r'\bencrypt\w*\b',
            r'\bdecrypt\w*\b', r'\bpermission\b', r'\baccess\s+control\b', r'\brole\b'
        ]

        # External integration patterns
        self.integration_patterns = [
            r'\bthird[- ]party\b', r'\bexternal\b', r'\bintegrat\w+\b', r'\bapi\b',
            r'\bwebhook\b', r'\bcallback\b', r'\boauth\b', r'\bopenid\b'
        ]

    def assess_complexity(self, data: Dict[str, Any], task_description: str = "",
                        context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Assess complexity of pre-planning data and return comprehensive complexity score.

        Args:
            data: Pre-planning data
            task_description: Original task description
            context: Additional context information

        Returns:
            Dictionary with complexity assessment details
        """
        result = {
            "score": 0.0,            # Overall complexity score (0-100)
            "level": 1,              # Complexity level (1-5)
            "is_complex": False,     # Whether task requires confirmation
            "factors": {},           # Contributing factors
            "justification": [],     # Textual justification for score
            "advice": ""             # Handling advice
        }

        # --- Factor 1: Feature count and complexity ---
        features = []
        for group in data.get("feature_groups", []):
            features.extend(group.get("features", []))

        feature_count = len(features)
        avg_complexity = sum(feature.get("complexity", 1) for feature in features) / max(1, feature_count)

        # Score based on number of features and their average complexity
        feature_factor = min(feature_count * avg_complexity / 3.0, 1.0) * self.weights["feature_count"]
        result["factors"]["feature_complexity"] = feature_factor

        if feature_count > 5:
            result["justification"].append(f"High feature count ({feature_count}) increases complexity")
        if avg_complexity > 3:
            result["justification"].append(f"High average feature complexity ({avg_complexity:.1f}/5)")

        # --- Factor 2: Impacted files ---
        impacted_files = set()
        for feature in features:
            for step in feature.get("implementation_steps", []):
                if isinstance(step, dict) and "file_path" in step:
                    impacted_files.add(step["file_path"])

        file_count = len(impacted_files)
        file_factor = min(file_count / 5.0, 1.0) * self.weights["impacted_files"]
        result["factors"]["impacted_files"] = file_factor

        if file_count > 5:
            result["justification"].append(f"Changes span many files ({file_count})")

        # --- Factor 3: Requirements complexity ---
        requirements_text = task_description
        for feature in features:
            requirements_text += " " + feature.get("description", "")

        # Count technical terms in requirements
        technical_term_count = sum(len(re.findall(pattern, requirements_text, re.IGNORECASE))
                                 for pattern in self.technical_patterns)

        req_complexity = min(technical_term_count / 10.0, 1.0) * self.weights["requirements"]
        result["factors"]["requirements_complexity"] = req_complexity

        if technical_term_count > 10:
            result["justification"].append(f"High technical complexity ({technical_term_count} technical terms)")

        # --- Factor 4: Security sensitivity ---
        security_term_count = sum(len(re.findall(pattern, requirements_text, re.IGNORECASE))
                                for pattern in self.security_patterns)

        security_factor = min(security_term_count / 5.0, 1.0) * self.weights["security_factors"]
        result["factors"]["security_sensitivity"] = security_factor

        if security_term_count > 0:
            result["justification"].append(f"Security-sensitive implementation ({security_term_count} security terms)")

        # --- Factor 5: External integrations ---
        integration_count = sum(len(re.findall(pattern, requirements_text, re.IGNORECASE))
                               for pattern in self.integration_patterns)

        integration_factor = min(integration_count / 3.0, 1.0) * self.weights["dependencies"]
        result["factors"]["external_integrations"] = integration_factor

        if integration_count > 0:
            result["justification"].append(f"External integrations increase complexity ({integration_count} mentions)")

        # --- Calculate overall score ---
        result["score"] = sum(result["factors"].values())

        # Determine complexity level (1-5)
        if result["score"] < 20:
            result["level"] = 1
            result["is_complex"] = False
        elif result["score"] < 40:
            result["level"] = 2
            result["is_complex"] = False
        elif result["score"] < 60:
            result["level"] = 3
            result["is_complex"] = True
        elif result["score"] < 80:
            result["level"] = 4
            result["is_complex"] = True
        else:
            result["level"] = 5
            result["is_complex"] = True

        # Generate advice
        if result["is_complex"]:
            result["advice"] = (
                "This task has high complexity and should be confirmed with the user. "
                f"Consider breaking it into smaller sub-tasks with complexity level {max(1, result['level'] - 1)}."
            )
        else:
            result["advice"] = "This task has manageable complexity and can proceed without special handling."

        return result
