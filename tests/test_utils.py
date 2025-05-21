import unittest
import sys
import os
from unittest.mock import patch, Mock
import requests # For requests.exceptions.RequestException

# Adjust the Python path to include the root directory of the project
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from project.utils import is_safe_url, get_random_wikipedia_page, extract_wiki_links
# project.models.ALLOWED_DOMAIN is "wikipedia.org"

# Ensure requests.exceptions.RequestException exists for environments where 'requests' might be minimally mocked
if not hasattr(requests.exceptions, 'RequestException'):
    class RequestException(IOError): pass # Define a fallback exception
    requests.exceptions.RequestException = RequestException


class TestIsSafeURL(unittest.TestCase):
    def test_valid_wikipedia_urls(self):
        self.assertTrue(is_safe_url("https://ja.wikipedia.org/wiki/Test"))
        self.assertTrue(is_safe_url("http://en.wikipedia.org/wiki/Test")) 
        self.assertTrue(is_safe_url("https://es.wikipedia.org/wiki/Prueba"))
        self.assertTrue(is_safe_url("https://ja.m.wikipedia.org/wiki/Test")) 
        self.assertFalse(is_safe_url("https://commons.wikimedia.org/wiki/File:Example.jpg")) 

    def test_invalid_schemes(self):
        self.assertFalse(is_safe_url("ftp://ja.wikipedia.org/wiki/Test"))
        self.assertFalse(is_safe_url("javascript:alert(1)//ja.wikipedia.org"))

    def test_non_wikipedia_urls(self):
        self.assertFalse(is_safe_url("https://www.google.com"))
        self.assertFalse(is_safe_url("http://example.com/wiki/Test"))
        self.assertFalse(is_safe_url("https://en.wikipedia.org.hacker.com/wiki/Test"))
        self.assertFalse(is_safe_url("https://wikimedia.org.hacker.com/wiki/File:Example.jpg"))

    def test_malformed_and_empty_urls(self):
        self.assertFalse(is_safe_url(""))
        self.assertFalse(is_safe_url("http:///example.com"))
        self.assertFalse(is_safe_url("Just a string"))
        self.assertFalse(is_safe_url(None))

    def test_urls_with_ports_and_paths(self):
        self.assertTrue(is_safe_url("https://ja.wikipedia.org:443/wiki/Test"))
        self.assertFalse(is_safe_url("https://example.com:443/wiki/Test"))

    def test_subdomains_of_wikipedia(self):
        self.assertTrue(is_safe_url("https://toolserver.wikipedia.org/some/path"))
        self.assertTrue(is_safe_url("https://meta.wikipedia.org/wiki/Meta"))

class TestGetRandomWikipediaPage(unittest.TestCase):
    @patch('project.utils.requests.get')
    def test_get_random_page_returns_valid_url(self, mock_get):
        mock_response = Mock()
        mock_response.url = "https://ja.wikipedia.org/wiki/ランダムなページ"
        mock_response.raise_for_status = Mock() 
        mock_get.return_value = mock_response

        random_url = get_random_wikipedia_page()
        self.assertTrue(random_url.startswith("https://ja.wikipedia.org/wiki/"))
        mock_get.assert_called_once_with('https://ja.wikipedia.org/wiki/特別:おまかせ表示', allow_redirects=True, timeout=5)

    @patch('project.utils.requests.get')
    def test_get_random_page_handles_different_language(self, mock_get):
        mock_response = Mock()
        mock_response.url = "https://en.wikipedia.org/wiki/Random_Page"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        random_url = get_random_wikipedia_page(language='en')
        self.assertTrue(random_url.startswith("https://en.wikipedia.org/wiki/"))
        mock_get.assert_called_once_with('https://en.wikipedia.org/wiki/特別:おまかせ表示', allow_redirects=True, timeout=5)

    @patch('project.utils.requests.get')
    def test_get_random_page_handles_request_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        random_url = get_random_wikipedia_page()
        self.assertEqual(random_url, 'https://ja.wikipedia.org/wiki/メインページ') # Checks fallback

class TestExtractWikiLinks(unittest.TestCase):
    @patch('project.utils.requests.get')
    def test_extract_links_simple_page(self, mock_get):
        sample_html = '''
        <html><head><title>Test Page</title></head><body>
        <div id="mw-content-text">
            <p>Some text <a href="/wiki/Link_1">Link 1</a>.
               Another <a href="/wiki/Link_2_(disambiguation)">Link 2</a>.
               A section <a href="#Section">Section link</a>.
               An external <a href="http://example.com">External</a>.
            </p>
            <a href="/wiki/Link_3">Link 3 outside p</a>
        </div>
        </body></html>
        '''
        mock_response = Mock()
        mock_response.text = sample_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        links = extract_wiki_links("https://ja.wikipedia.org/wiki/Test_Page")
        self.assertIn("https://ja.wikipedia.org/wiki/Link_1", links)
        self.assertIn("https://ja.wikipedia.org/wiki/Link_2_(disambiguation)", links)
        self.assertIn("https://ja.wikipedia.org/wiki/Link_3", links)
        self.assertNotIn("https://ja.wikipedia.org#Section", links) 
        self.assertNotIn("http://example.com", links)
        self.assertEqual(len(links), 3)

    @patch('project.utils.requests.get')
    def test_extract_links_filters_special_pages(self, mock_get):
        sample_html = '''
        <html><body><div id="mw-content-text">
            <a href="/wiki/File:Example.jpg">File link</a>
            <a href="/wiki/Special:RecentChanges">Special page</a>
            <a href="/wiki/Category:Help">Category page</a>
            <a href="/wiki/Valid_Page">Valid Page</a>
            <a href="/wiki/ノート:Note_Page">Note Page</a>
        </div></body></html>
        '''
        mock_response = Mock()
        mock_response.text = sample_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        links = extract_wiki_links("https://ja.wikipedia.org/wiki/Test_Filter")
        self.assertIn("https://ja.wikipedia.org/wiki/Valid_Page", links)
        self.assertEqual(len(links), 1) # Based on current filtering in project/utils.py

    @patch('project.utils.requests.get')
    def test_extract_links_no_links(self, mock_get):
        sample_html = '<html><body><div id="mw-content-text"><p>No links here.</p></div></body></html>'
        mock_response = Mock()
        mock_response.text = sample_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        links = extract_wiki_links("https://ja.wikipedia.org/wiki/No_Links_Page")
        self.assertEqual(len(links), 0)

    @patch('project.utils.requests.get')
    def test_extract_links_deduplication(self, mock_get):
        sample_html = '''
        <html><body><div id="mw-content-text">
            <a href="/wiki/Link_1">Link 1</a>
            <a href="/wiki/Link_1">Link 1 again</a>
        </div></body></html>
        '''
        mock_response = Mock()
        mock_response.text = sample_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        links = extract_wiki_links("https://ja.wikipedia.org/wiki/Duplicate_Links_Page")
        self.assertEqual(len(links), 1)
        self.assertIn("https://ja.wikipedia.org/wiki/Link_1", links)

    @patch('project.utils.requests.get')
    def test_extract_links_request_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        links = extract_wiki_links("https://ja.wikipedia.org/wiki/Error_Page")
        self.assertEqual(len(links), 0) # Function returns empty list on exception

if __name__ == '__main__':
    unittest.main()
