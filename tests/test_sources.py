import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from public_sources import (
    PUBLIC_SOURCES,
    fetch_glassdoor_description,
    parse_custom_career_html,
    parse_glassdoor_html,
    parse_kimeta_html,
    parse_talent_html,
)
from source_registry import build_targets, load_private_sources, parse_listing_date


KEYWORDS = ["Software Engineer"]
NEGATIVE_KEYWORDS = ["Senior"]


class PublicSourceParserTests(unittest.TestCase):
    def test_custom_career_parser_extracts_keyword_matching_links(self):
        html = """
        <main>
          <a href="/jobs/python-werkstudent"><h2>Werkstudent Python Automation</h2>
             <time datetime="2026-08-18">18.08.2026</time></a>
          <a href="/about">Über uns</a>
          <a href="https://jobs.example.test/other"><h2>Senior Accountant</h2></a>
        </main>
        """

        jobs = parse_custom_career_html(
            html,
            "https://acme.example/careers",
            ["Werkstudent", "Python"],
            ["Senior"],
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "Werkstudent Python Automation")
        self.assertEqual(jobs[0]["link"], "https://acme.example/jobs/python-werkstudent")
        self.assertEqual(jobs[0]["company"], "Acme")
        self.assertEqual(jobs[0]["platform"], "Custom Careers")
        self.assertEqual(jobs[0]["date"], "2026-08-18")

    def test_custom_career_source_is_configurable_as_a_list(self):
        config = {
            "custom_links": [
                "https://one.example/careers",
                "https://two.example/jobs",
            ],
            "custom_pages": 1,
        }

        targets = build_targets(config, PUBLIC_SOURCES)

        self.assertEqual(len([target for target in targets if target["domain"] == "Custom Careers"]), 2)

    def test_talent_parser_preserves_job_contract(self):
        html = """
        <article data-testid="job-card-unified">
          <h2 class="JobCard_title__x">Software Engineer</h2>
          <span class="JobCard_company__x">Example GmbH</span>
          <p class="JobCard_snippet__x">Python platform work</p>
          <a href="/view?id=123&tracking=no">Mehr anzeigen</a>
          <time datetime="2026-08-17T10:00:00Z">Gestern</time>
        </article>
        """
        jobs = parse_talent_html(
            html, "https://de.talent.com/jobs", KEYWORDS, NEGATIVE_KEYWORDS
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["platform"], "Talent.com")
        self.assertEqual(jobs[0]["link"], "https://de.talent.com/view?id=123")
        self.assertEqual(jobs[0]["date"], "2026-08-17")

    def test_kimeta_parser_extracts_company_date_and_preview(self):
        html = """
        <div class="offer">
          <div class="offer-head"><a href="/display-job/acme/software/99.html">
            <div class="cn">Acme GmbH</div><h3 class="jt">Software Engineer</h3>
            <span>Berlin</span><span>17.8.2026</span>
          </a></div>
          <div class="summary">Build reliable services</div>
        </div>
        """
        jobs = parse_kimeta_html(
            html, "https://www.kimeta.de/search", KEYWORDS, NEGATIVE_KEYWORDS
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["company"], "Acme GmbH")
        self.assertEqual(jobs[0]["date"], "2026-08-17")
        self.assertIn("Build reliable services", jobs[0]["preview_text"])

    def test_glassdoor_parser_marks_negative_keywords(self):
        html = """
        <li data-test="jobListing" data-jobid="77">
          <span class="EmployerProfile_compactEmployerName__x">Acme</span>
          <a data-test="job-title" href="/job-listing/example.htm?jl=77&src=tracking">
            Senior Software Engineer
          </a>
          <div data-test="descSnippet">Senior backend role</div>
          <div data-test="job-age">2T</div>
        </li>
        """
        jobs = parse_glassdoor_html(
            html,
            "https://www.glassdoor.de/Job/search.htm",
            KEYWORDS,
            NEGATIVE_KEYWORDS,
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["negative_keyword"], "Senior")
        self.assertEqual(jobs[0]["link"], "https://www.glassdoor.de/job-listing/example.htm?jl=77")
        self.assertEqual(
            jobs[0]["_detail_url"],
            "https://www.glassdoor.de/Job/search.htm?jl=77",
        )

    @patch("public_sources.fetch_soup")
    def test_glassdoor_description_uses_matching_search_detail_pane(self, fetch_soup):
        description = "Senior Software Engineer " + ("Full role details. " * 20)
        fetch_soup.return_value = BeautifulSoup(
            f'<div class="JobDetails_jobDescription__x">{description}</div>',
            "html.parser",
        )
        job = {
            "title": "Senior Software Engineer",
            "_detail_url": "https://www.glassdoor.de/Job/search.htm?jl=77",
        }

        result = fetch_glassdoor_description(job)

        self.assertIn("Full role details", result)
        fetch_soup.assert_called_once_with(job["_detail_url"], "Glassdoor detail pane")

    @patch("public_sources.fetch_soup")
    def test_glassdoor_description_rejects_wrong_selected_job(self, fetch_soup):
        fetch_soup.return_value = BeautifulSoup(
            '<div class="JobDetails_jobDescription__x">'
            + ("Unrelated Accountant role. " * 20)
            + "</div>",
            "html.parser",
        )
        job = {
            "title": "Senior Software Engineer",
            "_detail_url": "https://www.glassdoor.de/Job/search.htm?jl=77",
        }

        self.assertIsNone(fetch_glassdoor_description(job))

    def test_non_matching_title_is_filtered(self):
        html = """
        <article data-testid="job-card-unified">
          <h2 class="JobCard_title__x">Accountant</h2>
          <a href="/view?id=123">Mehr anzeigen</a>
        </article>
        """
        self.assertEqual(
            parse_talent_html(html, "https://de.talent.com/jobs", KEYWORDS, NEGATIVE_KEYWORDS),
            [],
        )

    def test_target_builder_paginates_and_clamps_kimeta(self):
        config = {
            "talent_link": "https://de.talent.com/jobs?k=python",
            "talent_pages": 2,
            "kimeta_link": "https://www.kimeta.de/stellenangebote-python",
            "kimeta_pages": 4,
        }
        targets = build_targets(config, PUBLIC_SOURCES)
        self.assertEqual(len(targets), 3)
        self.assertIn("p=2", targets[1]["url"])
        self.assertEqual(targets[2]["domain"], "Kimeta")

    def test_target_builder_accepts_multiple_links_and_removes_duplicates(self):
        config = {
            "talent_link": [
                "https://de.talent.com/jobs?k=werkstudent&l=hamburg",
                "https://de.talent.com/jobs?k=werkstudent+remote&l=deutschland",
                "https://de.talent.com/jobs?k=werkstudent&l=hamburg",
                "not-a-url",
            ],
            "talent_pages": 2,
        }
        targets = build_targets(config, PUBLIC_SOURCES)
        self.assertEqual(len(targets), 4)
        self.assertEqual(targets[0]["page"], 1)
        self.assertEqual(targets[2]["page"], 1)
        self.assertIn("remote", targets[2]["url"])

    def test_missing_private_directory_is_optional(self):
        self.assertEqual(load_private_sources("/path/that/does/not/exist"), [])

    def test_compact_glassdoor_hours_are_parsed(self):
        parsed = parse_listing_date("24Std")
        self.assertRegex(parsed, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")

    def test_plus_suffixed_relative_age_is_parsed(self):
        parsed = parse_listing_date("vor 30+ Tagen")
        self.assertRegex(parsed, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


if __name__ == "__main__":
    unittest.main()
