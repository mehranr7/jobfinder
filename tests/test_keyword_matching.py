import unittest
import utils
from source_registry import make_job

class KeywordMatchingTests(unittest.TestCase):
    def test_word_boundary_prevents_false_substring_matches(self):
        keywords = ["Student", "Werkstudent", "Manager", "Management", "Engineer", "Engineering", "Data", "Database", "Java", "JavaScript"]
        
        # 'Werkstudent' should not match 'Student'
        matches = utils.match_keywords("Werkstudent Python Entwickler", ["Student", "Werkstudent"])
        self.assertEqual(matches, ["Werkstudent"])
        
        # 'Management' should not match 'Manager'
        matches = utils.match_keywords("Project Management Office", ["Manager", "Management"])
        self.assertEqual(matches, ["Management"])
        
        # 'Engineering' should not match 'Engineer'
        matches = utils.match_keywords("Software Engineering Intern", ["Engineer", "Engineering"])
        self.assertEqual(matches, ["Engineering"])
        
        # 'Database' should not match 'Data'
        matches = utils.match_keywords("Database Administrator", ["Data", "Database"])
        self.assertEqual(matches, ["Database"])
        
        # 'JavaScript' should not match 'Java'
        matches = utils.match_keywords("Frontend JavaScript Developer", ["Java", "JavaScript"])
        self.assertEqual(matches, ["JavaScript"])

    def test_special_programming_characters(self):
        # Test C#, C++, .NET, React.js, CI/CD
        keywords = ["C#", ".NET", "C++", "React.js", "CI/CD", "Python"]
        text = "Wir suchen C# / .NET Entwickler mit C++ und React.js Kenntnissen (CI/CD)."
        matches = utils.match_keywords(text, keywords)
        self.assertEqual(matches, ["C#", ".NET", "C++", "React.js", "CI/CD"])

    def test_german_umlauts_and_punctuation(self):
        keywords = ["Büro", "Führerschein", "Werkstudent", "Verkauf"]
        text = "Werkstudent (m/w/d) - Büro ohne Führerschein"
        matches = utils.match_keywords(text, keywords)
        self.assertEqual(matches, ["Büro", "Führerschein", "Werkstudent"])

    def test_make_job_strictly_matches_negative_keywords_on_title_only(self):
        # Card text contains negative keyword 'Manager' and 'Marketing', but Title does not!
        job = make_job(
            title="Werkstudent Python Developer",
            link="https://example.com/job/123",
            company="Marketing Agency Hamburg",
            platform="Stepstone",
            card_text="Marketing Agency Hamburg seeks Werkstudent Python Developer. Report to the Senior Engineering Manager.",
            keywords=["Werkstudent", "Python", "Developer"],
            negative_keywords=["Marketing", "Manager", "Senior", "Praxissemester"],
        )
        self.assertIsNotNone(job)
        self.assertEqual(job["title"], "Werkstudent Python Developer")
        self.assertEqual(job["keyword"], "Werkstudent, Python, Developer")
        # negative_keyword must be EMPTY because neither 'Marketing' nor 'Manager' nor 'Senior' is in the title!
        self.assertEqual(job["negative_keyword"], "")
        # Score should be 3 positive hits * 2 = 6
        self.assertEqual(job["keyword_score"], 6)

    def test_make_job_detects_negative_keywords_when_in_title(self):
        job = make_job(
            title="Senior Project Manager Werkstudent",
            link="https://example.com/job/456",
            company="Tech Corp",
            platform="Xing",
            card_text="Tech Corp seeks Senior Project Manager Werkstudent",
            keywords=["Werkstudent", "Project Manager"],
            negative_keywords=["Senior", "Manager", "Leitung"],
        )
        self.assertIsNotNone(job)
        self.assertIn("Senior", job["negative_keyword"])
        self.assertIn("Manager", job["negative_keyword"])
        # Positives (Werkstudent, Project Manager) = 2 * 2 = 4
        # Negatives (Senior, Manager) = 2 * -3 = -6
        # Keyword score = 4 - 6 = -2
        self.assertEqual(job["keyword_score"], -2)

    def test_clean_text_strips_boilerplate(self):
        raw_html = """
        <html>
            <head><title>Job</title></head>
            <body>
                <header class="site-header"><nav><ul><li>Home</li><li>Services</li><li>Karriere</li></ul></nav></header>
                <div class="cookie-banner">Bitte akzeptieren Sie Cookies</div>
                <main class="job-description">
                    <h1>Werkstudent AI Engineer</h1>
                    <p>Deine Aufgaben umfassen die Entwicklung von KI-Modellen mit PyTorch.</p>
                </main>
                <footer class="footer-nav"><p>Impressum & Datenschutz</p></footer>
            </body>
        </html>
        """
        cleaned = utils.clean_text(raw_html)
        self.assertIn("Werkstudent AI Engineer", cleaned)
        self.assertIn("KI-Modellen mit PyTorch", cleaned)
        self.assertNotIn("Bitte akzeptieren Sie Cookies", cleaned)
        self.assertNotIn("Impressum & Datenschutz", cleaned)
        self.assertNotIn("Services", cleaned)

if __name__ == "__main__":
    unittest.main()
