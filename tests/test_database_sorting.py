import unittest
import database

class DatabaseSortingTests(unittest.TestCase):
    def test_sorting_options_work_without_error(self):
        sort_options = [
            "date-desc",
            "date-asc",
            "title-asc",
            "title-desc",
            "score-desc",
            "score-asc",
            "kw-score-desc",
            "kw-score-asc",
        ]
        
        for sort_key in sort_options:
            jobs, total = database.get_jobs_filtered(sort=sort_key, page=1, page_size=5)
            self.assertIsInstance(jobs, list)
            self.assertIsInstance(total, int)
            self.assertGreaterEqual(total, 0)
            
    def test_kw_score_asc_sorting_order(self):
        jobs, total = database.get_jobs_filtered(sort="kw-score-asc", page=1, page_size=10)
        if len(jobs) >= 2:
            scores = [j.get("keyword_score", 0) for j in jobs]
            # Verify non-decreasing order
            for i in range(len(scores) - 1):
                self.assertLessEqual(scores[i], scores[i+1])

    def test_kw_score_desc_sorting_order(self):
        jobs, total = database.get_jobs_filtered(sort="kw-score-desc", page=1, page_size=10)
        if len(jobs) >= 2:
            scores = [j.get("keyword_score", 0) for j in jobs]
            # Verify non-increasing order
            for i in range(len(scores) - 1):
                self.assertGreaterEqual(scores[i], scores[i+1])

if __name__ == "__main__":
    unittest.main()
