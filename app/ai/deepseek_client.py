"""DeepSeek 的最小 HTTP 客户端；不执行本地文件或数据库操作。"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


class DeepSeekClientError(RuntimeError):
    """可安全展示给用户的 AI 请求错误，不包含 API Key。"""


@dataclass(frozen=True)
class DeepSeekConfig:
    enabled: bool = False
    api_key: str = ""
    model: str = "deepseek-chat"
    base_url: str = ""

    @classmethod
    def load(cls, env_path: str | Path | None = None) -> "DeepSeekConfig":
        values = dict(os.environ)
        path = Path(env_path) if env_path else Path(__file__).resolve().parents[2] / ".env"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip()
        return cls(values.get("DEEPSEEK_ENABLED", "false").lower() in {"1", "true", "yes"}, values.get("DEEPSEEK_API_KEY", ""), values.get("DEEPSEEK_MODEL", "deepseek-chat"), values.get("DEEPSEEK_BASE_URL", ""))

    def save(self, env_path: str | Path) -> None:
        path = Path(env_path)
        path.write_text("\n".join((
            f"DEEPSEEK_ENABLED={'true' if self.enabled else 'false'}", f"DEEPSEEK_API_KEY={self.api_key}",
            f"DEEPSEEK_MODEL={self.model}", f"DEEPSEEK_BASE_URL={self.base_url}", "",
        )), encoding="utf-8")


class DeepSeekClient:
    def __init__(self, env_path: str | Path | None = None, timeout_seconds: int = 20) -> None:
        self.env_path = Path(env_path) if env_path else Path(__file__).resolve().parents[2] / ".env"
        self.timeout_seconds = timeout_seconds

    def request_template_json(self, user_requirement: str) -> str:
        return self._request(self._config(), [{"role": "system", "content": "你是模板 Schema 解析器。只返回 JSON 对象，不要 Markdown、解释、代码或其他文字。"}, {"role": "user", "content": user_requirement}])

    def request_table_dataset_json(self, text: str) -> str:
        """仅发送用户当前粘贴的文本；绝不读取或发送本地学生库。"""
        prompt = """将下列用户文本结构化为 JSON。只返回对象：
{"columns":["字段名"],"rows":[{"字段名":"值"}]}
不得补充原文本没有的信息；不得返回 Markdown、解释、数据库操作、Excel 指令或文件内容。文本：""" + text
        return self._request(self._config(), [{"role": "system", "content": "你是受限文本结构化器，只返回 JSON。"}, {"role": "user", "content": prompt}])

    def test_connection(self) -> None:
        """仅验证 API 可响应；不解析需求、不生成 Schema 或 Excel。"""
        self._request(self._config(), [{"role": "user", "content": "请仅回复 OK。"}])

    def _config(self) -> DeepSeekConfig:
        config = DeepSeekConfig.load(self.env_path)
        if not config.enabled:
            raise DeepSeekClientError("DeepSeek 尚未启用，可继续使用手动创建。")
        if not config.api_key:
            raise DeepSeekClientError("DeepSeek API Key 未配置，可继续使用手动创建。")
        if not config.base_url:
            raise DeepSeekClientError("DeepSeek API 地址未配置，可继续使用手动创建。")
        return config

    def _request(self, config: DeepSeekConfig, messages: list[dict[str, str]]) -> str:
        payload = json.dumps({"model": config.model, "messages": messages, "temperature": 0.1}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(config.base_url.rstrip("/") + "/chat/completions", data=payload, headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            messages = {401: "DeepSeek 身份验证失败，请检查 API Key。", 403: "DeepSeek 没有访问权限。", 429: "DeepSeek 请求过于频繁，请稍后再试。"}
            raise DeepSeekClientError(messages.get(error.code, f"DeepSeek 服务请求失败（HTTP {error.code}）。")) from error
        except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
            raise DeepSeekClientError("无法连接 DeepSeek 或请求超时，可继续使用手动创建。") from error
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise DeepSeekClientError("DeepSeek 返回格式异常，请稍后重试。") from error
        try:
            return str(result["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as error:
            raise DeepSeekClientError("DeepSeek 未返回可用内容。") from error
