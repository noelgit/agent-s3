"""
Factory for creating optimized summarization prompts based on language, code type, and desired level of detail.
"""
class SummarizationPromptFactory:
    def create_prompt(self, code_chunk: str, language: str) -> dict:
        system_prompt = f"You are an expert code summarizer for {language} code. Summarize the following code chunk with maximum faithfulness and detail preservation."
        user_prompt = f"Summarize this {language} code:\n\n```{language}\n{code_chunk}\n```"
        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }
