"""
NDA Analyzer Module
Analyzes NDA documents for risk assessment and identifies questionable clauses.
Supports both English and Arabic NDAs.
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from openai import OpenAI
import logging

from config import Config

logger = logging.getLogger(__name__)


class NDAAnalyzer:
    """Analyzes NDA documents for risks and questionable clauses."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize the NDA analyzer with OpenAI client."""
        self.config = config or Config()
        if not self.config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for NDA analysis")

        self.client = OpenAI(
            api_key=self.config.OPENAI_API_KEY,
            base_url=self.config.OPENAI_API_BASE,
        )
        self.model = self.config.OPENAI_MODEL

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

    def _chunk_text(self, text: str, max_chunk_chars: int = 80000) -> List[str]:
        """Split text into chunks that fit within token limits."""
        # Split by paragraphs first to keep context
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = []
        current_length = 0

        for para in paragraphs:
            para_length = len(para)
            if current_length + para_length > max_chunk_chars and current_chunk:
                # Save current chunk and start new one
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_length = para_length
            else:
                current_chunk.append(para)
                current_length += para_length + 2  # +2 for \n\n

        # Add final chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        return chunks

    def analyze_nda(self, nda_text: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze NDA document and return risk assessment.
        Uses chunked analysis for large documents to ensure nothing is skipped.

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

            # Check if we need to use chunked analysis
            max_single_chars = 80000  # Conservative limit for single-pass analysis

            if len(nda_text) > max_single_chars:
                logger.info(f"Document is large ({len(nda_text)} chars), using chunked analysis")
                return self._analyze_nda_chunked(nda_text, language)
            else:
                logger.info("Document size is manageable, using single-pass analysis")
                return self._analyze_nda_single(nda_text, language)

        except Exception as e:
            logger.error(f"Error analyzing NDA: {e}", exc_info=True)
            raise

    def _analyze_nda_single(self, nda_text: str, language: str) -> Dict[str, Any]:
        """Analyze entire NDA in a single pass."""
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

    def _analyze_nda_chunked(self, nda_text: str, language: str) -> Dict[str, Any]:
        """Analyze large NDA in chunks to ensure complete coverage."""
        chunks = self._chunk_text(nda_text)
        logger.info(f"Split document into {len(chunks)} chunks for analysis")

        all_clauses = []
        chunk_summaries = []
        chunk_scores = []

        # Analyze each chunk
        for i, chunk in enumerate(chunks):
            logger.info(f"Analyzing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")

            try:
                chunk_analysis = self._analyze_nda_single(chunk, language)

                # Collect questionable clauses from this chunk
                chunk_clauses = chunk_analysis.get("questionable_clauses", [])
                for clause in chunk_clauses:
                    clause["chunk"] = i + 1  # Tag with chunk number
                all_clauses.extend(chunk_clauses)

                # Collect chunk summary and score
                chunk_summaries.append(chunk_analysis.get("summary", ""))
                chunk_scores.append(chunk_analysis.get("risk_score", 50))

            except Exception as e:
                logger.error(f"Error analyzing chunk {i+1}: {e}")
                chunk_summaries.append(f"Error analyzing section {i+1}")
                chunk_scores.append(50)

        # Combine results
        avg_score = int(sum(chunk_scores) / len(chunk_scores)) if chunk_scores else 50
        max_score = max(chunk_scores) if chunk_scores else 50

        # Use max score (worst case) for overall risk
        overall_score = max_score

        # Determine risk category based on worst chunk
        if overall_score >= 70:
            risk_category = "Risky"
        elif overall_score >= 40:
            risk_category = "Needs Attention"
        else:
            risk_category = "Safe"

        # Combine summaries
        combined_summary = f"Analyzed {len(chunks)} sections of the document. " + " ".join(chunk_summaries[:3])
        if len(combined_summary) > 500:
            combined_summary = combined_summary[:497] + "..."

        logger.info(f"Chunked analysis complete: {risk_category} (score: {overall_score}, {len(all_clauses)} issues found)")

        return {
            "risk_category": risk_category,
            "risk_score": overall_score,
            "summary": combined_summary,
            "questionable_clauses": all_clauses,
            "language": language,
            "raw_analysis": {
                "chunks_analyzed": len(chunks),
                "chunk_scores": chunk_scores,
                "average_score": avg_score,
                "max_score": max_score
            }
        }

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
