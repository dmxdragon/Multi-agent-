import asyncio
import aiohttp
import os
import sys
import json
import time
import traceback
import logging
from datetime import datetime
from pathlib import Path

# ==================== dotenv ====================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==================== رنگ‌ها ====================
class Color:
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BOLD    = "\033[1m"
    RESET   = "\033[0m"

def red(t):     return f"{Color.RED}{t}{Color.RESET}"
def green(t):   return f"{Color.GREEN}{t}{Color.RESET}"
def yellow(t):  return f"{Color.YELLOW}{t}{Color.RESET}"
def blue(t):    return f"{Color.BLUE}{t}{Color.RESET}"
def cyan(t):    return f"{Color.CYAN}{t}{Color.RESET}"
def bold(t):    return f"{Color.BOLD}{t}{Color.RESET}"
def magenta(t): return f"{Color.MAGENTA}{t}{Color.RESET}"


# ==================== Master Logger ====================
class MasterLogger:
    LOG_FILE = "system_logs.txt"

    def __init__(self):
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        if not root_logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler = logging.FileHandler(self.LOG_FILE, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)

            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            stream_handler.setFormatter(formatter)

            root_logger.addHandler(file_handler)
            root_logger.addHandler(stream_handler)

        self.logger = logging.getLogger("MultiAgent.System")
        self.logger.info("=" * 60)
        self.logger.info("🚀 Session جدید شروع شد")
        self.logger.info("=" * 60)

    def info(self, module, msg):
        self.logger.info(f"[{module:20s}] {msg}")

    def success(self, module, msg):
        self.logger.info(f"[{module:20s}] ✅ {msg}")

    def warning(self, module, msg):
        self.logger.warning(f"[{module:20s}] ⚠️  {msg}")

    def error(self, module, msg, exc=None):
        if exc:
            tb = traceback.format_exc()
            self.logger.error(
                f"[{module:20s}] ❌ {msg}\n"
                f"  Exception: {type(exc).__name__}: {exc}\n"
                f"  File: {self._get_file_info(exc)}\n"
                f"  Traceback:\n{tb}"
            )
        else:
            self.logger.error(f"[{module:20s}] ❌ {msg}")

    def critical(self, module, msg, exc=None):
        if exc:
            tb = traceback.format_exc()
            self.logger.critical(
                f"[{module:20s}] 🚨 {msg}\n"
                f"  Exception: {type(exc).__name__}: {exc}\n"
                f"  File: {self._get_file_info(exc)}\n"
                f"  Traceback:\n{tb}"
            )
        else:
            self.logger.critical(f"[{module:20s}] 🚨 {msg}")

    def _get_file_info(self, exc):
        tb = traceback.extract_tb(exc.__traceback__)
        if tb:
            last = tb[-1]
            return f"{last.filename}:{last.lineno} in {last.name}()"
        return "unknown"

    def divider(self, title=""):
        if title:
            self.logger.info(f"{'─' * 20} {title} {'─' * 20}")
        else:
            self.logger.info("─" * 60)


# ==================== System Health Check ====================
class SystemHealthCheck:
    def __init__(self, log):
        self.log = log
        self.results = {}

    def check_env_variables(self):
        required = {
            "AIMLAPI_KEY": "همه Agent‌ها (Claude, Gemini, GPT-4, Grok)",
        }
        results = {}
        for env_var, agent_name in required.items():
            value = os.getenv(env_var)
            if value:
                results[agent_name] = {"status": "ok", "message": f"✅ {env_var} تنظیم شده"}
                self.log.success("HealthCheck", f"{agent_name} API key موجوده")
            else:
                results[agent_name] = {"status": "missing", "message": f"❌ {env_var} تنظیم نشده — {agent_name} غیرفعاله"}
                self.log.warning("HealthCheck", f"{agent_name} API key موجود نیست!")
        return results

    def check_required_files(self):
        """چک میکنه فایل‌های نسخه ۳ وجود دارن"""
        required_files = {
            "agents3.py":         "Agent definitions",
            "conversation3.py":   "Conversation system",
            "memory3.py":         "Memory system",
            "voting3.py":         "Voting system",
            "logger3.py":         "Central logger",
            "error_tracker3.py":  "Error tracker",
        }
        results = {}
        for filename, description in required_files.items():
            path = Path(filename)
            if path.exists():
                size = path.stat().st_size
                results[filename] = {"status": "ok", "message": f"✅ {filename} موجوده ({size} bytes)"}
                self.log.success("HealthCheck", f"{filename} موجوده")
            else:
                results[filename] = {"status": "missing", "message": f"❌ {filename} پیدا نشد! — {description}"}
                self.log.error("HealthCheck", f"{filename} پیدا نشد!")
        return results

    async def check_api_connectivity(self, timeout=5):
        endpoints = {
            "aimlapi": ("https://api.aimlapi.com", "AIMLAPI_KEY"),
        }
        results = {}
        for agent_name, (url, key_name) in endpoints.items():
            if not os.getenv(key_name):
                results[agent_name] = {"status": "skipped", "message": f"⏭️  {agent_name} رد شد (API key نیست)"}
                continue
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                        results[agent_name] = {"status": "ok", "message": f"✅ {agent_name} قابل دسترسه (HTTP {resp.status})"}
                        self.log.success("HealthCheck", f"{agent_name} online")
            except aiohttp.ClientConnectorError:
                results[agent_name] = {"status": "unreachable", "message": f"❌ {agent_name} قابل دسترس نیست"}
                self.log.error("HealthCheck", f"{agent_name} offline!")
            except asyncio.TimeoutError:
                results[agent_name] = {"status": "timeout", "message": f"⏰ {agent_name} timeout شد ({timeout}s)"}
                self.log.warning("HealthCheck", f"{agent_name} timeout!")
            except Exception as e:
                results[agent_name] = {"status": "error", "message": f"❌ خطای ناشناخته: {e}"}
                self.log.error("HealthCheck", f"{agent_name} خطا", e)
        return results

    async def run_full_check(self):
        self.log.divider("System Health Check")
        all_results = {}

        env_results  = self.check_env_variables()
        all_results["env"] = env_results

        file_results = self.check_required_files()
        all_results["files"] = file_results

        conn_results = await self.check_api_connectivity()
        all_results["connectivity"] = conn_results

        can_continue = any(v["status"] == "ok" for v in env_results.values())
        files_ok     = all(v["status"] == "ok" for v in file_results.values())

        if not files_ok:
            self.log.critical("HealthCheck", "فایل‌های لازم موجود نیستن — سیستم اجرا نمیشه!")
            can_continue = False

        return can_continue, all_results

    def print_report(self, results):
        print(f"\n{bold('═' * 60)}")
        print(bold("🏥 گزارش سلامت سیستم"))
        print(bold("═" * 60))

        print(f"\n{cyan('📋 API Keys:')}")
        for agent, result in results.get("env", {}).items():
            msg = result["message"]
            print(f"  {green(msg)}" if result["status"] == "ok" else f"  {red(msg)}")

        print(f"\n{cyan('📁 فایل‌ها:')}")
        for filename, result in results.get("files", {}).items():
            msg = result["message"]
            print(f"  {green(msg)}" if result["status"] == "ok" else f"  {red(msg)}")

        print(f"\n{cyan('🌐 اتصال به API ها:')}")
        for agent, result in results.get("connectivity", {}).items():
            msg = result["message"]
            if result["status"] == "ok":
                print(f"  {green(msg)}")
            elif result["status"] == "skipped":
                print(f"  {yellow(msg)}")
            else:
                print(f"  {red(msg)}")

        print(bold("═" * 60))


# ==================== File Handler ====================
class FileHandler:
    SUPPORTED_EXTENSIONS = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".java": "Java", ".cpp": "C++", ".c": "C", ".go": "Go",
        ".rs": "Rust", ".php": "PHP", ".rb": "Ruby",
        ".txt": "Text", ".md": "Markdown",
    }

    def __init__(self, log):
        self.log = log

    def read_file(self, file_path):
        path = Path(file_path)
        if not path.exists():
            self.log.error("FileHandler", f"فایل پیدا نشد: {file_path}")
            raise FileNotFoundError(f"❌ فایل '{file_path}' وجود نداره")

        ext = path.suffix.lower()
        language = self.SUPPORTED_EXTENSIONS.get(ext, "Unknown")

        if language == "Unknown":
            self.log.warning("FileHandler", f"extension ناشناخته: {ext}")

        size = path.stat().st_size
        if size > 1_000_000:
            self.log.warning("FileHandler", f"فایل بزرگه: {size:,} bytes")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.log.success("FileHandler", f"فایل خونده شد: {path.name} | زبان: {language} | سایز: {size:,} bytes | خطوط: {content.count(chr(10))}")
            return content, language
        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read()
                self.log.warning("FileHandler", "با latin-1 encoding خونده شد")
                return content, language
            except Exception as e:
                self.log.error("FileHandler", "نمیشه فایل رو خوند", e)
                raise
        except Exception as e:
            self.log.error("FileHandler", f"خطا در خواندن فایل: {file_path}", e)
            raise

    def read_text(self, text):
        language = "Unknown"
        if "def " in text and "import " in text:
            language = "Python"
        elif "function " in text or "const " in text:
            language = "JavaScript"
        elif "public class " in text:
            language = "Java"
        self.log.info("FileHandler", f"متن مستقیم دریافت شد | زبان احتمالی: {language} | خطوط: {text.count(chr(10))}")
        return text, language

    def save_report(self, report, original_file=None):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"report_{Path(original_file).stem}_{timestamp}.txt" if original_file else f"report_{timestamp}.txt"
        try:
            with open(output_name, "w", encoding="utf-8") as f:
                f.write(report)
            self.log.success("FileHandler", f"گزارش ذخیره شد: {output_name}")
            return output_name
        except OSError as e:
            self.log.error("FileHandler", "خطا در ذخیره گزارش", e)
            return ""


# ==================== Main System ====================
class MultiAgentSystem:
    def __init__(self):
        self.log = MasterLogger()
        self.health_checker = SystemHealthCheck(self.log)
        self.file_handler = FileHandler(self.log)
        self.start_time = time.time()

    async def initialize(self):
        print(f"\n{bold(magenta('🤖 Multi-Agent AI System'))}")
        print(f"{cyan('DMXdragon Edition')} 🐉\n")

        can_continue, results = await self.health_checker.run_full_check()
        self.health_checker.print_report(results)

        if not can_continue:
            print(f"\n{red('❌ سیستم نمیتونه شروع کنه — مشکلات بالا رو برطرف کن')}")
            return False

        print(f"\n{green('✅ سیستم آماده‌ست!')}\n")
        return True

    async def analyze(self, content, language, source_name="input",
                      use_conversation=True, use_voting=True, use_memory=True):
        self.start_time = time.time()  # ریست زمان برای هر تحلیل جداگانه
        self.log.divider(f"شروع تحلیل: {source_name}")
        self.log.info("System", f"زبان: {language} | حجم: {len(content)} کاراکتر")

        report_parts = [
            f"📄 فایل: {source_name}",
            f"🔤 زبان: {language}",
            f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "═" * 60
        ]

        try:
            # ── مرحله ۱: بارگذاری ماژول‌ها ──
            self.log.info("System", "مرحله ۱: بارگذاری ماژول‌ها...")

            error_tracker = None
            try:
                from error_tracker3 import MasterErrorHandler
                error_tracker = MasterErrorHandler()
                self.log.success("System", "error_tracker3.py بارگذاری شد")
            except ImportError as e:
                self.log.warning("System", f"error_tracker3.py رد شد: {e}")

            try:
                from agents3 import ClaudeAgent, GeminiAgent, GPTAgent, GrokAgent, Orchestrator
                self.log.success("System", "agents3.py بارگذاری شد")
            except ImportError as e:
                self.log.error("System", "agents3.py بارگذاری نشد", e)
                report_parts.append(red(f"❌ agents3.py مشکل داره: {e}"))
                return "\n".join(report_parts)

            if use_conversation:
                try:
                    from conversation3 import (ClaudeConversational, GeminiConversational,
                                               GPTConversational, GrokConversational, ConversationManager)
                    self.log.success("System", "conversation3.py بارگذاری شد")
                except ImportError as e:
                    self.log.error("System", "conversation3.py بارگذاری نشد", e)
                    report_parts.append(yellow(f"⚠️ conversation3.py مشکل داره: {e} — رد میشه"))
                    use_conversation = False

            if use_voting:
                try:
                    from voting3 import ClaudeVoter, GeminiVoter, GPTVoter, GrokVoter, VotingSystem
                    self.log.success("System", "voting3.py بارگذاری شد")
                except ImportError as e:
                    self.log.error("System", "voting3.py بارگذاری نشد", e)
                    report_parts.append(yellow(f"⚠️ voting3.py مشکل داره: {e} — رد میشه"))
                    use_voting = False

            memory_manager = None
            if use_memory:
                try:
                    from memory3 import MemoryManager
                    memory_manager = MemoryManager()
                    self.log.success("System", "memory3.py بارگذاری شد")
                except ImportError as e:
                    self.log.error("System", "memory3.py بارگذاری نشد", e)
                    use_memory = False

            # ── مرحله ۲: Static Analysis ──
            self.log.info("System", "مرحله ۲: Static Analysis...")
            print(f"\n{blue('🔎 مرحله ۲: Static Analysis...')}")
            if error_tracker and language == "Python":
                try:
                    static_report = error_tracker.analyze_code_before_run(content, source_name)
                    report_parts += ["\n" + "═" * 60, "🔎 Static Analysis (قبل از AI)", "═" * 60, static_report]
                    self.log.success("System", "Static analysis کامل شد")
                    print(f"{green('  ✅ کامل شد')}")
                except Exception as e:
                    self.log.error("System", "Static analysis شکست خورد", e)
                    print(f"{yellow('  ⚠️ شکست خورد')}")
            else:
                print(f"{yellow('  ⏭️  رد شد')}")

            # ── مرحله ۳: تحلیل اولیه ──
            self.log.info("System", "مرحله ۳: تحلیل اولیه...")
            print(f"\n{blue('🔍 مرحله ۳: تحلیل اولیه Agent‌ها...')}")
            orchestrator = None
            try:
                agents = [ClaudeAgent(), GeminiAgent(), GPTAgent(), GrokAgent()]
                orchestrator = Orchestrator(agents)
                initial_results = await orchestrator.run(content)

                report_parts += ["\n" + "═" * 60, "🔍 تحلیل اولیه هر Agent", "═" * 60]
                for agent_name, result in initial_results.items():
                    report_parts += [f"\n{'─' * 40}", f"🤖 {agent_name}", "─" * 40, result]
                    if use_memory and memory_manager:
                        mem = memory_manager.get_or_create(agent_name)
                        mem.remember(f"تحلیل {source_name}: {result[:200]}", importance=6)

                self.log.success("System", "تحلیل اولیه کامل شد")
                print(f"{green('  ✅ کامل شد')}")
            except Exception as e:
                self.log.error("System", "تحلیل اولیه شکست خورد", e)
                report_parts.append(red(f"❌ تحلیل اولیه شکست خورد: {e}"))
            finally:
                if orchestrator:
                    await orchestrator.close()

            # ── مرحله ۴: مکالمه ──
            if use_conversation:
                self.log.info("System", "مرحله ۴: مکالمه...")
                print(f"\n{blue('💬 مرحله ۴: مکالمه بین Agent‌ها...')}")
                conv_manager = None
                try:
                    conv_agents = [ClaudeConversational(), GeminiConversational(),
                                   GPTConversational(), GrokConversational()]
                    conv_manager = ConversationManager(conv_agents, max_rounds=2)
                    history = await conv_manager.run_conversation(content)
                    report_parts += ["\n" + "═" * 60, "💬 مکالمه بین Agent‌ها", "═" * 60,
                                     history.format_full_conversation(), conv_manager.get_summary()]
                    self.log.success("System", "مکالمه کامل شد")
                    print(f"{green('  ✅ کامل شد')}")
                except Exception as e:
                    self.log.error("System", "مکالمه شکست خورد", e)
                    report_parts.append(yellow(f"⚠️ مکالمه شکست خورد: {e}"))
                    print(f"{yellow('  ⚠️ شکست خورد')}")
                finally:
                    if conv_manager:
                        await conv_manager.close()

            # ── مرحله ۵: رای‌گیری ──
            if use_voting:
                self.log.info("System", "مرحله ۵: رای‌گیری...")
                print(f"\n{blue('🗳️  مرحله ۵: رای‌گیری نهایی...')}")
                voting_system = None
                try:
                    voters = [ClaudeVoter(), GeminiVoter(), GPTVoter(), GrokVoter()]
                    voting_system = VotingSystem(voters)
                    vote_result = await voting_system.run_vote(content)
                    report_parts.append(vote_result.format_report())
                    if vote_result.critical_issues:
                        self.log.critical("System", f"{len(vote_result.critical_issues)} مشکل بحرانی پیدا شد!")
                        print(f"\n{red('🚨 ' + str(len(vote_result.critical_issues)) + ' مشکل بحرانی!')}")
                    self.log.success("System", "رای‌گیری کامل شد")
                    print(f"{green('  ✅ کامل شد')}")
                except Exception as e:
                    self.log.error("System", "رای‌گیری شکست خورد", e)
                    report_parts.append(yellow(f"⚠️ رای‌گیری شکست خورد: {e}"))
                    print(f"{yellow('  ⚠️ شکست خورد')}")
                finally:
                    if voting_system:
                        await voting_system.close()

            # ── مرحله ۶: آمار حافظه ──
            if use_memory and memory_manager:
                try:
                    stats = memory_manager.get_all_stats()
                    report_parts += ["\n" + "═" * 60, "🧠 آمار حافظه Agent‌ها", "═" * 60]
                    for agent_name, stat in stats.items():
                        report_parts.append(
                            f"  {agent_name}: کوتاه‌مدت={stat['short_term_count']} | بلندمدت={stat['long_term']['total']}"
                        )
                except Exception as e:
                    self.log.error("System", "آمار حافظه شکست خورد", e)

        except Exception as e:
            self.log.critical("System", "خطای کلی سیستم!", e)
            report_parts += [
                red(f"\n🚨 خطای کلی سیستم: {e}"),
                red(f"فایل: {self.log._get_file_info(e)}"),
                f"برای جزئیات بیشتر: {MasterLogger.LOG_FILE}"
            ]

        elapsed = time.time() - self.start_time
        report_parts += ["\n" + "═" * 60, f"⏱️  زمان کل: {elapsed:.2f} ثانیه", "═" * 60]
        self.log.success("System", f"تحلیل کامل شد در {elapsed:.2f} ثانیه")
        return "\n".join(report_parts)

    async def run_from_file(self, file_path):
        try:
            content, language = self.file_handler.read_file(file_path)
            report = await self.analyze(content=content, language=language, source_name=Path(file_path).name)
            saved_to = self.file_handler.save_report(report, file_path)
            if saved_to:
                print(f"\n{green(f'💾 گزارش ذخیره شد: {saved_to}')}")
            return report
        except FileNotFoundError as e:
            self.log.error("System", str(e))
            return red(str(e))
        except Exception as e:
            self.log.critical("System", "خطا در اجرا از فایل", e)
            return red(f"خطا: {e}")

    async def run_from_text(self, text):
        content, language = self.file_handler.read_text(text)
        return await self.analyze(content=content, language=language, source_name="direct_input")


# ==================== CLI ====================
async def main():
    system = MultiAgentSystem()

    ready = await system.initialize()
    if not ready:
        sys.exit(1)

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"\n{cyan(f'📂 تحلیل فایل: {file_path}')}")
        report = await system.run_from_file(file_path)
        print(report)
    else:
        print(f"{cyan('چطور میخوای ادامه بدی؟')}")
        print(f"  {green('1')} — آدرس فایل بده")
        print(f"  {green('2')} — کد رو مستقیم paste کن")
        print(f"  {green('3')} — تست با کد نمونه\n")

        choice = input("انتخاب (1/2/3): ").strip()

        if choice == "1":
            file_path = input("آدرس فایل: ").strip()
            report = await system.run_from_file(file_path)
            print(report)

        elif choice == "2":
            print(f"\n{cyan('کدت رو paste کن (Enter دو بار برای تموم کردن):')}")
            lines = []
            empty_count = 0
            while True:
                line = input()
                if line == "":
                    empty_count += 1
                    if empty_count >= 2:
                        break
                else:
                    empty_count = 0
                lines.append(line)
            code = "\n".join(lines)
            if code.strip():
                report = await system.run_from_text(code)
                print(report)
            else:
                print(red("❌ کدی وارد نشد"))

        elif choice == "3":
            sample = """
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

password = "admin123"
SECRET_KEY = "mysecretkey"
            """
            print(f"\n{cyan('🧪 تست با کد نمونه...')}")
            report = await system.run_from_text(sample)
            print(report)

        else:
            print(red("❌ انتخاب نامعتبر"))


if __name__ == "__main__":
    asyncio.run(main())
