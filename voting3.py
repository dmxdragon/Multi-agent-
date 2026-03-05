import re
import asyncio
import aiohttp
import os
import traceback
import logging
from enum import Enum
from datetime import datetime
from typing import Optional
from logger3 import get_logger, log_info, log_error, log_success, log_warn

# ==================== Logger ====================
logger = get_logger("MultiAgent.Voting")


# ==================== Vote Types ====================

class VoteType(Enum):
    APPROVE      = "تایید"
    REJECT       = "رد"
    NEEDS_REVIEW = "نیاز به بررسی"
    CRITICAL     = "بحرانی"
    MINOR        = "جزئی"


class Severity(Enum):
    CRITICAL = 4
    HIGH     = 3
    MEDIUM   = 2
    LOW      = 1


# ==================== Issue ====================

class Issue:
    def __init__(
        self,
        title: str,
        description: str,
        severity: Severity,
        found_by: str,
        line_number: int = None,
        suggestion: str = None,
        tags: list[str] = None
    ):
        self.title = title
        self.description = description
        self.severity = severity
        self.found_by = found_by
        self.line_number = line_number
        self.suggestion = suggestion
        self.tags = tags or []
        self.timestamp = datetime.now().strftime("%H:%M:%S")
        self.confirmed_by: list[str] = []
        self.rejected_by: list[str] = []

    def confirm(self, agent_name: str):
        if agent_name not in self.confirmed_by:
            self.confirmed_by.append(agent_name)

    def reject(self, agent_name: str):
        if agent_name not in self.rejected_by:
            self.rejected_by.append(agent_name)

    @property
    def confidence(self) -> float:
        total = len(self.confirmed_by) + len(self.rejected_by)
        if total == 0:
            return 0.5
        return len(self.confirmed_by) / total

    @property
    def is_confirmed(self) -> bool:
        return self.confidence > 0.5

    def __repr__(self):
        return (
            f"[{self.severity.name}] {self.title} "
            f"| by: {self.found_by} "
            f"| confirmed: {len(self.confirmed_by)} "
            f"| rejected: {len(self.rejected_by)}"
        )


# ==================== Vote ====================

class Vote:
    def __init__(
        self,
        agent_name: str,
        vote_type: VoteType,
        confidence: float,
        reasoning: str,
        issues: list[Issue] = None,
        suggestions: list[str] = None,
        weight: float = 1.0
    ):
        self.agent_name = agent_name
        self.vote_type = vote_type
        self.confidence = max(0.0, min(1.0, confidence))
        self.reasoning = reasoning
        self.issues = issues or []
        self.suggestions = suggestions or []
        self.weight = weight
        self.timestamp = datetime.now().strftime("%H:%M:%S")

    @property
    def weighted_score(self) -> float:
        scores = {
            VoteType.APPROVE:      1.0,
            VoteType.MINOR:        0.7,
            VoteType.NEEDS_REVIEW: 0.5,
            VoteType.REJECT:       0.2,
            VoteType.CRITICAL:     0.0
        }
        base_score = scores.get(self.vote_type, 0.5)
        return base_score * self.confidence * self.weight

    def __repr__(self):
        return (
            f"{self.agent_name}: {self.vote_type.value} "
            f"(confidence: {self.confidence:.0%}, "
            f"weight: {self.weight})"
        )


# ==================== Voting Result ====================

class VotingResult:
    def __init__(
        self,
        votes: list[Vote],
        final_verdict: VoteType,
        consensus_score: float,
        confirmed_issues: list[Issue],
        all_suggestions: list[str]
    ):
        self.votes = votes
        self.final_verdict = final_verdict
        self.consensus_score = consensus_score
        self.confirmed_issues = confirmed_issues
        self.all_suggestions = all_suggestions
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @property
    def has_consensus(self) -> bool:
        return self.consensus_score >= 0.7

    @property
    def critical_issues(self) -> list[Issue]:
        return [i for i in self.confirmed_issues if i.severity == Severity.CRITICAL]

    @property
    def high_issues(self) -> list[Issue]:
        return [i for i in self.confirmed_issues if i.severity == Severity.HIGH]

    def format_report(self) -> str:
        lines = []
        lines.append("\n" + "═" * 60)
        lines.append("🗳️  نتیجه رای‌گیری Multi-Agent")
        lines.append("═" * 60)

        emoji = {
            VoteType.APPROVE:      "✅",
            VoteType.MINOR:        "🟡",
            VoteType.NEEDS_REVIEW: "🔵",
            VoteType.REJECT:       "❌",
            VoteType.CRITICAL:     "🚨"
        }
        verdict_emoji = emoji.get(self.final_verdict, "❓")
        lines.append(f"\n{verdict_emoji} حکم نهایی: {self.final_verdict.value}")
        lines.append(f"📊 امتیاز اجماع: {self.consensus_score:.0%}")

        if self.has_consensus:
            lines.append("🤝 اتفاق نظر: بله")
        else:
            lines.append("⚡ اتفاق نظر: خیر — agent‌ها اختلاف نظر دارن")

        lines.append(f"\n{'─' * 40}")
        lines.append("🤖 رای‌های فردی:")
        for vote in self.votes:
            e = emoji.get(vote.vote_type, "❓")
            lines.append(
                f"  {e} {vote.agent_name}: {vote.vote_type.value} "
                f"({vote.confidence:.0%} مطمئن)"
            )
            lines.append(f"     دلیل: {vote.reasoning[:100]}...")

        if self.confirmed_issues:
            lines.append(f"\n{'─' * 40}")
            lines.append(f"🔍 مشکلات تایید شده ({len(self.confirmed_issues)} مورد):")

            sorted_issues = sorted(
                self.confirmed_issues,
                key=lambda x: x.severity.value,
                reverse=True
            )

            severity_emoji = {
                Severity.CRITICAL: "🚨",
                Severity.HIGH:     "🔴",
                Severity.MEDIUM:   "🟡",
                Severity.LOW:      "🟢"
            }

            for issue in sorted_issues:
                se = severity_emoji.get(issue.severity, "⚪")
                lines.append(f"\n  {se} [{issue.severity.name}] {issue.title}")
                lines.append(f"     {issue.description[:150]}")
                if issue.suggestion:
                    lines.append(f"     💡 پیشنهاد: {issue.suggestion[:100]}")
                lines.append(
                    f"     تایید: {', '.join(issue.confirmed_by)} "
                    f"| اطمینان: {issue.confidence:.0%}"
                )

        if self.all_suggestions:
            lines.append(f"\n{'─' * 40}")
            lines.append(f"💡 پیشنهادات ({len(self.all_suggestions)} مورد):")
            for i, suggestion in enumerate(self.all_suggestions[:10], 1):
                lines.append(f"  {i}. {suggestion[:150]}")

        lines.append("\n" + "═" * 60)
        return "\n".join(lines)


# ==================== Base Voting Agent ====================

# الگوی regex برای parse کردن مشکلات — یه بار compile میشه
_ISSUE_PATTERN = re.compile(
    r'\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s*(.+?):\s*(.+?)(?:\|\s*(.+))?$',
    re.IGNORECASE
)


class VotingAgent:
    def __init__(
        self,
        name: str,
        role: str,
        specialty_tags: list[str],
        weight: float = 1.0
    ):
        self.name = name
        self.role = role
        self.specialty_tags = specialty_tags
        self.weight = weight
        self._session: aiohttp.ClientSession = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _call_api(self, prompt: str) -> str:
        raise NotImplementedError

    def _parse_severity(self, text: str) -> Severity:
        text_lower = text.lower()
        if any(w in text_lower for w in ["critical", "بحرانی", "خطرناک", "فوری"]):
            return Severity.CRITICAL
        elif any(w in text_lower for w in ["high", "مهم", "جدی"]):
            return Severity.HIGH
        elif any(w in text_lower for w in ["medium", "متوسط", "معمولی"]):
            return Severity.MEDIUM
        return Severity.LOW

    def _parse_vote_type(self, text: str) -> VoteType:
        text_lower = text.lower()
        if any(w in text_lower for w in ["critical", "بحرانی", "خطر جدی"]):
            return VoteType.CRITICAL
        elif any(w in text_lower for w in ["reject", "رد", "مشکل جدی", "قبول نیست"]):
            return VoteType.REJECT
        elif any(w in text_lower for w in ["minor", "جزئی", "کوچک"]):
            return VoteType.MINOR
        elif any(w in text_lower for w in ["approve", "تایید", "مشکلی نیست", "خوبه"]):
            return VoteType.APPROVE
        return VoteType.NEEDS_REVIEW

    def _parse_confidence(self, text: str) -> float:
        # دنبال درصد بگرد
        percentages = re.findall(r'(\d+)%', text)
        if percentages:
            return int(percentages[0]) / 100
        text_lower = text.lower()
        if any(w in text_lower for w in ["مطمئنم", "قطعاً", "definitely", "certain"]):
            return 0.95
        elif any(w in text_lower for w in ["احتمالاً", "probably", "likely"]):
            return 0.75
        elif any(w in text_lower for w in ["شاید", "maybe", "possibly"]):
            return 0.5
        return 0.7

    async def cast_vote(
        self,
        content: str,
        existing_issues: list[Issue] = None
    ) -> Vote:
        log_info(logger, self.name, "در حال رای دادن...")

        existing_context = ""
        if existing_issues:
            existing_context = "\n\nمشکلاتی که agent‌های دیگه پیدا کردن:\n"
            for issue in existing_issues:
                existing_context += f"- [{issue.severity.name}] {issue.title}: {issue.description[:100]}\n"

        prompt = f"""
تو یه agent متخصص در {self.role} هستی.
تخصص‌های تو: {', '.join(self.specialty_tags)}

محتوایی که باید بررسی کنی:
{content}
{existing_context}

وظیفه تو:
1. یه رای بده: APPROVE / MINOR / NEEDS_REVIEW / REJECT / CRITICAL
2. بگو چقدر مطمئنی (مثلاً 85%)
3. دلیل رایت رو بگو
4. مشکلاتی که پیدا کردی رو لیست کن (هر مشکل در یه خط با فرمت: [SEVERITY] عنوان: توضیح | پیشنهاد)
5. پیشنهادات بهبود رو بده

جواب رو ساختارمند بده.
"""

        try:
            response = await self._call_api(prompt)

            vote_type = self._parse_vote_type(response)
            confidence = self._parse_confidence(response)
            issues = self._extract_issues(response)
            suggestions = self._extract_suggestions(response)

            vote = Vote(
                agent_name=self.name,
                vote_type=vote_type,
                confidence=confidence,
                reasoning=response[:300],
                issues=issues,
                suggestions=suggestions,
                weight=self.weight
            )

            log_success(logger, self.name, f"رای داد: {vote_type.value} ({confidence:.0%})")
            return vote

        except Exception as e:
            log_error(logger, self.name, "خطا در رای دادن", e)
            return Vote(
                agent_name=self.name,
                vote_type=VoteType.NEEDS_REVIEW,
                confidence=0.0,
                reasoning=f"خطا: {e}",
                weight=self.weight
            )

    def _extract_issues(self, response: str) -> list[Issue]:
        """مشکلات رو از جواب agent استخراج کن"""
        issues = []
        severity_map = {
            "CRITICAL": Severity.CRITICAL,
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MEDIUM,
            "LOW": Severity.LOW
        }

        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue

            match = _ISSUE_PATTERN.search(line)
            if match:
                severity_str = match.group(1).upper()
                title = match.group(2).strip()
                description = match.group(3).strip()
                suggestion = match.group(4).strip() if match.group(4) else None

                issue = Issue(
                    title=title,
                    description=description,
                    severity=severity_map.get(severity_str, Severity.MEDIUM),
                    found_by=self.name,
                    suggestion=suggestion,
                    tags=self.specialty_tags
                )
                issues.append(issue)

        return issues

    def _extract_suggestions(self, response: str) -> list[str]:
        """پیشنهادات رو از جواب استخراج کن"""
        suggestions = []
        lines = response.split('\n')
        in_suggestions = False

        for line in lines:
            line = line.strip()
            if any(w in line.lower() for w in ["پیشنهاد", "suggestion", "بهبود", "improvement"]):
                in_suggestions = True
                continue
            if in_suggestions and line.startswith(('-', '•', '*', '1', '2', '3', '4', '5')):
                clean = line.lstrip('-•*0123456789. ').strip()
                if len(clean) > 10:
                    suggestions.append(clean)

        return suggestions[:5]


# ==================== Agent implementations ====================

class ClaudeVoter(VotingAgent):
    def __init__(self):
        super().__init__(
            name="Claude",
            role="Code Review & Security",
            specialty_tags=["security", "logic", "code_quality"],
            weight=1.2
        )
        self.api_key = os.getenv("AIMLAPI_KEY")

    async def _call_api(self, prompt: str) -> str:
        if not self.api_key:
            return "NEEDS_REVIEW | 50% | AIMLAPI_KEY تنظیم نشده"
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "claude-sonnet-4-5",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}]
            }
            session = await self._get_session()
            async with session.post(
                "https://api.aimlapi.com/v1/chat/completions",
                headers=headers, json=body
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    log_warn(logger, self.name, f"HTTP {resp.status}: {error_text}")
                    return f"NEEDS_REVIEW | 0% | خطای API: HTTP {resp.status}"
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            log_error(logger, self.name, "خطای API", e)
            return f"NEEDS_REVIEW | 0% | خطا: {e}"


class GeminiVoter(VotingAgent):
    def __init__(self):
        super().__init__(
            name="Gemini",
            role="Performance & Optimization",
            specialty_tags=["performance", "complexity", "optimization"],
            weight=1.2
        )
        self.api_key = os.getenv("AIMLAPI_KEY")

    async def _call_api(self, prompt: str) -> str:
        if not self.api_key:
            return "NEEDS_REVIEW | 50% | AIMLAPI_KEY تنظیم نشده"
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "gemini-2.0-flash",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}]
            }
            session = await self._get_session()
            async with session.post(
                "https://api.aimlapi.com/v1/chat/completions",
                headers=headers, json=body
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    log_warn(logger, self.name, f"HTTP {resp.status}: {error_text}")
                    return f"NEEDS_REVIEW | 0% | خطای API: HTTP {resp.status}"
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            log_error(logger, self.name, "خطای API", e)
            return f"NEEDS_REVIEW | 0% | خطا: {e}"


class GPTVoter(VotingAgent):
    def __init__(self):
        super().__init__(
            name="GPT-4",
            role="Best Practices & Documentation",
            specialty_tags=["best_practices", "documentation", "standards"],
            weight=1.0
        )
        self.api_key = os.getenv("AIMLAPI_KEY")

    async def _call_api(self, prompt: str) -> str:
        if not self.api_key:
            return "NEEDS_REVIEW | 50% | AIMLAPI_KEY تنظیم نشده"
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "gpt-4o",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}]
            }
            session = await self._get_session()
            async with session.post(
                "https://api.aimlapi.com/v1/chat/completions",
                headers=headers, json=body
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    log_warn(logger, self.name, f"HTTP {resp.status}: {error_text}")
                    return f"NEEDS_REVIEW | 0% | خطای API: HTTP {resp.status}"
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            log_error(logger, self.name, "خطای API", e)
            return f"NEEDS_REVIEW | 0% | خطا: {e}"


class GrokVoter(VotingAgent):
    def __init__(self):
        super().__init__(
            name="Grok",
            role="Debugging & Direct Feedback",
            specialty_tags=["debugging", "runtime_errors", "edge_cases"],
            weight=1.0
        )
        self.api_key = os.getenv("AIMLAPI_KEY")

    async def _call_api(self, prompt: str) -> str:
        if not self.api_key:
            return "NEEDS_REVIEW | 50% | AIMLAPI_KEY تنظیم نشده"
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "grok-3",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}]
            }
            session = await self._get_session()
            async with session.post(
                "https://api.aimlapi.com/v1/chat/completions",
                headers=headers, json=body
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    log_warn(logger, self.name, f"HTTP {resp.status}: {error_text}")
                    return f"NEEDS_REVIEW | 0% | خطای API: HTTP {resp.status}"
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            log_error(logger, self.name, "خطای API", e)
            return f"NEEDS_REVIEW | 0% | خطا: {e}"


# ==================== Voting System ====================

class VotingSystem:
    def __init__(self, agents: list[VotingAgent]):
        self.agents = agents

    async def run_vote(self, content: str) -> VotingResult:
        log_info(logger, "VotingSystem", f"شروع رای‌گیری با {len(self.agents)} agent...")

        tasks = [agent.cast_vote(content) for agent in self.agents]
        votes = await asyncio.gather(*tasks, return_exceptions=True)

        valid_votes = []
        for vote in votes:
            if isinstance(vote, Exception):
                log_error(logger, "VotingSystem", "رای معتبر نبود", vote)
            else:
                valid_votes.append(vote)

        if not valid_votes:
            log_warn(logger, "VotingSystem", "هیچ رای معتبری نبود!")
            return VotingResult(
                votes=[],
                final_verdict=VoteType.NEEDS_REVIEW,
                consensus_score=0.0,
                confirmed_issues=[],
                all_suggestions=[]
            )

        all_issues = []
        for vote in valid_votes:
            all_issues.extend(vote.issues)

        confirmed_issues = self._confirm_issues(all_issues, valid_votes)

        all_suggestions = []
        seen = set()
        for vote in valid_votes:
            for s in vote.suggestions:
                if s not in seen:
                    all_suggestions.append(s)
                    seen.add(s)

        final_verdict, consensus_score = self._calculate_verdict(valid_votes)

        log_success(
            logger,
            "VotingSystem",
            f"رای‌گیری تموم شد | حکم: {final_verdict.value} | "
            f"اجماع: {consensus_score:.0%}"
        )

        return VotingResult(
            votes=valid_votes,
            final_verdict=final_verdict,
            consensus_score=consensus_score,
            confirmed_issues=confirmed_issues,
            all_suggestions=all_suggestions
        )

    def _confirm_issues(
        self,
        all_issues: list[Issue],
        votes: list[Vote]
    ) -> list[Issue]:
        confirmed = []
        processed_titles = set()

        for issue in all_issues:
            title_lower = issue.title.lower()
            is_duplicate = False

            for processed in confirmed:
                processed_words = set(processed.title.lower().split())
                current_words = set(title_lower.split())
                overlap = len(processed_words & current_words)

                if overlap >= 2:
                    processed.confirm(issue.found_by)
                    is_duplicate = True
                    break

            if not is_duplicate and title_lower not in processed_titles:
                confirmed.append(issue)
                processed_titles.add(title_lower)

        return [
            i for i in confirmed
            if i.is_confirmed
            or i.severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM]
        ]

    def _calculate_verdict(
        self,
        votes: list[Vote]
    ) -> tuple[VoteType, float]:
        if not votes:
            return VoteType.NEEDS_REVIEW, 0.0

        total_weight = sum(v.weight for v in votes)
        weighted_sum = sum(v.weighted_score for v in votes)
        avg_score = weighted_sum / total_weight if total_weight > 0 else 0.5

        critical_votes = [v for v in votes if v.vote_type == VoteType.CRITICAL]
        if critical_votes:
            high_confidence_critical = [
                v for v in critical_votes if v.confidence >= 0.8
            ]
            if high_confidence_critical:
                consensus = len(critical_votes) / len(votes)
                return VoteType.CRITICAL, consensus

        if avg_score >= 0.85:
            verdict = VoteType.APPROVE
        elif avg_score >= 0.65:
            verdict = VoteType.MINOR
        elif avg_score >= 0.45:
            verdict = VoteType.NEEDS_REVIEW
        elif avg_score >= 0.2:
            verdict = VoteType.REJECT
        else:
            verdict = VoteType.CRITICAL

        vote_types = [v.vote_type for v in votes]
        most_common = max(set(vote_types), key=vote_types.count)
        consensus = vote_types.count(most_common) / len(votes)

        return verdict, consensus

    async def close(self):
        for agent in self.agents:
            await agent.close()


# ==================== Main (standalone test) ====================
async def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    agents = [
        ClaudeVoter(),
        GeminiVoter(),
        GPTVoter(),
        GrokVoter(),
    ]

    voting_system = VotingSystem(agents)

    sample_code = """
def get_user(user_id):
    db = connect_database()
    query = "SELECT * FROM users WHERE id = " + user_id
    result = db.execute(query)
    return result

def find_duplicates(items):
    result = []
    for i in range(len(items)):
        for j in range(len(items)):
            if i != j and items[i] == items[j]:
                result.append(items[i])
    return result

def divide(a, b):
    return a / b
    """

    try:
        print("\n🗳️  شروع رای‌گیری...\n")
        result = await voting_system.run_vote(sample_code)
        print(result.format_report())
    finally:
        await voting_system.close()


if __name__ == "__main__":
    asyncio.run(main())
