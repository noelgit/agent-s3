from agent_s3.llm_prompts.summarization_prompts import SummarizationPromptGenerator

def test_prompt_generator_python_function():
    gen = SummarizationPromptGenerator()
    prompt = gen.get_unit_prompt('function', 'foo', 'python', 'def foo(): pass')
    assert 'python function' in prompt
    assert 'foo' in prompt
    assert 'Code to summarize' in prompt

def test_prompt_generator_js_class():
    gen = SummarizationPromptGenerator()
    prompt = gen.get_unit_prompt('class', 'MyClass', 'javascript', 'class MyClass {}')
    assert 'javascript class' in prompt
    assert 'MyClass' in prompt
    assert 'Code to summarize' in prompt
