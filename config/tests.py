import json

from django.test import TestCase, Client
from django.urls import reverse


class CspReportViewTests(TestCase):

    def setUp(self):
        self.client = Client()

    def test_valid_csp_report_returns_204(self):
        payload = json.dumps({"csp-report": {"violated-directive": "script-src"}})
        response = self.client.post(
            reverse("csp_report"),
            data=payload,
            content_type="application/csp-report",
        )
        self.assertEqual(response.status_code, 204)

    def test_malformed_json_still_returns_204(self):
        response = self.client.post(
            reverse("csp_report"),
            data="not-json",
            content_type="application/csp-report",
        )
        self.assertEqual(response.status_code, 204)

    def test_get_not_allowed(self):
        response = self.client.get(reverse("csp_report"))
        self.assertEqual(response.status_code, 405)

    def test_csrf_exempt(self):
        csrf_client = Client(enforce_csrf_checks=True)
        payload = json.dumps({"csp-report": {}})
        response = csrf_client.post(
            reverse("csp_report"),
            data=payload,
            content_type="application/csp-report",
        )
        self.assertEqual(response.status_code, 204)


class RobotsTxtViewTests(TestCase):

    def setUp(self):
        self.client = Client()

    def test_robots_txt_returns_200_plain_text(self):
        response = self.client.get(reverse("robots_txt"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")

    def test_robots_txt_disallows_admin_and_references_sitemap(self):
        response = self.client.get(reverse("robots_txt"))
        content = response.content.decode()
        self.assertIn("Disallow: /admin/", content)
        self.assertIn("Sitemap: ", content)
        self.assertIn("/sitemap.xml", content)

    def test_post_not_allowed(self):
        response = self.client.post(reverse("robots_txt"))
        self.assertEqual(response.status_code, 405)
