# 初始化包
from .base_checker import BaseChecker
from .api_checker import ApiChecker
from .web_checker import WebChecker
from .di_checker_example import DICheckerExample
from .upstream_github_checker import UpstreamGithubChecker
from .upstream_gitlab_checker import UpstreamGitlabChecker
from .upstream_pypi_checker import UpstreamPypiChecker
from .upstream_common_checker import UpstreamCommonChecker
from .upstream_gitee_checker import UpstreamGiteeChecker
from .upstream_json_checker import UpstreamJsonChecker
from .upstream_redirect_checker import UpstreamRedirectChecker
# 该模块已不存在，暂时注释掉 - from .upstream_headless_checker import UpstreamHeadlessChecker
from .upstream_playwright_checker import UpstreamPlaywrightChecker
from .upstream_curl_checker import UpstreamCurlChecker
from .upstream_npm_checker import UpstreamNpmChecker

__all__ = [
    'BaseChecker',
    'ApiChecker',
    'WebChecker',
    'DICheckerExample',
    'UpstreamGithubChecker',
    'UpstreamGitlabChecker',
    'UpstreamPypiChecker',
    'UpstreamCommonChecker',
    'UpstreamGiteeChecker',
    'UpstreamJsonChecker',
    'UpstreamRedirectChecker',
    # 'UpstreamHeadlessChecker', # 已移除
    'UpstreamPlaywrightChecker',
    'UpstreamCurlChecker',
    'UpstreamNpmChecker'
]
