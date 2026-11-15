"""Small, non-secret provider diagnostics shared by CLI, index and browser."""
from __future__ import annotations

CATEGORIES = {
    'http_not_found', 'access_denied', 'rate_limited', 'provider_error',
    'network_timeout', 'network_error', 'response_too_large', 'invalid_json',
    'schema_error', 'redirect_rejected', 'partial_details', 'unknown_error',
}


class SourceError(RuntimeError):
    def __init__(self, category, *, http_status=None, retry_after=None):
        self.category = category if category in CATEGORIES else 'unknown_error'
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        self.retryable = self.category in {'rate_limited', 'provider_error', 'network_timeout', 'network_error'}
        self.retry_after = min(86400, max(0, retry_after)) if type(retry_after) in {int, float} else None
        super().__init__(self.category)


def diagnostic(exc):
    # Do not copy exception text, URLs, bodies, headers or private search strings.
    if isinstance(exc, SourceError):
        return {'error_category': exc.category, 'http_status': exc.http_status, 'retryable': exc.retryable,
                'retry_after_seconds': exc.retry_after}
    return {'error_category': 'unknown_error', 'http_status': None, 'retryable': False}


class FeedResult(list):
    """Keep list compatibility while carrying bounded, allowlisted scan facts."""
    def __init__(self, jobs=(), *, complete=True, **report):
        super().__init__(jobs)
        self.report = {'complete': bool(complete)}
        for key in ('list_count', 'details_attempted', 'details_succeeded', 'response_bytes', 'budget_bytes_used', 'details_failed', 'details_pending'):
            value = report.get(key)
            if type(value) is int and value >= 0:
                self.report[key] = value
        if report.get('error_category') in CATEGORIES:
            self.report['error_category'] = report['error_category']
        if report.get('detail_error_category') in CATEGORIES:
            self.report['detail_error_category'] = report['detail_error_category']
        status = report.get('detail_http_status')
        if type(status) is int and 100 <= status <= 599:
            self.report['detail_http_status'] = status
        retry_after = report.get('retry_after_seconds')
        if type(retry_after) in {int, float} and 0 <= retry_after <= 86400:
            self.report['retry_after_seconds'] = retry_after


def feed_report(jobs):
    if isinstance(jobs, FeedResult):
        return dict(jobs.report)
    return {'complete': True, 'list_count': len(jobs)}
