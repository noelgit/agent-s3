from agent_s3.tools.parsing.framework_extractors.react_extractor import ReactExtractor

def test_react_extractor_basic():
    extractor = ReactExtractor()
    # Minimal JSX/React code
    code = '''import React from 'react';
    export default function App() {
      return (<div><MyComponent prop="x" /><ns.Another /></div>);
    }'''
    # Simulate a tree-sitter root_node (mocked for now)
    root_node = None
    tech_stack = {'frameworks': ['react']}
    results = extractor.extract(root_node, 'App.jsx', code, 'javascript', tech_stack)
    assert isinstance(results, list)
    assert extractor.is_relevant_framework(tech_stack, 'App.jsx', code)
