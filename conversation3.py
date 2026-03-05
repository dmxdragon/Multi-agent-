import re
import asyncio
import aiohttp
import os
import traceback
import logging
from datetime import datetime
from enum import Enum
from logger3 import get_logger, log_info, log_error, log_success, log_warn

# ==================== Logger ====================
logger = get_logger("MultiAgent.Conversation")


# ==================== Message Types ====================

class MessageType(Enum):
    INITIAL_ANALYSIS = "تحلیل اولیه"
    RESPONSE         = "پاسخ"
    AGREEMENT        = "موافقت"
    DISAGREEMENT     = "مخالفت"
    QUESTION         = "سوال"
    ANSWER           = "جواب"
    FINAL_VERDICT    = "نظر نهایی"


# ==================== Message ====================

class Message:
    def __init__(
        self,
        sender: str,
        receiver: str,
        content: str,
        msg_type: MessageType,
        round_number: int = 0
    ):
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.msg_type = msg_type
        self.round_number = round_number
        self.timestamp = datetime.now().strftime("%H:%M:%S")

    def __repr__(self):
        return (
            f"[Round {self.round_number}] "
            f"{self.sender} → {self.receiver} "
            f"({self.msg_type.value})"
        )

    def to_text(self) -> str:
        return (
            f"از: {self.sender}\n"
            f"به: {self.receiver}\n"
            f"نوع: {self.msg_type.value}\n"
            f"زمان: {self.timestamp}\n"
            f"محتوا: {self.content}"
        )


# ==================== Conversation History ====================

class ConversationHistory:
    def __init__(self):
        self.messages: list[Message] = []

    def add(self, message: Message):
        self.messages.append(message)
        log_info(logger, "History", str(message))

    def get_all(self) -> list[Message]:
        return self.messages

    def get_by_sender(self, sender: str) -> list[Message]:
        return [m for m in self.messages if m.sender == sender]

    def get_by_round(self, round_number: int) -> list[Message]:
        return [m for m in self.messages if m.round_number == round_number]

    def get_context_for_agent(self, agent_name: str, current_round: int) -> str:
        relevant = []
        for m in self.messages:
            if m.round_number < current_round:
                if m.receiver == "ALL" or m.receiver == agent_name or m.sender == agent_name:
                    relevant.append(
                        f"[{m.sender} → {m.receiver}] ({m.msg_type.value}):\n{m.content}"
                    )
        if not relevant:
            return "هنوز مکالمه‌ای نبوده."
        return "\n\n---\n\n".join(relevant)

    def format_full_conversation(self) -> str:
        lines = []
        current_round = -1
        for msg in self.messages:
            if msg.round_number != current_round:
                current_round = msg.round_number
                lines.append(f"\n{'═' * 50}")
                lines.append(f"🔄 راند {current_round}")
                lines.append(f"{'═' * 50}")
            lines.append(f"\n🤖 {msg.sender} → {msg.receiver}")
            lines.append(f"📌 {msg.msg_type.value} | ⏰ {msg.timestamp}")
            lines.append(f"{'─' * 30}")
            lines.append(msg.content)
        return "\n".join(lines)


# ==================== Base Conversational Agent ====================

class ConversationalAgent:
    def __init__(self, name: str, role: str, personality: str):
        self.name = name
        self.role = role
        self.personality = personality
        self._session: aiohttp.ClientSession = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """session مشترک با timeout مناسب"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _call_api(self, prompt: str) -> str:
        raise NotImplementedError

    def _detect_message_type(self, response: str) -> MessageType:
        """تشخیص نوع پیام با بررسی دقیق‌تر negation"""

        def has_keyword_without_negation(text: str, keywords: list) -> bool:
            """چک کن کلمه کلیدی بدون negation قبلش وجود داره"""
            # الگوی negation: نه|نیست|نمی|نمیشه|نبود + فاصله + کلمه
            negation_pattern = r'(نه|نیست|نمی|نمیشه|نبود|اصلاً|هرگز)\s*\S*\s*'
            for kw in keywords:
                # پیدا کردن همه جاهایی که کلمه کلیدی هست
                for match in re.finditer(re.escape(kw), text, re.IGNORECASE):
                    start = match.start()
                    # ۳۰ کاراکتر قبل از کلمه رو بررسی کن
                    prefix = text[max(0, start - 30):start]
                    if not re.search(negation_pattern, prefix):
                        return True
            return False

        if has_keyword_without_negation(response, ["موافقم", "درسته", "agree", "correct", "صحیحه"]):
            return MessageType.AGREEMENT
        elif has_keyword_without_negation(response, ["مخالفم", "اشتباهه", "disagree", "wrong", "غلطه"]):
            return MessageType.DISAGREEMENT
        elif "?" in response or "چرا" in response or "چطور" in response or "آیا" in response:
            return MessageType.QUESTION
        return MessageType.RESPONSE

    async def initial_analysis(
        self,
        content: str,
        history: ConversationHistory,
        round_num: int
    ) -> Message:
        log_info(logger, self.name, f"راند {round_num} - تحلیل اولیه...")
        context = history.get_context_for_agent(self.name, round_num)
        prompt = f"""
شخصیت تو: {self.personality}
نقش تخصصی تو: {self.role}

محتوایی که باید تحلیل کنی:
{content}

مکالمات قبلی (اگه وجود داشته باشه):
{context}

وظیفه تو در این راند:
- تحلیل اولیه خودت رو بده
- اگه مکالمه قبلی بوده، به نظرات بقیه هم اشاره کن
- اگه با کسی موافق یا مخالفی بگو
- مستقیم و واضح باش
"""
        response = await self._call_api(prompt)
        msg_type = MessageType.INITIAL_ANALYSIS if round_num == 0 else MessageType.RESPONSE
        return Message(
            sender=self.name,
            receiver="ALL",
            content=response,
            msg_type=msg_type,
            round_number=round_num
        )

    async def respond_to_agent(
        self,
        target_agent: str,
        target_message: Message,
        history: ConversationHistory,
        round_num: int
    ) -> Message:
        log_info(logger, self.name, f"راند {round_num} - جواب به {target_agent}...")
        context = history.get_context_for_agent(self.name, round_num)
        prompt = f"""
شخصیت تو: {self.personality}
نقش تخصصی تو: {self.role}

{target_agent} این رو گفت:
{target_message.content}

مکالمات قبلی:
{context}

وظیفه تو:
- مستقیماً به {target_agent} جواب بده
- اگه موافقی دلیل بیار
- اگه مخالفی صریح بگو چرا
- می‌تونی سوال بپرسی
"""
        response = await self._call_api(prompt)
        msg_type = self._detect_message_type(response)

        return Message(
            sender=self.name,
            receiver=target_agent,
            content=response,
            msg_type=msg_type,
            round_number=round_num
        )

    async def final_verdict(
        self,
        content: str,
        history: ConversationHistory,
        round_num: int
    ) -> Message:
        log_info(logger, self.name, f"راند {round_num} - نظر نهایی...")
        context = history.get_context_for_agent(self.name, round_num)
        prompt = f"""
شخصیت تو: {self.personality}
نقش تخصصی تو: {self.role}

محتوای اصلی:
{content}

همه بحث‌هایی که شد:
{context}

حالا نظر نهایی خودت رو بده:
- مهم‌ترین مشکلات چیه؟
- بهترین راه‌حل چیه؟
- با کدوم نظرات موافقی؟
- چی رو اضافه می‌کنی؟
"""
        response = await self._call_api(prompt)
        return Message(
            sender=self.name,
            receiver="ALL",
            content=response,
            msg_type=MessageType.FINAL_VERDICT,
            round_number=round_num
        )


# ==================== Claude Conversational ====================

class ClaudeConversational(ConversationalAgent):
    def __init__(self):
        super().__init__(
            name="Claude",
            role="Code Review & Security",
            personality="دقیق، مستقیم، امنیت رو جدی میگیره"
        )
        self.api_key = os.getenv("AIMLAPI_KEY")

    async def _call_api(self, prompt: str) -> str:
        if not self.api_key:
            return "❌ AIMLAPI_KEY تنظیم نشده"
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "claude-sonnet-4-5",
                "max_tokens": 1024,
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
                    return f"❌ خطای API: HTTP {resp.status}"
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            log_error(logger, self.name, "خطای API", e)
            return f"❌ خطا: {e}"


# ==================== Gemini Conversational ====================

class GeminiConversational(ConversationalAgent):
    def __init__(self):
        super().__init__(
            name="Gemini",
            role="Performance & Optimization",
            personality="ریاضی‌دان، داده‌محور، همه چیز رو با عدد میسنجه"
        )
        self.api_key = os.getenv("AIMLAPI_KEY")

    async def _call_api(self, prompt: str) -> str:
        if not self.api_key:
            return "❌ AIMLAPI_KEY تنظیم نشده"
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "gemini-2.0-flash",
                "max_tokens": 1024,
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
                    return f"❌ خطای API: HTTP {resp.status}"
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            log_error(logger, self.name, "خطای API", e)
            return f"❌ خطا: {e}"


# ==================== GPT Conversational ====================

class GPTConversational(ConversationalAgent):
    def __init__(self):
        super().__init__(
            name="GPT-4",
            role="Best Practices & Documentation",
            personality="محتاط، همه طرف رو میبینه، توضیح زیاد میده 😂"
        )
        self.api_key = os.getenv("AIMLAPI_KEY")

    async def _call_api(self, prompt: str) -> str:
        if not self.api_key:
            return "❌ AIMLAPI_KEY تنظیم نشده"
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "gpt-4o",
                "max_tokens": 1024,
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
                    return f"❌ خطای API: HTTP {resp.status}"
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            log_error(logger, self.name, "خطای API", e)
            return f"❌ خطا: {e}"


# ==================== Grok Conversational ====================

class GrokConversational(ConversationalAgent):
    def __init__(self):
        super().__init__(
            name="Grok",
            role="Debugging & Direct Feedback",
            personality="پررو، صریح، از تعارف متنفره، مستقیم میگه 😂"
        )
        self.api_key = os.getenv("AIMLAPI_KEY")

    async def _call_api(self, prompt: str) -> str:
        if not self.api_key:
            return "❌ AIMLAPI_KEY تنظیم نشده"
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "grok-3",
                "max_tokens": 1024,
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
                    return f"❌ خطای API: HTTP {resp.status}"
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            log_error(logger, self.name, "خطای API", e)
            return f"❌ خطا: {e}"


# ==================== Conversation Manager ====================

class ConversationManager:
    def __init__(self, agents: list[ConversationalAgent], max_rounds: int = 3):
        self.agents = agents
        self.max_rounds = max_rounds  # تعداد راندهای بحث (نه شامل راند ۰ و نظر نهایی)
        self.history = ConversationHistory()

    async def run_conversation(self, content: str) -> ConversationHistory:
        log_info(logger, "Manager", f"شروع مکالمه با {len(self.agents)} agent و {self.max_rounds} راند")

        # راند ۰: تحلیل اولیه
        initial_tasks = [
            agent.initial_analysis(content, self.history, round_num=0)
            for agent in self.agents
        ]
        initial_messages = await asyncio.gather(*initial_tasks, return_exceptions=True)
        for msg in initial_messages:
            if isinstance(msg, Exception):
                log_error(logger, "Manager", "خطا در تحلیل اولیه", msg)
            else:
                self.history.add(msg)

        # راندهای بعدی: بحث
        for round_num in range(1, self.max_rounds):
            log_info(logger, "Manager", f"راند {round_num}: agent ها دارن باهم بحث می‌کنن...")
            round_tasks = []
            for i, agent in enumerate(self.agents):
                target_idx = (i - 1) % len(self.agents)
                target_agent = self.agents[target_idx]
                target_messages = self.history.get_by_sender(target_agent.name)
                if target_messages:
                    last_msg = target_messages[-1]
                    task = agent.respond_to_agent(
                        target_agent.name, last_msg, self.history, round_num
                    )
                else:
                    task = agent.initial_analysis(content, self.history, round_num)
                round_tasks.append(task)

            round_messages = await asyncio.gather(*round_tasks, return_exceptions=True)
            for msg in round_messages:
                if isinstance(msg, Exception):
                    log_error(logger, "Manager", f"خطا در راند {round_num}", msg)
                else:
                    self.history.add(msg)

        # راند آخر: نظر نهایی
        log_info(logger, "Manager", "راند آخر: همه نظر نهایی میدن...")
        final_tasks = [
            agent.final_verdict(content, self.history, round_num=self.max_rounds)
            for agent in self.agents
        ]
        final_messages = await asyncio.gather(*final_tasks, return_exceptions=True)
        for msg in final_messages:
            if isinstance(msg, Exception):
                log_error(logger, "Manager", "خطا در نظر نهایی", msg)
            else:
                self.history.add(msg)

        log_success(logger, "Manager", f"مکالمه کامل شد - {len(self.history.messages)} پیام")
        return self.history

    async def close(self):
        for agent in self.agents:
            await agent.close()

    def get_summary(self) -> str:
        messages = self.history.get_all()
        agreement_count    = sum(1 for m in messages if m.msg_type == MessageType.AGREEMENT)
        disagreement_count = sum(1 for m in messages if m.msg_type == MessageType.DISAGREEMENT)
        question_count     = sum(1 for m in messages if m.msg_type == MessageType.QUESTION)
        lines = [
            "\n📊 آمار مکالمه:",
            f"   کل پیام‌ها: {len(messages)}",
            f"   موافقت‌ها: {agreement_count}",
            f"   مخالفت‌ها: {disagreement_count}",
            f"   سوال‌ها: {question_count}",
        ]
        return "\n".join(lines)


# ==================== Main (standalone test) ====================
async def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    agents = [
        ClaudeConversational(),
        GeminiConversational(),
        GPTConversational(),
        GrokConversational(),
    ]
    manager = ConversationManager(agents, max_rounds=3)
    sample_code = """
def get_user(user_id):
    db = connect_database()
    query = "SELECT * FROM users WHERE id = " + user_id
    result = db.execute(query)
    return result
    """
    try:
        print("\n🚀 شروع مکالمه بین agent ها...\n")
        history = await manager.run_conversation(sample_code)
        print(history.format_full_conversation())
        print(manager.get_summary())
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
