"""
NDA Analyzer Module
Analyzes NDA documents for risk assessment and identifies questionable clauses.
Supports both English and Arabic NDAs.
"""

import os
import json
import base64
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import openai
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class NDAAnalyzer:
    """Analyzes NDA documents for risks and questionable clauses."""

    def __init__(self):
        """Initialize the NDA analyzer with OpenAI client."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o"  # Using GPT-4o for best multilingual support

    def detect_language(self, text: str) -> str:
        """Detect if the document is in English or Arabic."""
        try:
            # Simple heuristic: check for Arabic characters
            arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
            total_chars = sum(1 for c in text if c.isalpha())

            if total_chars == 0:
                return "en"  # Default to English if no text

            arabic_ratio = arabic_chars / total_chars
            return "ar" if arabic_ratio > 0.3 else "en"
        except Exception as e:
            logger.error(f"Error detecting language: {e}")
            return "en"

    def extract_text_from_file(self, file_content: bytes, file_name: str) -> str:
        """
        Extract text from uploaded file.
        For now, assumes text files. Can be extended to support PDF extraction.
        """
        try:
            # Try to decode as UTF-8 text
            text = file_content.decode('utf-8')
            # Remove null bytes and other problematic characters
            text = text.replace('\x00', '').replace('\u0000', '')
            return text
        except UnicodeDecodeError:
            # Try other encodings for Arabic text
            try:
                text = file_content.decode('utf-16')
                # Remove null bytes and other problematic characters
                text = text.replace('\x00', '').replace('\u0000', '')
                return text
            except:
                try:
                    text = file_content.decode('iso-8859-1')
                    # Remove null bytes and other problematic characters
                    text = text.replace('\x00', '').replace('\u0000', '')
                    return text
                except Exception as e:
                    logger.error(f"Error extracting text from file: {e}")
                    return ""

    def analyze_nda(self, nda_text: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze NDA document and return risk assessment.

        Args:
            nda_text: The full text of the NDA document
            language: Optional language code ('en' or 'ar'). Will auto-detect if not provided.

        Returns:
            Dictionary containing:
                - risk_category: 'Safe', 'Needs Attention', or 'Risky'
                - risk_score: 0-100
                - summary: Brief summary of the analysis
                - questionable_clauses: List of concerning clauses with suggestions
                - language: Detected language
        """
        try:
            # Detect language if not provided
            if not language:
                language = self.detect_language(nda_text)

            logger.info(f"Analyzing NDA (language: {language}, length: {len(nda_text)} chars)")

            # Truncate text if too long (roughly 30,000 tokens = ~120,000 chars)
            # This leaves room for system prompt and response
            max_chars = 120000
            if len(nda_text) > max_chars:
                logger.warning(f"NDA text is {len(nda_text)} chars, truncating to {max_chars}")
                nda_text = nda_text[:max_chars] + "\n\n[Document truncated due to length...]"

            # Build prompt based on language
            if language == "ar":
                system_prompt = self._get_arabic_system_prompt()
                user_prompt = self._get_arabic_user_prompt(nda_text)
            else:
                system_prompt = self._get_english_system_prompt()
                user_prompt = self._get_english_user_prompt(nda_text)

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            # Parse response
            analysis = json.loads(response.choices[0].message.content)

            # Ensure required fields
            result = {
                "risk_category": analysis.get("risk_category", "Needs Attention"),
                "risk_score": analysis.get("risk_score", 50),
                "summary": analysis.get("summary", "Analysis completed"),
                "questionable_clauses": analysis.get("questionable_clauses", []),
                "language": language,
                "raw_analysis": analysis
            }

            # Validate risk score
            if not isinstance(result["risk_score"], int) or not (0 <= result["risk_score"] <= 100):
                result["risk_score"] = 50

            # Validate risk category
            valid_categories = ["Safe", "Needs Attention", "Risky"]
            if result["risk_category"] not in valid_categories:
                result["risk_category"] = "Needs Attention"

            logger.info(f"Analysis complete: {result['risk_category']} (score: {result['risk_score']})")
            return result

        except Exception as e:
            logger.error(f"Error analyzing NDA: {e}", exc_info=True)
            raise

    def _get_english_system_prompt(self) -> str:
        """Get system prompt for English NDA analysis."""
        return """You are an expert legal analyst specializing in Non-Disclosure Agreements (NDAs).
Your role is to analyze NDA documents and assess their risk level for the signing party.

You must respond with a JSON object containing:
1. risk_category: One of "Safe", "Needs Attention", or "Risky"
2. risk_score: Integer from 0-100 (0=safest, 100=riskiest)
3. summary: A brief 2-3 sentence summary of the overall assessment
4. questionable_clauses: An array of objects, each containing:
   - clause: The exact text or description of the concerning clause
   - concern: What makes this clause problematic
   - suggestion: Recommended modification or action
   - severity: One of "low", "medium", "high"

Consider these risk factors:
- Overly broad confidentiality scope
- Unreasonable time periods
- Unclear definitions
- One-sided obligations
- Excessive liability or penalties
- Restrictions on employee hiring
- Intellectual property rights concerns
- Lack of exceptions (prior knowledge, public domain, etc.)
- Jurisdiction and dispute resolution clauses"""

    def _get_english_user_prompt(self, nda_text: str) -> str:
        """Get user prompt for English NDA analysis."""
        return f"""Please analyze the following NDA document and provide a comprehensive risk assessment.

NDA Document:
{nda_text}

Provide your analysis as a JSON object with the structure specified in your system instructions."""

    def _get_arabic_system_prompt(self) -> str:
        """Get system prompt for Arabic NDA analysis."""
        return """أنت محلل قانوني خبير متخصص في اتفاقيات عدم الإفصاح (NDAs).
دورك هو تحليل وثائق اتفاقيات عدم الإفصاح وتقييم مستوى المخاطر للطرف الموقع.

يجب أن ترد بكائن JSON يحتوي على:
1. risk_category: واحد من "Safe" أو "Needs Attention" أو "Risky"
2. risk_score: رقم صحيح من 0-100 (0=الأكثر أماناً، 100=الأكثر خطورة)
3. summary: ملخص موجز من 2-3 جمل للتقييم الشامل (بالعربية)
4. questionable_clauses: مصفوفة من الكائنات، كل منها يحتوي على:
   - clause: النص الدقيق أو وصف البند المثير للقلق (بالعربية)
   - concern: ما الذي يجعل هذا البند إشكالياً (بالعربية)
   - suggestion: التعديل أو الإجراء الموصى به (بالعربية)
   - severity: واحد من "low" أو "medium" أو "high"

ضع في اعتبارك عوامل المخاطر التالية:
- نطاق سرية واسع جداً
- فترات زمنية غير معقولة
- تعريفات غير واضحة
- التزامات من جانب واحد
- مسؤولية أو عقوبات مفرطة
- قيود على توظيف الموظفين
- مخاوف حقوق الملكية الفكرية
- عدم وجود استثناءات (معرفة مسبقة، مجال عام، إلخ)
- بنود الاختصاص القضائي وحل النزاعات"""

    def _get_arabic_user_prompt(self, nda_text: str) -> str:
        """Get user prompt for Arabic NDA analysis."""
        return f"""يرجى تحليل وثيقة اتفاقية عدم الإفصاح التالية وتقديم تقييم شامل للمخاطر.

وثيقة اتفاقية عدم الإفصاح:
{nda_text}

قدم تحليلك ككائن JSON بالهيكل المحدد في تعليمات النظام الخاصة بك."""

    def analyze_batch(self, nda_documents: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
        """
        Analyze multiple NDA documents in batch.

        Args:
            nda_documents: List of tuples (nda_id, nda_text)

        Returns:
            List of analysis results with nda_id included
        """
        results = []
        for nda_id, nda_text in nda_documents:
            try:
                analysis = self.analyze_nda(nda_text)
                analysis["nda_id"] = nda_id
                results.append(analysis)
            except Exception as e:
                logger.error(f"Error analyzing NDA {nda_id}: {e}")
                results.append({
                    "nda_id": nda_id,
                    "error": str(e),
                    "risk_category": "Needs Attention",
                    "risk_score": 50,
                    "summary": f"Analysis failed: {str(e)}",
                    "questionable_clauses": []
                })

        return results
