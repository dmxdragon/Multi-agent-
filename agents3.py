import asyncio
import aiohttp
import os
import traceback
import logging
from abc import ABC, abstractmethod
from logger3 import get_logger, log_info, log_error, log_success, log_warn

# ==================== Logger ====================
logger = get_logger("MultiAgent.Agents")


# ==================== Base Agent ====================

class BaseAgent(ABC):
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self._session: aiohttp.ClientSession = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """session مشترک با timeout مناسب"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """بستن session"""
        if self._session and not self._session.closed:
            await self._session.close()

    @abstractmethod
    async def analyze(self, content: str) -> str:
        pass

    def __repr__(self):
        return f"{self.name} ({self.role})"


# ==================== Claude Agent ====================

class ClaudeAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Claude", role="Code Review & Security")
        self.api_key = os.getenv("AIMLAPI_KEY")
        self.url = "https://api.aimlapi.com/v1/chat/completions"

    async def analyze(self, content: str) -> str:
        if not self.api_key:
            log_warn(logger, self.name, "API key پیدا نشد")
            return "❌ AIMLAPI_KEY تنظیم نشده"
        try:
            log_info(logger, self.name, "شروع تحلیل...")
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "claude-sonnet-4-5",
                "max_tokens": 1024,
                "messages": [{
                    "role": "user",
                    "content": (
                        f"نقش تو: {self.role}\n"
                        f"این محتوا رو بررسی کن و مشکلات امنیتی، "
                        f"باگ‌ها و بهبودهای منطقی رو بگو:\n\n{content}"
                    )
                }]
            }
            session = await self._get_session()
            async with session.post(self.url, headers=headers, json=body) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    log_warn(logger, self.name, f"HTTP {resp.status}: {error_text}")
                    return f"❌ خطای API: HTTP {resp.status}"
                data = await resp.json()
                result = data["choices"][0]["message"]["content"]
                log_success(logger, self.name, "تحلیل کامل شد")
                return result
        except aiohttp.ClientConnectionError as e:
            log_error(logger, self.name, "اتصال به aimlapi قطع شد", e)
            return "❌ خطای اتصال به Claude API"
        except Exception as e:
            log_error(logger, self.name, "خطای ناشناخته", e)
            return f"❌ خطا: {e}"


# ==================== Gemini Agent ====================

class GeminiAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Gemini", role="Performance & Optimization")
        self.api_key = os.getenv("AIMLAPI_KEY")
        self.url = "https://api.aimlapi.com/v1/chat/completions"

    async def analyze(self, content: str) -> str:
        if not self.api_key:
            log_warn(logger, self.name, "API key پیدا نشد")
            return "❌ AIMLAPI_KEY تنظیم نشده"
        try:
            log_info(logger, self.name, "شروع تحلیل...")
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "gemini-2.0-flash",
                "max_tokens": 1024,
                "messages": [{
                    "role": "user",
                    "content": (
                        f"نقش تو: {self.role}\n"
                        f"این محتوا رو از نظر performance، "
                        f"پیچیدگی زمانی و بهینه‌سازی بررسی کن:\n\n{content}"
                    )
                }]
            }
            session = await self._get_session()
            async with session.post(self.url, headers=headers, json=body) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    log_warn(logger, self.name, f"HTTP {resp.status}: {error_text}")
                    return f"❌ خطای API: HTTP {resp.status}"
                data = await resp.json()
                result = data["choices"][0]["message"]["content"]
                log_success(logger, self.name, "تحلیل کامل شد")
                return result
        except aiohttp.ClientConnectionError as e:
            log_error(logger, self.name, "اتصال به aimlapi قطع شد", e)
            return "❌ خطای اتصال به Gemini API"
        except Exception as e:
            log_error(logger, self.name, "خطای ناشناخته", e)
            return f"❌ خطا: {e}"


# ==================== GPT Agent ====================

class GPTAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="GPT-4", role="Best Practices & Documentation")
        self.api_key = os.getenv("AIMLAPI_KEY")
        self.url = "https://api.aimlapi.com/v1/chat/completions"

    async def analyze(self, content: str) -> str:
        if not self.api_key:
            log_warn(logger, self.name, "API key پیدا نشد")
            return "❌ AIMLAPI_KEY تنظیم نشده"
        try:
            log_info(logger, self.name, "شروع تحلیل...")
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "gpt-4o",
                "max_tokens": 1024,
                "messages": [{
                    "role": "user",
                    "content": (
                        f"نقش تو: {self.role}\n"
                        f"این محتوا رو از نظر best practices، "
                        f"مستندسازی و استانداردها بررسی کن:\n\n{content}"
                    )
                }]
            }
            session = await self._get_session()
            async with session.post(self.url, headers=headers, json=body) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    log_warn(logger, self.name, f"HTTP {resp.status}: {error_text}")
                    return f"❌ خطای API: HTTP {resp.status}"
                data = await resp.json()
                result = data["choices"][0]["message"]["content"]
                log_success(logger, self.name, "تحلیل کامل شد")
                return result
        except aiohttp.ClientConnectionError as e:
            log_error(logger, self.name, "اتصال به aimlapi قطع شد", e)
            return "❌ خطای اتصال به GPT API"
        except Exception as e:
            log_error(logger, self.name, "خطای ناشناخته", e)
            return f"❌ خطا: {e}"


# ==================== Grok Agent ====================

class GrokAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Grok", role="Debugging & Direct Feedback")
        self.api_key = os.getenv("AIMLAPI_KEY")
        self.url = "https://api.aimlapi.com/v1/chat/completions"

    async def analyze(self, content: str) -> str:
        if not self.api_key:
            log_warn(logger, self.name, "API key پیدا نشد")
            return "❌ AIMLAPI_KEY تنظیم نشده"
        try:
            log_info(logger, self.name, "شروع تحلیل...")
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "grok-3",
                "max_tokens": 1024,
                "messages": [{
                    "role": "user",
                    "content": (
                        f"نقش تو: {self.role}\n"
                        f"مستقیم و بدون تعارف بگو "
                        f"این کد چه مشکلاتی داره و چطور debug بشه:\n\n{content}"
                    )
                }]
            }
            session = await self._get_session()
            async with session.post(self.url, headers=headers, json=body) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    log_warn(logger, self.name, f"HTTP {resp.status}: {error_text}")
                    return f"❌ خطای API: HTTP {resp.status}"
                data = await resp.json()
                result = data["choices"][0]["message"]["content"]
                log_success(logger, self.name, "تحلیل کامل شد")
                return result
        except aiohttp.ClientConnectionError as e:
            log_error(logger, self.name, "اتصال به aimlapi قطع شد", e)
            return "❌ خطای اتصال به Grok API"
        except Exception as e:
            log_error(logger, self.name, "خطای ناشناخته", e)
            return f"❌ خطا: {e}"


# ==================== Orchestrator ====================

class Orchestrator:
    def __init__(self, agents: list[BaseAgent]):
        self.agents = agents
        log_info(logger, "Orchestrator", f"{len(agents)} agent آماده: {[str(a) for a in agents]}")

    async def run(self, content: str) -> dict:
        log_info(logger, "Orchestrator", f"شروع تحلیل همزمان با {len(self.agents)} agent...")
        tasks = [agent.analyze(content) for agent in self.agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final = {}
        success_count = 0
        for agent, result in zip(self.agents, results):
            if isinstance(result, Exception):
                log_error(logger, "Orchestrator", f"{agent.name} خطا داد", result)
                final[agent.name] = f"❌ خطا: {result}"
            else:
                final[agent.name] = result
                success_count += 1

        log_success(logger, "Orchestrator", f"{success_count}/{len(self.agents)} agent موفق بودن")
        return final

    async def close(self):
        """بستن همه session ها"""
        for agent in self.agents:
            await agent.close()

    def format_output(self, results: dict) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("🤖 نتایج تحلیل Multi-Agent")
        lines.append("=" * 60)
        for agent_name, result in results.items():
            agent = next((a for a in self.agents if a.name == agent_name), None)
            role = agent.role if agent else ""
            lines.append(f"\n{'─' * 40}")
            lines.append(f"🔹 {agent_name} | {role}")
            lines.append(f"{'─' * 40}")
            lines.append(result)
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)


# ==================== Main (standalone test) ====================
async def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    agents = [ClaudeAgent(), GeminiAgent(), GPTAgent(), GrokAgent()]
    orchestrator = Orchestrator(agents)
    sample_code = """
def get_user(user_id):
    db = connect_database()
    query = "SELECT * FROM users WHERE id = " + user_id
    result = db.execute(query)
    return result
    """
    try:
        print("\n📤 کد ارسال شد به همه agent ها...\n")
        results = await orchestrator.run(sample_code)
        print(orchestrator.format_output(results))
    finally:
        await orchestrator.close()


if __name__ == "__main__":
    asyncio.run(main())
