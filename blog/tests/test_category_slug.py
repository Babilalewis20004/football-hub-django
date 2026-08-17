from django.test import TestCase

from blog.models import Category


class CategorySlugGenerationTests(TestCase):

    def test_slug_auto_generated_from_name(self):
        category = Category.objects.create(name="Serie A")
        self.assertEqual(category.slug, "serie-a")

    def test_explicit_slug_is_not_overwritten(self):
        category = Category.objects.create(name="Ligue 1", slug="custom-slug")
        self.assertEqual(category.slug, "custom-slug")

    def test_slug_collision_appends_incrementing_counter(self):
        first = Category.objects.create(name="Bundesliga")
        second = Category.objects.create(name="Bundesliga!")
        third = Category.objects.create(name="Bundesliga??")

        self.assertEqual(first.slug, "bundesliga")
        self.assertEqual(second.slug, "bundesliga-1")
        self.assertEqual(third.slug, "bundesliga-2")
