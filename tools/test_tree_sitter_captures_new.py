#!/usr/bin/env python3
"""
New debug script to understand the capture format from tree-sitter queries.
"""
from tree_sitter import Language
from tree_sitter import Parser
from tree_sitter import Query
import tree_sitter_javascript

def test_tree_sitter_captures():
    print("Testing Tree-sitter query captures format...\n")

    # Create parser with JavaScript grammar
    grammar = Language(tree_sitter_javascript.language())
    parser = Parser()
    parser.language = grammar

    # Sample JavaScript code
    js_code = """
    class Person {
        constructor(name) {
            this.name = name;
        }

        sayHello() {
            console.log(`Hello, ${this.name}!`);
        }
    }

    function greet() {
        console.log("Hello");
    }
    """

    # Parse the code
    tree = parser.parse(bytes(js_code, 'utf8'))
    root_node = tree.root_node

    # Create and execute query
    query_string = '''
        (class_declaration
            name: (identifier) @class_name
        )
        (function_declaration
            name: (identifier) @function_name
        )
    '''

    query = Query(grammar, query_string)

    print(f"Query pattern count: {query.pattern_count}")
    print(f"Query capture count: {query.capture_count}")

    # Execute the query and print raw results
    print("\nRaw query.captures() result:")
    captures = query.captures(root_node)
    print(f"Type: {type(captures)}")
    print(f"Content: {captures}")

    # Get matches and print them
    print("\nUsing query.matches() instead:")
    matches = query.matches(root_node)
    print(f"Type: {type(matches)}")
    print(f"Length: {len(matches)}")

    for i, match in enumerate(matches):
        print(f"\nMatch {i}:")
        print(f"  Pattern index: {match.pattern_index}")
        print(f"  Captures: {match.captures}")

        for j, capture in enumerate(match.captures):
            print(f"    Capture {j}:")
            print(f"      Index: {capture.index}")
            print(f"      Name: {capture.name}")
            node = capture.node
            print(f"      Node type: {node.type}")
            print(f"      Node text: {node.text.decode() if hasattr(node, 'text') else 'N/A'}")

    # Execute query based on results from Query documentation
    print("\nProcess captures as described in documentation:")
    for match in query.matches(root_node):
        for capture in match.captures:
            capture_name = capture.name
            node = capture.node
            print(f"Capture: {capture_name}, Text: {node.text.decode() if hasattr(node, 'text') else 'N/A'}")

if __name__ == "__main__":
    test_tree_sitter_captures()
