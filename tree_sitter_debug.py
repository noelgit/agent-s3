#!/usr/bin/env python3
"""
Tree-sitter API debug script.
"""
import json
import sys

def main():
    print(f"Python version: {sys.version}")
    
    # Import tree-sitter and its packages
    import tree_sitter
    print(f"\nTree-sitter version information from package:")
    print(f"  Package: {tree_sitter.__name__}")
    print(f"  File: {tree_sitter.__file__}")

    # Import language packages
    import tree_sitter_javascript
    import tree_sitter_php
    
    # Create a simple parser
    grammar_js = tree_sitter.Language(tree_sitter_javascript.language())
    parser = tree_sitter.Parser()
    parser.language = grammar_js
    
    # A simple JavaScript code snippet
    code = """
    function hello() {
        console.log("Hello, world!");
    }
    class User {
        constructor(name) {
            this.name = name;
        }
    }
    """
    
    # Parse the code
    tree = parser.parse(bytes(code, "utf8"))
    root = tree.root_node
    
    # Create and execute a query
    query_string = """
    (function_declaration name: (identifier) @func_name)
    (class_declaration name: (identifier) @class_name)
    """
    query = tree_sitter.Query(grammar_js, query_string)
    
    # Get query captures
    captures = query.captures(root)
    
    print("\nCaptures information:")
    print(f"  Type: {type(captures)}")
    
    if hasattr(captures, "__iter__"):
        print("  Iterable: Yes")
        print(f"  Length: {len(captures) if hasattr(captures, '__len__') else 'unknown'}")
        
        # Try to print the first few items
        try:
            for i, item in enumerate(captures[:3]):
                print(f"\n  Item {i}:")
                print(f"    Type: {type(item)}")
                print(f"    Value: {item}")
                print(f"    Dir: {dir(item)}")
                
                # If it's a tuple, examine its contents
                if isinstance(item, tuple):
                    print(f"    Tuple length: {len(item)}")
                    for j, element in enumerate(item):
                        print(f"      Element {j}: {type(element)}")
                        if hasattr(element, "text"):
                            try:
                                text = element.text.decode() if isinstance(element.text, bytes) else element.text
                                print(f"        Text: {text}")
                            except:
                                print(f"        Text: [Could not decode]")
        except Exception as e:
            print(f"  Error while iterating: {e}")
    else:
        print("  Iterable: No")
        print(f"  Dir: {dir(captures)}")
    
    # Try running matcher to understand its structure
    print("\nQuery matches information:")
    try:
        matches = query.matches(root)
        print(f"  Type: {type(matches)}")
        print(f"  Length: {len(matches) if hasattr(matches, '__len__') else 'unknown'}")
        
        # Examine the first match
        if hasattr(matches, "__iter__"):
            for i, match in enumerate(matches[:1]):
                print(f"\n  Match {i}:")
                print(f"    Type: {type(match)}")
                print(f"    Value: {match}")
                print(f"    Dir: {dir(match)}")
    except Exception as e:
        print(f"  Error with matches: {e}")

if __name__ == "__main__":
    main()
