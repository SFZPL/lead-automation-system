import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, Generator, Iterable, List, Optional

import requests

from config import Config

logger = logging.getLogger(__name__)


class ApolloClient:
    """Thin wrapper around Apollo's REST API for call retrieval."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: int = 30,
        send_api_key_in_body: Optional[bool] = None,
    ) -> None:
        self.config = Config()
        self.api_key = api_key or self.config.APOLLO_API_KEY
        self.base_url = (base_url or self.config.APOLLO_BASE_URL).rstrip('/')
        self.session = session or requests.Session()
        self.timeout = timeout
        self.send_api_key_in_body = (
            self.config.APOLLO_API_KEY_IN_BODY if send_api_key_in_body is None else send_api_key_in_body
        )

        if not self.api_key:
            logger.warning("Apollo API key missing. Client will not be able to authenticate.")

        self.session.headers.setdefault('Content-Type', 'application/json')
        if self.api_key:
            # Apollo uses Cache-Control and X-Api-Key for authentication
            self.session.headers.setdefault('Cache-Control', 'no-cache')
            self.session.headers.setdefault('X-Api-Key', self.api_key)

    def _build_url(self, path: str) -> str:
        if not path.startswith('/'):
            path = f'/{path}'
        return f'{self.base_url}{path}'

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError('Apollo API key is not configured')

        body = dict(payload)
        if self.send_api_key_in_body:
            body.setdefault('api_key', self.api_key)

        url = self._build_url(path)
        start = time.monotonic()
        response = self.session.post(url, json=body, timeout=self.timeout)
        duration = time.monotonic() - start
        logger.info('POST %s status=%s duration=%.2fs', url, response.status_code, duration)
        if response.status_code >= 400:
            logger.warning('Apollo API error response: %s', response.text[:500])
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError('Unexpected response type from Apollo API')
        return data

    def iter_calls(
        self,
        dispositions: Optional[Iterable[str]] = None,
        updated_after: Optional[datetime] = None,
        per_page: int = 25,
        max_pages: int = 5,
    ) -> Generator[Dict[str, Any], None, None]:
        """Yield call records that match the provided filters."""

        page = 1
        while page <= max_pages:
            payload: Dict[str, Any] = {
                'page': page,
                'per_page': per_page,
            }
            if dispositions:
                disposition_list = [value for value in dispositions if value]
                if disposition_list:
                    payload['q_dialer_disposition'] = disposition_list
            if updated_after:
                payload['q_start_date'] = updated_after.strftime('%Y-%m-%d')

            data = self._post('/phone_calls/search', payload)
            calls = data.get('phone_calls') or data.get('calls') or data.get('data') or []
            if not isinstance(calls, list) or not calls:
                break

            for call in calls:
                if isinstance(call, dict):
                    yield call

            pagination = data.get('pagination') or {}
            total_pages = pagination.get('total_pages') or data.get('total_pages')
            if total_pages and page >= total_pages:
                break
            if len(calls) < per_page:
                break
            page += 1

    def iter_no_answer_calls(
        self,
        dispositions: Optional[Iterable[str]] = None,
        updated_after: Optional[datetime] = None,
        per_page: int = 25,
        max_pages: int = 5,
    ) -> Generator[Dict[str, Any], None, None]:
        """Yield calls considered no-answer based on disposition list."""
        yield from self.iter_calls(
            dispositions=dispositions or self.config.APOLLO_NO_ANSWER_DISPOSITIONS,
            updated_after=updated_after,
            per_page=per_page,
            max_pages=max_pages,
        )

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value)
            except (OSError, ValueError):
                return None
        if isinstance(value, str):
            cleaned = value.replace('Z', '+00:00')
            try:
                return datetime.fromisoformat(cleaned)
            except ValueError:
                return None
        return None

    def call_to_contact_summary(self, call: Dict[str, Any]) -> Dict[str, Any]:
        person = call.get('person') or {}
        contact = call.get('contact') or {}
        account = call.get('account') or {}

        email = (
            person.get('email')
            or person.get('email_address')
            or contact.get('email')
            or contact.get('email_address')
            or call.get('person_email')
            or call.get('callable_contact_email')
        )
        full_name = (
            person.get('name')
            or contact.get('name')
            or ' '.join(filter(None, [person.get('first_name'), person.get('last_name')]))
            or ' '.join(filter(None, [contact.get('first_name'), contact.get('last_name')]))
        )
        job_title = person.get('title') or contact.get('title')
        company = account.get('name') or person.get('organization_name') or contact.get('account_name')
        called_at = (
            call.get('called_at')
            or call.get('created_at')
            or call.get('updated_at')
            or call.get('start_time')
        )
        called_at_dt = self._parse_datetime(called_at)

        summary = {
            'call_id': call.get('id'),
            'call_disposition': call.get('disposition') or call.get('call_disposition'),
            'call_direction': call.get('direction'),
            'duration_seconds': call.get('duration') or call.get('duration_seconds'),
            'notes': call.get('notes') or call.get('note'),
            'last_called_at': called_at_dt.isoformat() if called_at_dt else None,
            'last_called_at_dt': called_at_dt,
            'email': email,
            'full_name': full_name,
            'job_title': job_title,
            'company': company,
            'phone_number': call.get('to_number') or call.get('phone_number') or call.get('dialed_number'),
            'person_id': person.get('id') or call.get('person_id'),
            'contact_id': contact.get('id') or call.get('contact_id'),
            'account_id': account.get('id') or call.get('account_id'),
        }

        return summary

    def fetch_no_answer_contacts(
        self,
        limit: int = 20,
        dispositions: Optional[Iterable[str]] = None,
        updated_after: Optional[datetime] = None,
        per_page: Optional[int] = None,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return unique contacts for missed/no-answer calls."""

        per_page = per_page or self.config.APOLLO_PAGE_SIZE
        max_pages = max_pages or self.config.APOLLO_MAX_PAGES
        dispositions = dispositions or self.config.APOLLO_NO_ANSWER_DISPOSITIONS

        unique: Dict[str, Dict[str, Any]] = {}
        for call in self.iter_no_answer_calls(
            dispositions=dispositions,
            updated_after=updated_after,
            per_page=per_page,
            max_pages=max_pages,
        ):
            summary = self.call_to_contact_summary(call)
            email = (summary.get('email') or '').strip().lower()
            if not email:
                continue

            current = unique.get(email)
            current_dt = current.get('last_called_at_dt') if current else None
            candidate_dt = summary.get('last_called_at_dt')
            if current is None or (
                candidate_dt and (not current_dt or candidate_dt > current_dt)
            ):
                unique[email] = summary

            if limit and len(unique) >= limit:
                break

        return list(unique.values())

    def fetch_recent_calls(
        self,
        limit: int = 20,
        dispositions: Optional[Iterable[str]] = None,
        updated_after: Optional[datetime] = None,
        per_page: Optional[int] = None,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return recent calls ordered by called_at desc."""
        per_page = per_page or self.config.APOLLO_PAGE_SIZE
        max_pages = max_pages or self.config.APOLLO_MAX_PAGES

        results: List[Dict[str, Any]] = []
        for call in self.iter_calls(
            dispositions=dispositions,
            updated_after=updated_after,
            per_page=per_page,
            max_pages=max_pages,
        ):
            results.append(call)
            if limit and len(results) >= limit:
                break
        return results

