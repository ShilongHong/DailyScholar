def test_openclaw_notifier_builds_cli_command():
    from delivery.openclaw_notifier import OpenClawNotifier

    notifier = OpenClawNotifier(
        binary_path="openclaw",
        session_key="main",
        timeout_seconds=30,
    )
    command = notifier.build_send_command("每日论文摘要")

    assert command[0] == "openclaw"
    assert "main" in " ".join(command)


def test_openclaw_notifier_formats_daily_digest():
    from delivery.openclaw_notifier import OpenClawNotifier

    notifier = OpenClawNotifier(
        binary_path="openclaw",
        session_key="main",
        timeout_seconds=30,
    )
    content = notifier.render_digest(
        [
            {
                "TitleCN": "论文A",
                "Stars": 92,
                "Link": "https://example.com/a",
            }
        ]
    )

    assert "论文A" in content
    assert "92" in content


def test_openclaw_notifier_send_papers_runs_command():
    from delivery.openclaw_notifier import OpenClawNotifier

    calls = []

    def fake_runner(command, capture_output, text, timeout, check):
        calls.append((command, capture_output, text, timeout, check))

        class Result:
            returncode = 0

        return Result()

    notifier = OpenClawNotifier(
        binary_path="openclaw",
        session_key="main",
        timeout_seconds=30,
        runner=fake_runner,
    )

    assert notifier.send_papers([{"TitleCN": "论文A", "Stars": 92}]) is True
    assert calls[0][0][0] == "openclaw"
