import json
import os
import time
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


# ==================== Memory Types ====================

class MemoryType:
    SHORT_TERM  = "short_term"
    LONG_TERM   = "long_term"
    PATTERN     = "pattern"
    USER        = "user"
    ERROR       = "error"
    SUCCESS     = "success"


# ==================== Memory Entry ====================

class MemoryEntry:
    def __init__(
        self,
        content: str,
        memory_type: str,
        agent_name: str,
        importance: int = 5,
        tags: list[str] = None,
    ):
        # از uuid برای جلوگیری از collision استفاده میکنیم
        self.id = str(uuid.uuid4())[:8]
        self.content = content
        self.memory_type = memory_type
        self.agent_name = agent_name
        self.importance = max(1, min(10, importance))  # clamp بین ۱ تا ۱۰
        self.tags = tags or []
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.access_count = 0
        self.last_accessed: Optional[str] = None

    def access(self):
        self.access_count += 1
        self.last_accessed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "agent_name": self.agent_name,
            "importance": self.importance,
            "tags": self.tags,
            "timestamp": self.timestamp,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        entry = cls(
            content=data["content"],
            memory_type=data["memory_type"],
            agent_name=data["agent_name"],
            importance=data["importance"],
            tags=data["tags"]
        )
        entry.id = data["id"]
        entry.timestamp = data["timestamp"]
        entry.access_count = data["access_count"]
        entry.last_accessed = data["last_accessed"]
        return entry

    def __repr__(self):
        return (
            f"[{self.id}] {self.agent_name} | "
            f"{self.memory_type} | "
            f"importance:{self.importance} | "
            f"{self.timestamp}"
        )


# ==================== Short Term Memory ====================

class ShortTermMemory:
    def __init__(self, max_size: int = 50):
        self.memories: list[MemoryEntry] = []
        self.max_size = max_size

    def add(self, entry: MemoryEntry):
        # duplicate بر اساس content + agent_name چک میشه
        for m in self.memories:
            if m.content == entry.content and m.agent_name == entry.agent_name:
                m.access()
                return

        self.memories.append(entry)

        # اگه پر شد قدیمی‌ترین و کم‌اهمیت‌ترین رو حذف کن
        if len(self.memories) > self.max_size:
            self.memories.sort(key=lambda x: (x.importance, x.access_count))
            self.memories.pop(0)

    def get_all(self) -> list[MemoryEntry]:
        return self.memories

    def get_by_tag(self, tag: str) -> list[MemoryEntry]:
        return [m for m in self.memories if tag in m.tags]

    def get_recent(self, n: int = 10) -> list[MemoryEntry]:
        return self.memories[-n:]

    def clear(self):
        self.memories = []

    def to_context(self) -> str:
        if not self.memories:
            return "حافظه کوتاه‌مدت خالیه"
        lines = ["📝 حافظه کوتاه‌مدت:"]
        for m in self.get_recent(10):
            preview = m.content[:100]
            suffix = "..." if len(m.content) > 100 else ""
            lines.append(f"  [{m.memory_type}] {preview}{suffix}")
        return "\n".join(lines)


# ==================== Long Term Memory ====================

# مسیر پیش‌فرض برای ذخیره فایل‌های حافظه
DEFAULT_MEMORY_DIR = Path("./data/memory")


class LongTermMemory:
    def __init__(self, agent_name: str, file_path: str = None):
        self.agent_name = agent_name
        # ذخیره در پوشه data/memory به جای working directory
        if file_path:
            self.file_path = Path(file_path)
        else:
            DEFAULT_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            self.file_path = DEFAULT_MEMORY_DIR / f"memory_{agent_name.lower()}.json"
        self.memories: list[MemoryEntry] = []
        self._load()

    def _load(self):
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.memories = [MemoryEntry.from_dict(d) for d in data]
            except Exception as e:
                print(f"⚠️ خطا در بارگذاری حافظه {self.agent_name}: {e}")
                self.memories = []

    def _save(self):
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(
                    [m.to_dict() for m in self.memories],
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except OSError as e:
            print(f"⚠️ خطا در ذخیره حافظه {self.agent_name}: {e}")

    def add(self, entry: MemoryEntry):
        """اضافه کردن خاطره — duplicate بر اساس content + agent_name چک میشه"""
        for m in self.memories:
            if m.content == entry.content and m.agent_name == entry.agent_name:
                m.access()
                self._save()
                return

        self.memories.append(entry)
        self._save()

    def get_all(self) -> list[MemoryEntry]:
        return self.memories

    def get_by_type(self, memory_type: str) -> list[MemoryEntry]:
        return [m for m in self.memories if m.memory_type == memory_type]

    def get_by_tag(self, tag: str) -> list[MemoryEntry]:
        result = [m for m in self.memories if tag in m.tags]
        for m in result:
            m.access()
        return result

    def get_important(self, min_importance: int = 7) -> list[MemoryEntry]:
        return [m for m in self.memories if m.importance >= min_importance]

    def search(self, keyword: str) -> list[MemoryEntry]:
        keyword_lower = keyword.lower()
        result = [
            m for m in self.memories
            if keyword_lower in m.content.lower()
            or keyword_lower in " ".join(m.tags).lower()
        ]
        for m in result:
            m.access()
        self._save()
        return result

    def forget(self, memory_id: str) -> bool:
        before = len(self.memories)
        self.memories = [m for m in self.memories if m.id != memory_id]
        if len(self.memories) < before:
            self._save()
            return True
        return False

    def forget_old(self, days: int = 30) -> int:
        cutoff = time.time() - (days * 86400)
        before = len(self.memories)
        self.memories = [
            m for m in self.memories
            if m.importance >= 8 or
            datetime.strptime(m.timestamp, "%Y-%m-%d %H:%M:%S").timestamp() > cutoff
        ]
        removed = before - len(self.memories)
        if removed > 0:
            self._save()
        return removed

    def to_context(self, limit: int = 10) -> str:
        if not self.memories:
            return "حافظه بلندمدت خالیه"

        sorted_memories = sorted(
            self.memories,
            key=lambda x: (x.importance, x.access_count),
            reverse=True
        )

        lines = ["🧠 حافظه بلندمدت (مهم‌ترین‌ها):"]
        for m in sorted_memories[:limit]:
            preview = m.content[:100]
            suffix = "..." if len(m.content) > 100 else ""
            lines.append(
                f"  [{m.memory_type}] "
                f"(importance:{m.importance}) "
                f"{preview}{suffix}"
            )
        return "\n".join(lines)

    def stats(self) -> dict:
        return {
            "total": len(self.memories),
            "by_type": {
                t: len([m for m in self.memories if m.memory_type == t])
                for t in [
                    MemoryType.SHORT_TERM,
                    MemoryType.LONG_TERM,
                    MemoryType.PATTERN,
                    MemoryType.USER,
                    MemoryType.ERROR,
                    MemoryType.SUCCESS
                ]
            },
            "avg_importance": (
                sum(m.importance for m in self.memories) / len(self.memories)
                if self.memories else 0
            )
        }


# ==================== Pattern Memory ====================

DEFAULT_PATTERN_DIR = Path("./data/patterns")


class PatternMemory:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.patterns: dict[str, int] = {}
        DEFAULT_PATTERN_DIR.mkdir(parents=True, exist_ok=True)
        self.file_path = DEFAULT_PATTERN_DIR / f"patterns_{agent_name.lower()}.json"
        self._load()

    def _load(self):
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.patterns = json.load(f)
            except Exception as e:
                print(f"⚠️ خطا در بارگذاری patterns: {e}")
                self.patterns = {}

    def _save(self):
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.patterns, f, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"⚠️ خطا در ذخیره patterns: {e}")

    def record(self, pattern: str):
        self.patterns[pattern] = self.patterns.get(pattern, 0) + 1
        self._save()

    def get_common(self, min_count: int = 3) -> list[tuple]:
        common = [
            (pattern, count)
            for pattern, count in self.patterns.items()
            if count >= min_count
        ]
        return sorted(common, key=lambda x: x[1], reverse=True)

    def to_context(self) -> str:
        common = self.get_common(min_count=2)
        if not common:
            return "هنوز الگوی تکراری پیدا نشده"

        lines = ["🔄 الگوهای تکراری که دیدم:"]
        for pattern, count in common[:10]:
            lines.append(f"  ({count}x) {pattern}")
        return "\n".join(lines)


# ==================== Agent Memory ====================

class AgentMemory:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.short_term = ShortTermMemory(max_size=50)
        self.long_term = LongTermMemory(agent_name)
        self.patterns = PatternMemory(agent_name)

    def remember(
        self,
        content: str,
        memory_type: str = MemoryType.SHORT_TERM,
        importance: int = 5,
        tags: list[str] = None,
        persist: bool = False
    ):
        entry = MemoryEntry(
            content=content,
            memory_type=memory_type,
            agent_name=self.agent_name,
            importance=importance,
            tags=tags or []
        )

        self.short_term.add(entry)

        if persist or importance >= 7:
            self.long_term.add(entry)

        if memory_type == MemoryType.PATTERN:
            self.patterns.record(content)

    def remember_error(self, error: str, context: str = ""):
        self.remember(
            content=f"خطا: {error} | context: {context}",
            memory_type=MemoryType.ERROR,
            importance=8,
            tags=["error", "bug"],
            persist=True
        )

    def remember_success(self, success: str):
        self.remember(
            content=success,
            memory_type=MemoryType.SUCCESS,
            importance=7,
            tags=["success"],
            persist=True
        )

    def remember_user(self, info: str):
        self.remember(
            content=info,
            memory_type=MemoryType.USER,
            importance=9,
            tags=["user"],
            persist=True
        )

    def recall(self, keyword: str = None) -> str:
        lines = []

        lines.append(self.short_term.to_context())
        lines.append("")

        lines.append(self.patterns.to_context())
        lines.append("")

        if keyword:
            search_results = self.long_term.search(keyword)
            if search_results:
                lines.append(f"🔍 نتایج جستجو برای '{keyword}':")
                for m in search_results[:5]:
                    lines.append(f"  {m.content[:150]}...")
        else:
            lines.append(self.long_term.to_context())

        return "\n".join(lines)

    def get_stats(self) -> dict:
        return {
            "agent": self.agent_name,
            "short_term_count": len(self.short_term.get_all()),
            "long_term": self.long_term.stats(),
            "pattern_count": len(self.patterns.patterns)
        }

    def clear_session(self):
        self.short_term.clear()

    def full_reset(self):
        self.short_term.clear()
        self.long_term.memories = []
        self.long_term._save()
        self.patterns.patterns = {}
        self.patterns._save()


# ==================== Global Memory Manager ====================

class MemoryManager:
    def __init__(self):
        self.agent_memories: dict[str, AgentMemory] = {}

    def get_or_create(self, agent_name: str) -> AgentMemory:
        if agent_name not in self.agent_memories:
            self.agent_memories[agent_name] = AgentMemory(agent_name)
        return self.agent_memories[agent_name]

    def share_memory(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        importance: int = 6
    ):
        target = self.get_or_create(to_agent)
        target.remember(
            content=f"از {from_agent}: {content}",
            memory_type=MemoryType.LONG_TERM,
            importance=importance,
            tags=["shared", from_agent.lower()],
            persist=True
        )

    def broadcast_memory(self, from_agent: str, content: str, importance: int = 6):
        for agent_name, memory in self.agent_memories.items():
            if agent_name != from_agent:
                memory.remember(
                    content=f"از {from_agent}: {content}",
                    memory_type=MemoryType.LONG_TERM,
                    importance=importance,
                    tags=["broadcast", from_agent.lower()],
                    persist=True
                )

    def get_all_stats(self) -> dict:
        return {
            name: memory.get_stats()
            for name, memory in self.agent_memories.items()
        }

    def clear_all_sessions(self):
        for memory in self.agent_memories.values():
            memory.clear_session()


# ==================== Main (تست) ====================
def main():
    print("🧠 تست Memory System\n")

    manager = MemoryManager()

    claude_memory = manager.get_or_create("Claude")
    claude_memory.remember("SQL injection توی این کد دیدم", importance=9, tags=["security", "sql"])
    claude_memory.remember_error("API timeout", "وقتی کد طولانی بود")
    claude_memory.remember_user("این کاربر Python میزنه و تازه‌کاره")
    claude_memory.remember("buffer overflow pattern دیدم", memory_type=MemoryType.PATTERN)
    claude_memory.remember("buffer overflow pattern دیدم", memory_type=MemoryType.PATTERN)
    claude_memory.remember("buffer overflow pattern دیدم", memory_type=MemoryType.PATTERN)

    gemini_memory = manager.get_or_create("Gemini")
    gemini_memory.remember("O(n²) loop pattern دیدم", importance=8, tags=["performance"])
    gemini_memory.remember("O(n²) loop pattern دیدم", memory_type=MemoryType.PATTERN)
    gemini_memory.remember("O(n²) loop pattern دیدم", memory_type=MemoryType.PATTERN)

    manager.broadcast_memory(
        from_agent="Claude",
        content="این کاربر به امنیت حساسه، همیشه SQL injection چک کن",
        importance=9
    )

    print("📊 آمار کل:")
    stats = manager.get_all_stats()
    for agent, stat in stats.items():
        print(f"\n{agent}:")
        print(f"  کوتاه‌مدت: {stat['short_term_count']}")
        print(f"  بلندمدت: {stat['long_term']['total']}")
        print(f"  الگوها: {stat['pattern_count']}")

    print("\n" + "=" * 50)
    print("🧠 recall Claude:")
    print(claude_memory.recall(keyword="SQL"))

    print("\n" + "=" * 50)
    print("🔄 الگوهای Gemini:")
    print(gemini_memory.patterns.to_context())


if __name__ == "__main__":
    main()
