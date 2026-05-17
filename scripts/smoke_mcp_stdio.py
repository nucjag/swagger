#!/usr/bin/env python3
"""Smoke test for MCP stdio handshake and tools listing using MCP framing."""

from __future__ import annotations

import io
import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path


def _stderr_reader(stream, target_queue: queue.Queue[str]) -> None:
    for line in iter(stream.readline, b""):
        target_queue.put(line.decode("utf-8", errors="replace").rstrip("\n"))


def _read_exact(stream, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError("Unexpected EOF while reading MCP frame body")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _stdout_reader(stream, target_queue: queue.Queue[dict]) -> None:
    buffer = io.BufferedReader(stream)
    while True:
        headers: dict[str, str] = {}
        while True:
            line = buffer.readline()
            if not line:
                return
            if line in (b"\r\n", b"\n"):
                break
            raw = line.decode("utf-8", errors="replace").strip()
            if ":" in raw:
                k, v = raw.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        if "content-length" not in headers:
            continue
        length = int(headers["content-length"])
        payload = _read_exact(buffer, length)
        msg = json.loads(payload.decode("utf-8"))
        target_queue.put(msg)


def _wait_for_json_response(
    out_queue: queue.Queue[dict], request_id: int, timeout_s: float
) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            payload = out_queue.get(timeout=0.2)
        except queue.Empty:
            continue
        if payload.get("id") == request_id:
            return payload
    raise TimeoutError(f"Timeout waiting for response id={request_id}")


def _wait_for_ready(err_queue: queue.Queue[str], timeout_s: float) -> list[str]:
    deadline = time.time() + timeout_s
    seen: list[str] = []
    while time.time() < deadline:
        try:
            line = err_queue.get(timeout=0.2)
        except queue.Empty:
            continue
        seen.append(line)
        if "Waiting for MCP connections..." in line:
            return seen
    return seen


def _send_mcp_message(stdin, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    frame = b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body
    stdin.write(frame)
    stdin.flush()


def main() -> int:
    root = Path(__file__).resolve().parents[4]
    start_script = root / ".claude/mcp/swagger/start-openapi-mcp.sh"
    env = os.environ.copy()
    env.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")
    env.setdefault("FASTMCP_CHECK_FOR_UPDATES", "off")
    env.setdefault("LOG_LEVEL", "INFO")

    proc = subprocess.Popen(
        ["bash", str(start_script)],
        cwd=str(root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert proc.stdin and proc.stdout and proc.stderr

    out_queue: queue.Queue[dict] = queue.Queue()
    err_queue: queue.Queue[str] = queue.Queue()

    out_thread = threading.Thread(
        target=_stdout_reader, args=(proc.stdout, out_queue), daemon=True
    )
    err_thread = threading.Thread(
        target=_stderr_reader, args=(proc.stderr, err_queue), daemon=True
    )
    out_thread.start()
    err_thread.start()

    try:
        ready_logs = _wait_for_ready(err_queue, timeout_s=20)
        if not ready_logs:
            raise RuntimeError("Server did not emit startup logs")

        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "smoke-test", "version": "0.1"},
            },
        }
        _send_mcp_message(proc.stdin, init_req)
        init_resp = _wait_for_json_response(out_queue, 1, timeout_s=20)
        if "result" not in init_resp:
            raise RuntimeError(f"initialize failed: {init_resp}")

        initialized_ntf = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        _send_mcp_message(proc.stdin, initialized_ntf)

        tools_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        _send_mcp_message(proc.stdin, tools_req)
        tools_resp = _wait_for_json_response(out_queue, 2, timeout_s=20)
        if "result" not in tools_resp or "tools" not in tools_resp["result"]:
            raise RuntimeError(f"tools/list failed: {tools_resp}")

        print(
            f"OK: protocol={init_resp['result'].get('protocolVersion')} "
            f"tools={len(tools_resp['result']['tools'])}"
        )
        return 0
    except Exception:
        tail = []
        while True:
            try:
                tail.append(err_queue.get_nowait())
            except queue.Empty:
                break
        if tail:
            print("stderr tail:")
            for line in tail[-40:]:
                print(line)
        raise
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
