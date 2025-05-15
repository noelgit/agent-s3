#!/usr/bin/env python3
"""
Test script to verify Tree-sitter parser integration with the modern capsule-based approach.
"""
from agent_s3.tools.parsing.parser_registry import ParserRegistry

def test_javascript_parser():
    """Test the JavaScript parser with a simple code snippet."""
    parser_registry = ParserRegistry()
    js_parser = parser_registry.get_parser(language_name="javascript")
    
    js_code = """
    class Person {
        constructor(name) {
            this.name = name;
        }
        
        sayHello() {
            console.log(`Hello, ${this.name}!`);
        }
    }
    
    function greet(person) {
        person.sayHello();
    }
    
    const john = new Person("John");
    greet(john);
    """
    
    result = js_parser.analyze(js_code, "test.js", {})
    print("\n=== JavaScript Parser Test ===")
    print(f"Found {len(result['nodes'])} nodes")
    for node in result['nodes']:
        print(f"- {node['type']}: {node['name']}")
    
    return len(result['nodes']) > 0

def test_php_parser():
    """Test the PHP parser with a simple code snippet."""
    parser_registry = ParserRegistry()
    php_parser = parser_registry.get_parser(language_name="php")
    
    php_code = """<?php
    class Person {
        private $name;
        
        public function __construct($name) {
            $this->name = $name;
        }
        
        public function sayHello() {
            echo "Hello, {$this->name}!";
        }
    }
    
    function greet($person) {
        $person->sayHello();
    }
    
    $john = new Person("John");
    greet($john);
    ?>
    """
    
    result = php_parser.analyze(php_code, "test.php", {})
    print("\n=== PHP Parser Test ===")
    print(f"Found {len(result['nodes'])} nodes")
    for node in result['nodes']:
        print(f"- {node['type']}: {node['name']}")
    
    return len(result['nodes']) > 0

def test_typescript_parser():
    """Test the TypeScript parser with a simple code snippet."""
    parser_registry = ParserRegistry()
    ts_parser = parser_registry.get_parser(language_name="typescript")
    
    ts_code = """
    class Person {
        name: string;
        
        constructor(name: string) {
            this.name = name;
        }
        
        sayHello(): void {
            console.log(`Hello, ${this.name}!`);
        }
    }
    
    function greet(person: Person): void {
        person.sayHello();
    }
    
    const john = new Person("John");
    greet(john);
    """
    
    result = ts_parser.analyze(ts_code, "test.ts", {})
    print("\n=== TypeScript Parser Test ===")
    print(f"Found {len(result['nodes'])} nodes")
    for node in result['nodes']:
        print(f"- {node['type']}: {node['name']}")
    
    return len(result['nodes']) > 0

if __name__ == "__main__":
    print("Testing Tree-sitter parsers with the modern capsule-based approach...")
    js_success = test_javascript_parser()
    php_success = test_php_parser()
    ts_success = test_typescript_parser()
    
    print("\n=== Test Results ===")
    print(f"JavaScript Parser: {'✅ SUCCESS' if js_success else '❌ FAILED'}")
    print(f"PHP Parser: {'✅ SUCCESS' if php_success else '❌ FAILED'}")
    print(f"TypeScript Parser: {'✅ SUCCESS' if ts_success else '❌ FAILED'}")
