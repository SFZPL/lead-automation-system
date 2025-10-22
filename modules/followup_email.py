import re
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


class FollowUpEmailBuilder:
    """Compose personalized follow-up emails for unanswered calls."""

    def __init__(
        self,
        sender_name: str,
        value_proposition: str,
        calendar_link: Optional[str] = None,
        sender_title: Optional[str] = None,
        sender_email: Optional[str] = None,
        proposed_meeting_text: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        openai_model: Optional[str] = None,
        use_llm: bool = True,
    ) -> None:
        self.sender_name = sender_name or 'Team'
        self.value_proposition = (value_proposition or '').strip()
        self.calendar_link = calendar_link
        self.sender_title = sender_title
        self.sender_email = sender_email
        self.proposed_meeting_text = (
            proposed_meeting_text.strip() if proposed_meeting_text else ''
        )
        self.use_llm = bool(use_llm and openai_api_key)
        self.openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        self.openai_model = openai_model or 'gpt-5-mini'
        logger.info(f"FollowUpEmailBuilder initialized: use_llm={self.use_llm}, has_client={self.openai_client is not None}, model={self.openai_model}")

    @staticmethod
    def _first_name(full_name: Optional[str]) -> str:
        if not full_name:
            return 'there'
        parts = [part for part in full_name.strip().split() if part]
        return parts[0] if parts else 'there'

    @staticmethod
    def _clean_text(value: Optional[str]) -> str:
        if not value:
            return ''
        stripped = re.sub(r'<[^>]+>', ' ', value)
        stripped = re.sub(r'\s+', ' ', stripped)
        return stripped.strip()

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            cleaned = value.replace('Z', '+00:00')
            try:
                return datetime.fromisoformat(cleaned)
            except ValueError:
                return None
        return None

    @staticmethod
    def _format_called_at(value: Optional[datetime]) -> Optional[str]:
        if not value:
            return None
        return value.strftime('%A, %B %d').replace(' 0', ' ')

    def _build_with_llm(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Generate personalized email using LLM with enriched Odoo data."""
        full_name = (
            context.get('contact_name')
            or context.get('Full Name')
            or context.get('full_name')
            or context.get('name')
        )
        first_name = self._first_name(full_name)
        company = context.get('partner_name') or context.get('Company Name') or context.get('company')
        stage = context.get('stage_name')
        description = self._clean_text(context.get('description') or context.get('notes'))
        job_title = context.get('job_title') or context.get('function')
        last_called_dt = context.get('last_called_at_dt') or context.get('last_called_at')
        last_called_dt = self._parse_datetime(last_called_dt)
        called_at_str = self._format_called_at(last_called_dt)

        # Build context for LLM
        prompt = f"""You are {self.sender_name}, a {self.sender_title or 'sales professional'} at PrezLab. Write a short, personalized follow-up email for {first_name} who didn't answer your call.

CONTEXT ABOUT THE LEAD:
- Full Name: {full_name or 'Unknown'}
- Company: {company or 'Unknown'}
- Job Title: {job_title or 'Unknown'}
- Current Stage: {stage or 'Unknown'}
- Last Called: {called_at_str or 'recently'}
{f'- Notes from Odoo: {description}' if description else ''}

VALUE PROPOSITION: {self.value_proposition}

INSTRUCTIONS:
1. Keep the email concise (3-4 short paragraphs max)
2. Be warm, professional, and helpful - not pushy
3. Reference specific details from the context to show you've done your homework
4. Mention that you tried calling on {called_at_str or 'recently'} but they didn't answer
5. If there are notes from Odoo, weave them naturally into the conversation
6. Focus on how PrezLab can specifically help their company/role
7. End with a soft call-to-action to book a 15-minute call
8. Do NOT include a subject line - just the email body
9. Do NOT include signature - just the message body
10. Do NOT use em dashes (—) in the email. Use regular hyphens (-) or commas instead.

TONE: Conversational, consultative, genuinely helpful"""

        try:
            logger.info(f"Calling OpenAI with model={self.openai_model}")
            logger.info(f"Prompt length: {len(prompt)} characters")
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": "You are an expert at writing personalized, high-converting sales follow-up emails that feel authentic and helpful, not salesy."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=2000
            )

            logger.info(f"OpenAI response: {response}")
            body = response.choices[0].message.content
            logger.info(f"Raw body from LLM: {repr(body)}")
            body = body.strip() if body else ""
            logger.info(f"LLM generated email body length: {len(body)} characters")
            logger.info(f"LLM generated email body preview: {body[:200] if body else 'EMPTY'}")

            # Add calendar link if provided
            if self.calendar_link:
                body += f"\n\n{self.calendar_link}"
            elif self.proposed_meeting_text:
                body += f"\n\n{self.proposed_meeting_text}"

            # Add signature
            signature_lines = ["\n", self.sender_name]
            if self.sender_title:
                signature_lines.append(self.sender_title)
            if self.sender_email:
                signature_lines.append(self.sender_email)
            body += '\n'.join(signature_lines)

            subject = f"Sorry I missed you, {first_name}" if first_name != 'there' else "Sorry I missed your call"

            return {
                'subject': subject,
                'body': body,
            }

        except Exception as e:
            logger.error(f"LLM email generation failed: {e}. Falling back to template.")
            return self._build_template(context)

    def _build_template(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Original template-based email generation (fallback)."""
        full_name = (
            context.get('contact_name')
            or context.get('Full Name')
            or context.get('full_name')
            or context.get('name')
        )
        first_name = self._first_name(full_name)
        company = context.get('partner_name') or context.get('Company Name') or context.get('company')
        stage = context.get('stage_name')
        description = self._clean_text(context.get('description') or context.get('notes'))
        last_called_dt = context.get('last_called_at_dt') or context.get('last_called_at')
        last_called_dt = self._parse_datetime(last_called_dt)
        called_at_str = self._format_called_at(last_called_dt)

        subject = f"Sorry I missed you, {first_name}" if first_name != 'there' else "Sorry I missed your call"

        lines = [f"Hi {first_name},", ""]

        if called_at_str:
            lines.append(f"I gave you a quick call on {called_at_str}, but it went to voicemail.")
        else:
            lines.append("I gave you a quick call earlier, but it went to voicemail.")

        opportunity_name = context.get('name') or context.get('opportunity_name')
        if opportunity_name:
            lines.append(f"I wanted to follow up on {opportunity_name} and keep things moving.")
        elif company:
            lines.append(f"I wanted to follow up because I think what we do at PrezLab could help {company} right away.")
        else:
            lines.append("I wanted to follow up in case there is anything else you needed from me.")

        if self.value_proposition:
            value_line = self.value_proposition
            if company:
                value_line = value_line.replace('{company}', company)
            lines.append(value_line)

        if description:
            lines.append("")
            lines.append(f"My notes from our last touchpoint: {description}.")

        if stage:
            lines.append("")
            lines.append(f"It looks like you are currently in the '{stage}' stage - happy to help get you what you need to progress.")

        lines.append("")
        if self.proposed_meeting_text:
            lines.append(self.proposed_meeting_text)
        elif self.calendar_link:
            lines.append("Does a quick 15-minute call this week work for you? You can grab a slot that fits here:")
        else:
            lines.append("Does a quick 15-minute call this week work for you?")

        if self.calendar_link:
            lines.append(self.calendar_link)

        lines.append("")
        signature = [self.sender_name]
        if self.sender_title:
            signature.append(self.sender_title)
        if self.sender_email:
            signature.append(self.sender_email)

        lines.extend(signature)

        body = '\n'.join(lines)

        return {
            'subject': subject,
            'body': body,
        }

    def build(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Build personalized email - use LLM if available, otherwise template."""
        logger.info(f"Building email: use_llm={self.use_llm}, has_client={self.openai_client is not None}")
        if self.use_llm and self.openai_client:
            logger.info("Using LLM for email generation")
            return self._build_with_llm(context)
        else:
            logger.info("Using template for email generation")
            return self._build_template(context)

