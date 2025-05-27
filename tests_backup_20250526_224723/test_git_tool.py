import pytest

from agent_s3.tools.git_tool import GitTool

class DummyResponse:
    def __init__(self, status_code, json_data=None, text=''):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text
    def json(self):
        return self._json

@pytest.fixture(autouse=True)
def dummy_repo_info(monkeypatch, tmp_path):
    # Monkeypatch get_repository_info to return dummy owner/repo/branch
    monkeypatch.setattr(GitTool, 'get_repository_info', lambda self: {
        'owner': 'test_owner', 'repo': 'test_repo', 'current_branch': 'feature-branch'
    })
    yield

def test_create_github_issue_success(monkeypatch):
    def fake_post(url, headers=None, json=None):
        assert 'repos/test_owner/test_repo/issues' in url
        return DummyResponse(201, {'html_url': 'https://github.com/test_owner/test_repo/issues/1'})
    monkeypatch.setattr('requests.post', fake_post)

    tool = GitTool(github_token='token')
    issue_url = tool.create_github_issue('Title', 'Body')
    assert issue_url == 'https://github.com/test_owner/test_repo/issues/1'

def test_create_pull_request_success(monkeypatch):
    def fake_post(url, headers=None, json=None):
        assert 'repos/test_owner/test_repo/pulls' in url
        return DummyResponse(201, {'html_url': 'https://github.com/test_owner/test_repo/pull/2'})
    monkeypatch.setattr('requests.post', fake_post)

    tool = GitTool(github_token='token')
    pr_url = tool.create_pull_request('PR Title', 'PR Body')
    assert pr_url == 'https://github.com/test_owner/test_repo/pull/2'

def test_create_pull_request_failure(monkeypatch):
    def fake_post(url, headers=None, json=None):
        return DummyResponse(400, text='Error')
    monkeypatch.setattr('requests.post', fake_post)

    tool = GitTool(github_token='token')
    pr_url = tool.create_pull_request('PR Title', 'PR Body')
    assert pr_url is None
