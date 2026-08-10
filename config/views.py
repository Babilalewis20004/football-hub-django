import json
import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

logger = logging.getLogger("csp")


@csrf_exempt
@require_POST
def csp_report_view(request):
    """
    Collects Content-Security-Policy-Report-Only violation reports.

    Browsers POST these without a CSRF token, so this endpoint has to be
    exempt from CSRF protection. It only ever logs the body it's given
    (see logs/csp_violations.log) — reviewing that log is how violations
    get turned into policy fixes before the policy is switched from
    Report-Only to enforced.
    """
    try:
        report = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        logger.warning("Received unparseable CSP report from %s", request.META.get("REMOTE_ADDR"))
        return HttpResponse(status=204)

    logger.info("CSP violation: %s", json.dumps(report))
    return HttpResponse(status=204)


@require_GET
def robots_txt(request):
    """
    Points crawlers at the sitemap and steers them away from account,
    dashboard, chat and admin paths that carry no SEO value and are
    already login-gated.
    """
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /dashboard/",
        "Disallow: /saved/",
        "Disallow: /post/create/",
        "Disallow: /search/",
        "Disallow: /users/",
        "Disallow: /login/",
        "Disallow: /logout/",
        "Disallow: /password-reset/",
        "Disallow: /chat/",
        "Disallow: /csp-report/",
        "",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
