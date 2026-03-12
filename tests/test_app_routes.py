import asyncio
import sys
import types

from fastapi import BackgroundTasks
from fastapi.routing import APIRoute


def test_delivery_endpoints_exist_and_share_same_background_task():
    if "cgi" not in sys.modules:
        cgi_stub = types.ModuleType("cgi")

        def parse_header(value: str) -> tuple[str, dict[str, str]]:
            return value, {}

        setattr(cgi_stub, "parse_header", parse_header)
        sys.modules["cgi"] = cgi_stub

    from app import app, deliver_now, push_now

    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}

    assert "/api/actions/deliver-now" in paths
    assert "/api/actions/push-now" in paths

    push_tasks = BackgroundTasks()
    deliver_tasks = BackgroundTasks()

    push_response = asyncio.run(push_now(push_tasks))
    deliver_response = asyncio.run(deliver_now(deliver_tasks))

    assert push_response == {
        "success": True,
        "message": "论文投递任务已在后台启动",
    }
    assert deliver_response == {
        "success": True,
        "message": "论文投递任务已在后台启动",
    }
    assert len(push_tasks.tasks) == 1
    assert len(deliver_tasks.tasks) == 1
    assert push_tasks.tasks[0].func is deliver_tasks.tasks[0].func
