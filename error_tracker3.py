import re
import traceback
import sys
import os
import ast
import linecache
from datetime import datetime
from pathlib import Path


# ==================== رنگ‌ها ====================
class Color:
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    CYAN    = "\033[96m"
    BOLD    = "\033[1m"
    RESET   = "\033[0m"

def red(t):    return f"{Color.RED}{t}{Color.RESET}"
def green(t):  return f"{Color.GREEN}{t}{Color.RESET}"
def yellow(t): return f"{Color.YELLOW}{t}{Color.RESET}"
def cyan(t):   return f"{Color.CYAN}{t}{Color.RESET}"
def bold(t):   return f"{Color.BOLD}{t}{Color.RESET}"


# ==================== Error Location ====================

class ErrorLocation:
    def __init__(
        self,
        file: str,
        line_number: int,
        function_name: str,
        line_content: str,
        error_type: str,
        error_message: str,
        context_lines: list[tuple] = None
    ):
        self.file = file
        self.line_number = line_number
        self.function_name = function_name
        self.line_content = line_content.strip()
        self.error_type = error_type
        self.error_message = error_message
        self.context_lines = context_lines or []
        self.timestamp = datetime.now().strftime("%H:%M:%S")

    def format(self) -> str:
        lines = []

        lines.append(f"\n{'═' * 55}")
        lines.append(red("🚨 خطا پیدا شد!"))
        lines.append(f"{'═' * 55}")

        lines.append(f"\n📁 فایل:     {bold(self.file)}")
        lines.append(f"📍 خط:       {bold(str(self.line_number))}")
        lines.append(f"⚙️  تابع:     {bold(self.function_name)}")
        lines.append(f"❌ نوع خطا:  {red(self.error_type)}")
        lines.append(f"💬 پیام:     {self.error_message}")

        if self.context_lines:
            lines.append(f"\n{'─' * 55}")
            lines.append(cyan("📜 کد اطراف خطا:"))
            lines.append(f"{'─' * 55}")

            for num, content, is_error in self.context_lines:
                if is_error:
                    lines.append(red(f">>> {num:4d} | {content}"))
                    lines.append(red(f"         {'~' * len(content.rstrip())} ← اینجا!"))
                else:
                    lines.append(f"     {num:4d} | {content}")

        lines.append(f"{'═' * 55}\n")
        return "\n".join(lines)


# ==================== Error Tracker ====================

class ErrorTracker:
    def __init__(self, log_file: str = "error_tracker.txt"):
        self.log_file = log_file
        self.errors: list[ErrorLocation] = []
        self.error_counts: dict[str, int] = {}

    def _get_context(
        self,
        file: str,
        error_line: int,
        context: int = 3
    ) -> list[tuple]:
        """خطوط اطراف خطا رو برگردون"""
        result = []
        start = max(1, error_line - context)
        end = error_line + context

        for num in range(start, end + 1):
            content = linecache.getline(file, num)
            if content:
                is_error = (num == error_line)
                result.append((num, content.rstrip(), is_error))

        return result

    def track(self, exc: Exception, module: str = "Unknown") -> ErrorLocation:
        """یه خطا رو رهگیری کن"""
        tb = traceback.extract_tb(exc.__traceback__)

        if tb:
            last_frame = tb[-1]
            file = last_frame.filename
            line_number = last_frame.lineno
            function_name = last_frame.name
            line_content = last_frame.line or ""
            context = self._get_context(file, line_number)
        else:
            file = "unknown"
            line_number = 0
            function_name = "unknown"
            line_content = ""
            context = []

        location = ErrorLocation(
            file=file,
            line_number=line_number,
            function_name=function_name,
            line_content=line_content,
            error_type=type(exc).__name__,
            error_message=str(exc),
            context_lines=context
        )

        self.errors.append(location)
        self.error_counts[file] = self.error_counts.get(file, 0) + 1
        self._save_to_file(location, module)

        return location

    def _save_to_file(self, location: ErrorLocation, module: str):
        """خطا رو توی فایل ذخیره کن"""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 60}\n")
                f.write(f"زمان: {location.timestamp}\n")
                f.write(f"ماژول: {module}\n")
                f.write(f"فایل: {location.file}\n")
                f.write(f"خط: {location.line_number}\n")
                f.write(f"تابع: {location.function_name}\n")
                f.write(f"نوع خطا: {location.error_type}\n")
                f.write(f"پیام: {location.error_message}\n")
                f.write(f"کد: {location.line_content}\n")
                f.write(f"{'=' * 60}\n")
        except OSError as e:
            # فقط OSError رو catch کن، نه همه exception ها
            print(f"⚠️ نمیشه لاگ فایل رو ذخیره کرد: {e}")

    def get_summary(self) -> str:
        if not self.errors:
            return green("✅ هیچ خطایی ثبت نشده!")

        lines = []
        lines.append(bold(f"\n📊 خلاصه خطاها ({len(self.errors)} خطا):"))
        lines.append("─" * 50)

        by_file: dict[str, list[ErrorLocation]] = {}
        for err in self.errors:
            file_name = Path(err.file).name
            if file_name not in by_file:
                by_file[file_name] = []
            by_file[file_name].append(err)

        for file_name, file_errors in by_file.items():
            lines.append(f"\n📁 {bold(file_name)} — {red(str(len(file_errors)) + ' خطا')}")
            for err in file_errors:
                lines.append(
                    f"   خط {err.line_number:4d} | "
                    f"{red(err.error_type):30s} | "
                    f"{err.error_message[:50]}"
                )

        lines.append(f"\n💾 جزئیات کامل در: {self.log_file}")
        return "\n".join(lines)

    def get_most_problematic_file(self) -> str:
        if not self.error_counts:
            return ""
        return max(self.error_counts, key=self.error_counts.get)


# ==================== Static Code Analyzer ====================

class StaticAnalyzer:
    def __init__(self):
        self.issues: list[dict] = []

    def analyze(self, code: str, filename: str = "code") -> list[dict]:
        self.issues = []

        try:
            tree = ast.parse(code)
            self._analyze_tree(tree, code, filename)
        except SyntaxError as e:
            self.issues.append({
                "type": "SyntaxError",
                "severity": "CRITICAL",
                "file": filename,
                "line": e.lineno,
                "message": str(e),
                "description": "خطای syntax — کد اجرا نمیشه",
                "code": e.text or ""
            })

        self._check_text_patterns(code, filename)
        return self.issues

    def _analyze_tree(self, tree: ast.AST, code: str, filename: str):
        lines = code.split("\n")

        for node in ast.walk(tree):

            # division بدون چک صفر
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                self.issues.append({
                    "type": "ZeroDivisionRisk",
                    "severity": "HIGH",
                    "file": filename,
                    "line": getattr(node, "lineno", 0),
                    "message": "تقسیم بدون چک صفر",
                    "description": "اگه مقسوم‌علیه صفر باشه crash میکنه",
                    "suggestion": "قبل از تقسیم چک کن b != 0",
                    "code": lines[getattr(node, "lineno", 1) - 1] if getattr(node, "lineno", 0) else ""
                })

            # except خالی (BareExcept)
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                self.issues.append({
                    "type": "BareExcept",
                    "severity": "MEDIUM",
                    "file": filename,
                    "line": getattr(node, "lineno", 0),
                    "message": "except: خالی",
                    "description": "همه خطاها رو میگیره، حتی KeyboardInterrupt",
                    "suggestion": "از except Exception as e استفاده کن",
                    "code": lines[getattr(node, "lineno", 1) - 1] if getattr(node, "lineno", 0) else ""
                })

            # function بدون return type
            if isinstance(node, ast.FunctionDef):
                if not node.returns and node.name != "__init__":
                    self.issues.append({
                        "type": "MissingReturnType",
                        "severity": "LOW",
                        "file": filename,
                        "line": node.lineno,
                        "message": f"تابع '{node.name}' return type نداره",
                        "description": "type hint کمک میکنه باگ کمتر بشه",
                        "suggestion": f"def {node.name}(...) -> ReturnType:",
                        "code": lines[node.lineno - 1] if node.lineno else ""
                    })

    def _check_text_patterns(self, code: str, filename: str):
        """الگوهای خطرناک رو توی متن پیدا کن"""
        lines = code.split("\n")

        dangerous_patterns = [
            (
                'eval(', 'EvalUsage', 'CRITICAL',
                'eval() کد دلخواه رو اجرا میکنه — خطرناکه',
                'از ast.literal_eval() استفاده کن'
            ),
            (
                'exec(', 'ExecUsage', 'CRITICAL',
                'exec() کد دلخواه رو اجرا میکنه',
                'راه امن‌تری پیدا کن'
            ),
            (
                'password =', 'HardcodedPassword', 'CRITICAL',
                'پسورد مستقیم توی کد!',
                'از environment variable استفاده کن'
            ),
            (
                'secret_key =', 'HardcodedSecret', 'CRITICAL',
                'secret key مستقیم توی کد!',
                'از os.getenv() استفاده کن'
            ),
            (
                'api_key =', 'HardcodedApiKey', 'CRITICAL',
                'API key مستقیم توی کد!',
                'از os.getenv() استفاده کن'
            ),
            (
                'SELECT * FROM', 'SQLInjectionRisk', 'HIGH',
                'SQL query مستقیم — ممکنه injection باشه',
                'از parameterized queries استفاده کن'
            ),
            (
                'WHERE id = " +', 'SQLInjection', 'CRITICAL',
                'SQL Injection قطعی! ورودی مستقیم توی query',
                'از ? یا %s با parameterized query استفاده کن'
            ),
            (
                'print(', 'DebugPrint', 'LOW',
                'print() توی production — از logging استفاده کن',
                'import logging و logger.debug() به جاش'
            ),
            (
                'time.sleep(', 'BlockingSleep', 'MEDIUM',
                'sleep در async code block میکنه',
                'از asyncio.sleep() استفاده کن'
            ),
            (
                'TODO', 'UnfinishedCode', 'LOW',
                'کد ناتموم',
                'قبل از production تموم کن'
            ),
            (
                'FIXME', 'KnownBug', 'MEDIUM',
                'باگ شناخته شده',
                'قبل از production درست کن'
            ),
        ]

        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()
            for pattern, issue_type, severity, description, suggestion in dangerous_patterns:
                if pattern.lower() in line_lower:
                    self.issues.append({
                        "type": issue_type,
                        "severity": severity,
                        "file": filename,
                        "line": line_num,
                        "message": description,
                        "description": description,
                        "suggestion": suggestion,
                        "code": line.strip()
                    })

    def format_report(self) -> str:
        if not self.issues:
            return green("✅ Static analysis: مشکلی پیدا نشد!")

        lines = []
        lines.append(bold(f"\n🔬 Static Analysis — {len(self.issues)} مشکل:"))

        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        severity_emoji = {
            "CRITICAL": "🚨",
            "HIGH":     "🔴",
            "MEDIUM":   "🟡",
            "LOW":      "🟢"
        }

        sorted_issues = sorted(
            self.issues,
            key=lambda x: severity_order.get(x["severity"], 4)
        )

        current_severity = None
        for issue in sorted_issues:
            if issue["severity"] != current_severity:
                current_severity = issue["severity"]
                emoji = severity_emoji.get(current_severity, "⚪")
                lines.append(f"\n{emoji} {bold(current_severity)}:")

            lines.append(f"\n  📍 خط {issue['line']:4d}: {red(issue['type'])}")
            lines.append(f"  💬 {issue['message']}")
            if issue.get("code"):
                lines.append(f"  📝 کد:      {cyan(issue['code'][:80])}")
            if issue.get("suggestion"):
                lines.append(f"  💡 راه‌حل:  {green(issue['suggestion'])}")

        return "\n".join(lines)


# ==================== Runtime Monitor ====================

class RuntimeMonitor:
    def __init__(self, tracker: ErrorTracker):
        self.tracker = tracker
        self.call_count: dict[str, int] = {}
        self.error_rate: dict[str, float] = {}

    def record_call(self, module: str, success: bool):
        if module not in self.call_count:
            self.call_count[module] = 0
        self.call_count[module] += 1

        total = self.call_count[module]
        errors = len([e for e in self.tracker.errors
                     if module.lower() in e.file.lower()])
        self.error_rate[module] = errors / total if total > 0 else 0

    def get_health_status(self) -> dict:
        status = {}
        for module, rate in self.error_rate.items():
            if rate == 0:
                status[module] = {"status": "healthy", "error_rate": "0%"}
            elif rate < 0.1:
                status[module] = {"status": "warning", "error_rate": f"{rate:.0%}"}
            else:
                status[module] = {"status": "critical", "error_rate": f"{rate:.0%}"}
        return status

    def format_health(self) -> str:
        status = self.get_health_status()
        if not status:
            return "هنوز داده‌ای نیست"

        lines = [bold("\n💊 وضعیت سلامت ماژول‌ها:")]
        for module, info in status.items():
            s = info["status"]
            rate = info["error_rate"]
            if s == "healthy":
                lines.append(f"  {green('✅')} {module}: {green('سالم')} ({rate} خطا)")
            elif s == "warning":
                lines.append(f"  {yellow('⚠️')} {module}: {yellow('هشدار')} ({rate} خطا)")
            else:
                lines.append(f"  {red('🚨')} {module}: {red('بحرانی')} ({rate} خطا)")
        return "\n".join(lines)


# ==================== Master Error Handler ====================

class MasterErrorHandler:
    def __init__(self):
        self.tracker = ErrorTracker()
        self.static_analyzer = StaticAnalyzer()
        self.monitor = RuntimeMonitor(self.tracker)

    def analyze_code_before_run(self, code: str, filename: str = "code") -> str:
        issues = self.static_analyzer.analyze(code, filename)
        return self.static_analyzer.format_report()

    def handle_exception(
        self,
        exc: Exception,
        module: str = "Unknown",
        print_immediately: bool = True
    ) -> ErrorLocation:
        location = self.tracker.track(exc, module)
        self.monitor.record_call(module, success=False)

        if print_immediately:
            print(location.format())

        return location

    def record_success(self, module: str):
        self.monitor.record_call(module, success=True)

    def full_report(self) -> str:
        lines = []
        lines.append(bold("\n" + "═" * 60))
        lines.append(bold("🔍 گزارش کامل Error Tracker"))
        lines.append(bold("═" * 60))
        lines.append(self.tracker.get_summary())
        lines.append(self.monitor.format_health())

        if self.tracker.errors:
            worst = self.tracker.get_most_problematic_file()
            if worst:
                lines.append(f"\n⚠️  مشکل‌دارترین فایل: {red(Path(worst).name)}")

        lines.append(bold("═" * 60))
        return "\n".join(lines)


# ==================== نمونه استفاده ====================
def example_usage():
    handler = MasterErrorHandler()

    sample_code = """
import os

password = "admin123"
api_key = "sk-abc123"

def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    return query

def divide(a, b):
    return a / b

def process():
    try:
        result = divide(10, 0)
    except:
        pass

x = eval(input("عدد: "))
    """

    print(bold("\n🔬 تحلیل Static کد نمونه:"))
    print(handler.analyze_code_before_run(sample_code, "sample.py"))

    print(bold("\n🧪 شبیه‌سازی خطاهای Runtime:"))

    errors_to_test = [
        (ZeroDivisionError("division by zero"), "agents2.py"),
        (ConnectionError("API timeout"), "conversation2.py"),
        (KeyError("user_id not found"), "voting2.py"),
        (ValueError("invalid token"), "memory2.py"),
    ]

    for exc, module in errors_to_test:
        try:
            raise exc
        except Exception as e:
            location = handler.handle_exception(e, module)
            handler.record_success(module)

    print(handler.full_report())


if __name__ == "__main__":
    example_usage()
