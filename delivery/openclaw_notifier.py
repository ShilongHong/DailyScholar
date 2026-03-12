from typing import Final
import subprocess


RunnerType = object


class OpenClawNotifier:
    binary_path: Final[str]
    session_key: Final[str]
    timeout_seconds: Final[int]

    def __init__(
        self,
        binary_path: str,
        session_key: str,
        timeout_seconds: int,
        runner=subprocess.run,
    ):
        self.binary_path = binary_path
        self.session_key = session_key
        self.timeout_seconds = timeout_seconds
        self.runner = runner

    def build_send_command(self, content: str) -> list[str]:
        return [
            self.binary_path,
            "sessions",
            "send",
            "--session",
            self.session_key,
            "--message",
            content,
            "--timeout",
            str(self.timeout_seconds),
        ]

    def render_digest(self, papers: list[dict[str, object]]) -> str:
        lines = ["今日论文摘要"]
        for index, paper in enumerate(papers, start=1):
            lines.append(
                f"{index}. {paper.get('TitleCN') or paper.get('Title') or '未命名论文'}"
            )
            lines.append(f"评分: {paper.get('Stars', 0)}")
            if paper.get("Link"):
                lines.append(f"链接: {paper['Link']}")
        return "\n".join(lines)

    def send_papers(self, papers: list[dict[str, object]]) -> bool:
        content = self.render_digest(papers)
        command = self.build_send_command(content)
        result = self.runner(
            command,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        return getattr(result, "returncode", 1) == 0
