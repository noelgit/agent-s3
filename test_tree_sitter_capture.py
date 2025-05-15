#!/usr/bin/env python3
"""
Debug script to understand the capture format from tree-sitter queries.
"""
from tree_sitter import Parser, Language
import tree_sitter_javascript

def test_tree_sitter_captures():
    print("Testing Tree-sitter capture format...")
    
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
    """
    
    # Parse the code
    tree = parser.parse(bytes(js_code, 'utf8'))
    root_node = tree.root_node
    
    # Query for class declarations
    query_string = '((class_declaration name: (identifier) @name))'
    
    # Create query object
    from tree_sitter import Query
    query = Query(grammar, query_string)
    
    # Execute query
    captures = query.captures(root_node)
    
    # Print captures structure
    print(f"Type of captures: {type(captures)}")
    
    if hasattr(captures, "__iter__"):
        print(f"Captures is iterable")
        for i, item in enumerate(captures):
            print(f"\nItem {i}:")
            print(f"  Type: {type(item)}")
            print(f"  Value: {repr(item)}")
            
            if isinstance(item, tuple):
                print(f"  Tuple length: {len(item)}")
                for j, element in enumerate(item):
                    print(f"    Element {j}: {type(element)}, {element}")
                    
                    if hasattr(element, 'text'):
                        print(f"      Text: {element.text.decode() if isinstance(element.text, bytes) else element.text}")
    else:
        print("Captures is not directly iterable")
        print(f"Dir of captures: {dir(captures)}")
        
    # Try direct attribute access
    print("\nTrying to access captures directly:")
    try:
        for i, (node, name) in enumerate(captures):
            print(f"Capture {i}: {name} = {node.text.decode() if hasattr(node, 'text') and isinstance(node.text, bytes) else node}")
    except Exception as e:
        print(f"Error while iterating: {e}")

if __name__ == "__main__":
    test_tree_sitter_captures()
