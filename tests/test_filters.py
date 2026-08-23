"""Unit tests for filters.py. Run with: python -m unittest tests.test_filters
or: python tests/test_filters.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from filters import condition_note, matches_criteria


def make_listing(
    size=None,
    price=20.0,
    title="Lululemon Speed Up Shorts 2.5",
    condition="used_excellent",
    country="US",
    is_kids=False,
):
    # Defaults here are deliberately chosen to pass the REAL config.py
    # criteria (keyword, exclusion, condition, country, kids) so tests that
    # only care about size/price can pass target_sizes/max_price overrides
    # without also having to fight the other checks.
    return {
        "id": "abc123",
        "title": title,
        "price": price,
        "currency": "GBP",
        "size": size,
        "url": "https://www.depop.com/products/abc123/",
        "image_url": None,
        "condition": condition,
        "country": country,
        "is_kids": is_kids,
    }


class TestMatchesCriteria(unittest.TestCase):
    def test_size_match_exact(self):
        listing = make_listing(size="UK 8")
        self.assertTrue(matches_criteria(listing, target_sizes=["UK 6", "UK 8"], max_price=None))

    def test_size_match_case_insensitive(self):
        listing = make_listing(size="uk 8")
        self.assertTrue(matches_criteria(listing, target_sizes=["UK 6", "UK 8"], max_price=None))

    def test_size_mismatch(self):
        listing = make_listing(size="UK 10")
        self.assertFalse(matches_criteria(listing, target_sizes=["UK 6", "UK 8"], max_price=None))

    def test_size_none_with_criteria_specified_fails(self):
        # A listing with no parsed size does NOT match once sizes are
        # specified -- better to miss an ambiguous listing than spam.
        listing = make_listing(size=None)
        self.assertFalse(matches_criteria(listing, target_sizes=["UK 6", "UK 8"], max_price=None))

    def test_size_none_with_empty_target_sizes_passes(self):
        # Empty TARGET_SIZES means size filtering is skipped entirely, so
        # even an unparsed size passes.
        listing = make_listing(size=None)
        self.assertTrue(matches_criteria(listing, target_sizes=[], max_price=None))

    def test_empty_target_sizes_passes_all_sizes(self):
        listing = make_listing(size="XL")
        self.assertTrue(matches_criteria(listing, target_sizes=[], max_price=None))

    def test_price_ceiling_boundary_equal_passes(self):
        listing = make_listing(size=None, price=40.0)
        self.assertTrue(matches_criteria(listing, target_sizes=[], max_price=40.0))

    def test_price_ceiling_boundary_over_fails(self):
        listing = make_listing(size=None, price=40.01)
        self.assertFalse(matches_criteria(listing, target_sizes=[], max_price=40.0))

    def test_price_none_skips_price_check(self):
        listing = make_listing(size=None, price=999.0)
        self.assertTrue(matches_criteria(listing, target_sizes=[], max_price=None))

    def test_both_criteria_must_pass(self):
        listing = make_listing(size="UK 8", price=50.0)
        self.assertFalse(matches_criteria(listing, target_sizes=["UK 8"], max_price=40.0))
        listing_ok = make_listing(size="UK 8", price=30.0)
        self.assertTrue(matches_criteria(listing_ok, target_sizes=["UK 8"], max_price=40.0))

    def test_defaults_to_config_when_not_passed(self):
        # No kwargs passed -> falls back to the real config.py criteria.
        # Build a listing that satisfies all of them.
        listing = make_listing(size="0", price=20.0)
        self.assertTrue(matches_criteria(listing))

        # Flip one field (price over config.MAX_PRICE) and it should fail.
        over_priced = make_listing(size="0", price=26.0)
        self.assertFalse(matches_criteria(over_priced))


class TestRequiredKeywords(unittest.TestCase):
    def test_keyword_present_passes(self):
        listing = make_listing(title="Lululemon speed up shorts", size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=["speed up"],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=[],
            )
        )

    def test_keyword_absent_fails(self):
        listing = make_listing(title="Lululemon align shorts", size=None, price=None)
        self.assertFalse(
            matches_criteria(
                listing,
                required_keywords=["speed up"],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=[],
            )
        )

    def test_keyword_case_insensitive(self):
        listing = make_listing(title="LULULEMON SPEED UP SHORTS", size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=["speed up"],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=[],
            )
        )

    def test_keyword_matches_via_hyphen_normalization(self):
        listing = make_listing(title="lulu speed-up low rise 2.5", size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=["speed up"],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=[],
            )
        )

    def test_empty_required_keywords_skips_check(self):
        listing = make_listing(title="nothing relevant here", size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=[],
            )
        )


class TestExcludedTerms(unittest.TestCase):
    def _check(self, title, expected_pass, excluded_terms=None):
        listing = make_listing(title=title, size=None, price=None)
        result = matches_criteria(
            listing,
            required_keywords=[],
            excluded_terms=excluded_terms if excluded_terms is not None else ["rep", "style", "stain", "stains", "high rise", "high waist", '4"', "4in", "smoke home", "smoker"],
            target_sizes=[],
            max_price=None,
            allowed_conditions=[],
            allowed_countries=[],
        )
        self.assertEqual(result, expected_pass, f"title={title!r}")

    def test_rep_does_not_kill_represent(self):
        self._check("Lululemon speed up shorts, represent quality", True)

    def test_style_kills_whole_word_match(self):
        self._check("lululemon style shorts", False)

    def test_stylish_survives(self):
        self._check("these stylish shorts are great", True)

    def test_trailing_period_still_matches(self):
        self._check("shorts have small stains.", False)

    def test_high_rise_hyphenated_matches_via_normalization(self):
        self._check("lululemon speed up high-rise shorts", False)

    def test_inch_mark_kills_wrong_inseam(self):
        self._check('4" speed up shorts', False)

    def test_bare_size_number_survives(self):
        self._check("size 4 speed up", True)

    def test_smoke_free_home_survives(self):
        self._check("from a smoke free home", True)

    def test_smoke_home_dies(self):
        self._check("from a smoke home", False)

    def test_smoker_dies(self):
        self._check("kept by a non smoker", False)

    def test_empty_excluded_terms_skips_check(self):
        self._check("this has a stain and is high rise", True, excluded_terms=[])


class TestCondition(unittest.TestCase):
    def test_used_good_fails(self):
        listing = make_listing(condition="used_good", size=None, price=None)
        self.assertFalse(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=["brand_new", "used_like_new", "used_excellent"],
                allowed_countries=[],
            )
        )

    def test_used_excellent_passes(self):
        listing = make_listing(condition="used_excellent", size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=["brand_new", "used_like_new", "used_excellent"],
                allowed_countries=[],
            )
        )

    def test_brand_new_passes(self):
        listing = make_listing(condition="brand_new", size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=["brand_new", "used_like_new", "used_excellent"],
                allowed_countries=[],
            )
        )

    def test_missing_condition_passes(self):
        listing = make_listing(condition=None, size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=["brand_new", "used_like_new", "used_excellent"],
                allowed_countries=[],
            )
        )

    def test_empty_allowed_conditions_skips_check(self):
        listing = make_listing(condition="used_good", size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=[],
            )
        )


class TestCountry(unittest.TestCase):
    def test_us_passes(self):
        listing = make_listing(country="US", size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=["US", "CA"],
            )
        )

    def test_ca_passes(self):
        listing = make_listing(country="CA", size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=["US", "CA"],
            )
        )

    def test_gb_fails(self):
        listing = make_listing(country="GB", size=None, price=None)
        self.assertFalse(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=["US", "CA"],
            )
        )

    def test_missing_country_passes(self):
        listing = make_listing(country=None, size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=["US", "CA"],
            )
        )

    def test_empty_allowed_countries_skips_check(self):
        listing = make_listing(country="GB", size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=[],
            )
        )


class TestIsKids(unittest.TestCase):
    def test_is_kids_true_fails(self):
        listing = make_listing(is_kids=True, size=None, price=None)
        self.assertFalse(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=[],
            )
        )

    def test_is_kids_false_passes(self):
        listing = make_listing(is_kids=False, size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=[],
            )
        )

    def test_is_kids_missing_passes(self):
        listing = make_listing(is_kids=None, size=None, price=None)
        self.assertTrue(
            matches_criteria(
                listing,
                required_keywords=[],
                excluded_terms=[],
                target_sizes=[],
                max_price=None,
                allowed_conditions=[],
                allowed_countries=[],
            )
        )


class TestConditionNote(unittest.TestCase):
    def test_brand_new_condition_gives_new_note(self):
        listing = make_listing(condition="brand_new", title="anything at all")
        self.assertEqual(condition_note(listing), "✓ Condition: new (seller-marked)")

    def test_like_new_text_gives_says_note(self):
        listing = make_listing(condition="used_excellent", title="Lululemon speed up shorts, like new")
        self.assertEqual(condition_note(listing), '✓ Condition: says "like new"')

    def test_case_and_hyphen_variant_matches(self):
        listing = make_listing(condition="used_excellent", title="Lululemon speed up shorts, Like-New")
        self.assertEqual(condition_note(listing), '✓ Condition: says "like new"')

    def test_adjacent_punctuation_still_matches_word_boundary(self):
        listing = make_listing(condition="used_excellent", title="Lululemon speed up shorts LIKE NEW!!")
        self.assertEqual(condition_note(listing), '✓ Condition: says "like new"')

    def test_no_positive_phrase_gives_unstated_note(self):
        listing = make_listing(condition="used_excellent", title="Lululemon speed up shorts, worn a few times")
        self.assertEqual(condition_note(listing), "⚠ Condition unstated. Check photos")

    def test_good_condition_only_is_deliberately_not_vouched(self):
        # "good condition" / "vguc" are below the expert's excellent minimum
        # and are intentionally excluded from CONDITION_POSITIVE_PHRASES.
        listing = make_listing(condition="used_excellent", title="Lululemon speed up shorts, good condition")
        self.assertEqual(condition_note(listing), "⚠ Condition unstated. Check photos")

    def test_condition_note_never_changes_matches_criteria(self):
        # Regression guard: condition_note is purely informational. A
        # listing that passes matches_criteria must keep passing regardless
        # of what condition phrases appear in its text, and one that fails
        # must keep failing.
        passing = make_listing(size="0", price=20.0, condition="used_excellent")
        self.assertTrue(matches_criteria(passing))

        for extra_text in (
            "", " like new", " brand new nwt", " good condition only",
            " no flaws flawless mint condition",
        ):
            with_note_text = make_listing(
                size="0", price=20.0, condition="used_excellent",
                title=passing["title"] + extra_text,
            )
            self.assertEqual(
                matches_criteria(passing), matches_criteria(with_note_text),
                f"adding {extra_text!r} changed matches_criteria's result",
            )

        failing = make_listing(size="10", price=20.0, condition="used_excellent")
        self.assertFalse(matches_criteria(failing))
        for extra_text in ("", " like new", " brand new nwt"):
            with_note_text = make_listing(
                size="10", price=20.0, condition="used_excellent",
                title=failing["title"] + extra_text,
            )
            self.assertEqual(
                matches_criteria(failing), matches_criteria(with_note_text),
                f"adding {extra_text!r} changed matches_criteria's result",
            )


if __name__ == "__main__":
    unittest.main()
