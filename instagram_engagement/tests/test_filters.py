import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engagement import PostStats
from filters import filter_posts, search_comments, sort_posts


def _post(post_id, likes, comments, timestamp="", caption="", permalink=""):
    return PostStats(
        post_id=post_id,
        likes=likes,
        comments=comments,
        timestamp=timestamp,
        permalink=permalink,
        caption=caption,
    )


class FilterPostsTest(unittest.TestCase):
    def setUp(self):
        self.posts = [
            _post("1", likes=10, comments=2, timestamp="2024-01-01T10:00:00", caption="عرض شتوي"),
            _post("2", likes=100, comments=20, timestamp="2024-06-15T10:00:00", caption="صيف حار"),
            _post("3", likes=50, comments=5, timestamp="2024-12-31T10:00:00", caption="عرض خاص"),
        ]

    def test_keyword_matches_caption_case_insensitively(self):
        matches = filter_posts(self.posts, keyword="عرض")
        self.assertEqual({p.post_id for p in matches}, {"1", "3"})

    def test_min_likes(self):
        matches = filter_posts(self.posts, min_likes=50)
        self.assertEqual({p.post_id for p in matches}, {"2", "3"})

    def test_max_likes(self):
        matches = filter_posts(self.posts, max_likes=50)
        self.assertEqual({p.post_id for p in matches}, {"1", "3"})

    def test_min_interactions(self):
        matches = filter_posts(self.posts, min_interactions=100)
        self.assertEqual({p.post_id for p in matches}, {"2"})

    def test_date_range(self):
        matches = filter_posts(self.posts, since="2024-02-01", until="2024-07-01")
        self.assertEqual({p.post_id for p in matches}, {"2"})

    def test_no_filters_returns_everything(self):
        matches = filter_posts(self.posts)
        self.assertEqual(len(matches), 3)

    def test_combined_filters(self):
        matches = filter_posts(self.posts, keyword="عرض", min_likes=20)
        self.assertEqual({p.post_id for p in matches}, {"3"})

    def test_invalid_date_raises(self):
        with self.assertRaises(ValueError):
            filter_posts(self.posts, since="not-a-date")


class SortPostsTest(unittest.TestCase):
    def setUp(self):
        self.posts = [
            _post("1", likes=10, comments=2, timestamp="2024-01-01T10:00:00"),
            _post("2", likes=100, comments=20, timestamp="2024-06-15T10:00:00"),
            _post("3", likes=50, comments=5, timestamp="2024-12-31T10:00:00"),
        ]

    def test_sort_by_likes_descending(self):
        result = sort_posts(self.posts, sort_by="likes")
        self.assertEqual([p.post_id for p in result], ["2", "3", "1"])

    def test_sort_by_interactions_ascending(self):
        result = sort_posts(self.posts, sort_by="interactions", descending=False)
        self.assertEqual([p.post_id for p in result], ["1", "3", "2"])

    def test_unknown_sort_key_raises(self):
        with self.assertRaises(ValueError):
            sort_posts(self.posts, sort_by="unknown")


class SearchCommentsTest(unittest.TestCase):
    def setUp(self):
        self.comments = [
            {"id": "1", "username": "ali", "text": "منتج رائع"},
            {"id": "2", "username": "sara", "text": "السعر مرتفع"},
            {"id": "3", "username": "ali", "text": "متى يتوفر مجددًا؟"},
        ]

    def test_keyword_filters_text(self):
        matches = search_comments(self.comments, keyword="رائع")
        self.assertEqual([c["id"] for c in matches], ["1"])

    def test_author_filters_exact_username(self):
        matches = search_comments(self.comments, author="ali")
        self.assertEqual([c["id"] for c in matches], ["1", "3"])

    def test_combined_keyword_and_author_no_match(self):
        matches = search_comments(self.comments, keyword="رائع", author="sara")
        self.assertEqual(matches, [])

    def test_no_filters_returns_everything(self):
        matches = search_comments(self.comments)
        self.assertEqual(len(matches), 3)


if __name__ == "__main__":
    unittest.main()
