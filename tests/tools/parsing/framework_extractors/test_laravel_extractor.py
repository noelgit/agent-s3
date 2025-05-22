from agent_s3.tools.parsing.framework_extractors.laravel_extractor import LaravelExtractor

def test_laravel_extractor_basic():
    extractor = LaravelExtractor()
    code = '''<?php
    namespace App\\Http\\Controllers;
    use Illuminate\\Routing\\Controller;
    class HomeController extends Controller {
        public function index() { return view('home'); }
    }
    '''
    root_node = None
    tech_stack = {'frameworks': ['laravel']}
    results = extractor.extract(root_node, 'HomeController.php', code, 'php', tech_stack)
    assert isinstance(results, list)
    assert extractor.is_relevant_framework(tech_stack, 'HomeController.php', code)
