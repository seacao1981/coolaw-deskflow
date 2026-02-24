"""WeCom (Enterprise WeChat) channel adapter for IM integration.

Provides:
- WeCom message parsing (text, card, image)
- WeCom message sending (text, markdown, card)
- Callback signature verification (AES encryption)
- Health check for WeCom connection
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from Crypto.Cipher import AES

from deskflow.channels.gateway import (
    BaseMessage,
    ChannelAdapter,
    MessageType,
    OutboundMessage,
)
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


# PKCS7 padding for AES
def _pkcs7_pad(data: bytes, block_size: int = 32) -> bytes:
    """Add PKCS7 padding."""
    padding_len = block_size - len(data) % block_size
    return data + bytes([padding_len] * padding_len)


def _pkcs7_unpad(data: bytes) -> bytes:
    """Remove PKCS7 padding."""
    padding_len = data[-1]
    return data[:-padding_len]


@dataclass
class WeComMessage(BaseMessage):
    """WeCom-specific message with additional fields."""

    _channel_id: str = "wecom"
    _content: str = ""
    _sender_id: str = ""
    _message_id: str = field(default_factory=lambda: "")
    _message_type: MessageType = MessageType.TEXT
    _timestamp: datetime = field(default_factory=datetime.now)
    _metadata: dict[str, Any] = field(default_factory=dict)

    # WeCom-specific fields
    msg_id: str = ""  # WeCom message ID
    agent_id: str = ""  # Agent ID
    corp_id: str = ""  # Corporation ID

    def __post_init__(self):
        if not self._message_id:
            self._message_id = self.msg_id or f"wecom_{int(time.time())}"


@dataclass
class WeComConfig:
    """WeCom configuration."""

    corp_id: str = ""
    agent_id: str = ""
    secret: str = ""
    token: str = ""
    encoding_aes_key: str = ""
    webhook_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "corp_id": self.corp_id,
            "agent_id": self.agent_id,
            "secret": self.secret,
            "token": self.token,
            "encoding_aes_key": self.encoding_aes_key,
            "webhook_url": self.webhook_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WeComConfig:
        """Create config from dictionary."""
        return cls(
            corp_id=data.get("corp_id", ""),
            agent_id=data.get("agent_id", ""),
            secret=data.get("secret", ""),
            token=data.get("token", ""),
            encoding_aes_key=data.get("encoding_aes_key", ""),
            webhook_url=data.get("webhook_url", ""),
        )


class WeComAdapter(ChannelAdapter):
    """WeCom channel adapter."""

    def __init__(
        self,
        config: WeComConfig | None = None,
        channel_id: str = "wecom",
    ):
        super().__init__(channel_id=channel_id, config=config.to_dict() if config else {})
        self._config = config or WeComConfig()
        self._client = httpx.AsyncClient(timeout=30.0)
        self._access_token: str | None = None
        self._token_expire_at: int = 0

    @property
    def channel_type(self) -> str:
        return "wecom"

    def to_dict(self) -> dict[str, Any]:
        """Convert adapter config to dictionary."""
        return self._config.to_dict()

    @staticmethod
    def from_dict(data: dict[str, Any]) -> WeComAdapter:
        """Create adapter from dictionary."""
        config = WeComConfig.from_dict(data)
        return WeComAdapter(config=config, channel_id=data.get("channel_id", "wecom"))

    async def _get_access_token(self) -> str:
        """Get WeCom access token with caching."""
        current_time = int(time.time())

        # Return cached token if still valid
        if self._access_token and current_time < self._token_expire_at:
            return self._access_token

        # Request new token
        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {
            "corpid": self._config.corp_id,
            "corpsecret": self._config.secret,
        }

        async with self._client as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data.get("errcode") != 0:
            raise ValueError(f"Failed to get access token: {data}")

        self._access_token = data["access_token"]
        # Token expires in 7200 seconds, refresh 600 seconds early
        self._token_expire_at = current_time + data.get("expires_in", 7200) - 600

        logger.info("wecom_access_token_refreshed", expire_in=data.get("expires_in", 7200))
        return self._access_token

    def _verify_signature(
        self,
        msg_signature: str,
        timestamp: str,
        nonce: str,
        echo_str: str | None = None,
    ) -> str | bool:
        """Verify WeCom callback signature.

        For URL verification: returns decrypted echo_str
        For message verification: returns True/False
        """
        if not self._config.token:
            logger.warning("wecom_token_not_configured")
            return echo_str or True

        # Sort and concat for signature
        sorted_list = sorted([self._config.token, timestamp, nonce])
        concatenated = "".join(sorted_list)
        calculated_hash = hashlib.sha1(concatenated.encode()).hexdigest()

        if calculated_hash != msg_signature:
            return False

        # If echo_str provided, decrypt it for URL verification
        if echo_str:
            try:
                return self._decrypt_message(echo_str)
            except Exception as e:
                logger.error("wecom_echo_str_decrypt_failed", error=str(e))
                return False

        return True

    def _decrypt_message(self, encrypted: str) -> str:
        """Decrypt WeCom message using AES."""
        if not self._config.encoding_aes_key:
            return encrypted

        # Decode base64 and extract key
        aes_key = base64.b64decode(self._config.encoding_aes_key + "=")
        encrypted_data = base64.b64decode(encrypted)

        # IV is first 16 bytes
        iv = encrypted_data[:16]
        ciphertext = encrypted_data[16:]

        # Decrypt
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        decrypted = _pkcs7_unpad(cipher.decrypt(ciphertext))

        # Remove 4-byte length prefix and 4-byte corp_id suffix
        msg_len = int.from_bytes(decrypted[:4], "big")
        message = decrypted[4 : 4 + msg_len]

        return message.decode("utf-8")

    def _encrypt_message(self, message: str, timestamp: str, nonce: str) -> dict[str, Any]:
        """Encrypt message for WeCom response."""
        if not self._config.encoding_aes_key:
            return {"msg": message}

        aes_key = base64.b64decode(self._config.encoding_aes_key + "=")

        # Build message: 4-byte length + message + 4-byte random corp_id
        msg_bytes = message.encode("utf-8")
        rand_str = os.urandom(4)
        padded_msg = _pkcs7_pad(
            len(msg_bytes).to_bytes(4, "big") + msg_bytes + rand_str
        )

        # Encrypt
        iv = os.urandom(16)
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(padded_msg)

        # Encode
        encrypted_b64 = base64.b64encode(iv + encrypted).decode()

        # Generate signature
        sorted_list = sorted([self._config.token, timestamp, nonce, encrypted_b64])
        concatenated = "".join(sorted_list)
        signature = hashlib.sha1(concatenated.encode()).hexdigest()

        return {
            "Encrypt": encrypted_b64,
            "MsgSignature": signature,
            "TimeStamp": timestamp,
            "Nonce": nonce,
        }

    def _parse_wecom_message_type(self, msg_type: str) -> MessageType:
        """Parse WeCom message type to MessageType."""
        type_mapping = {
            "text": MessageType.TEXT,
            "markdown": MessageType.TEXT,
            "image": MessageType.IMAGE,
            "voice": MessageType.VOICE,
            "video": MessageType.VIDEO,
            "file": MessageType.FILE,
            "link": MessageType.LINK,
            "textcard": MessageType.LINK,
            "news": MessageType.LINK,
        }
        return type_mapping.get(msg_type, MessageType.TEXT)

    async def parse_message(self, raw_data: dict[str, Any]) -> WeComMessage:
        """Parse WeCom callback data into WeComMessage.

        Args:
            raw_data: Raw callback data from WeCom

        Returns:
            Parsed WeComMessage instance
        """
        # Check if this is an encrypted message
        if raw_data.get("Encrypt"):
            encrypted = raw_data["Encrypt"]
            decrypted = self._decrypt_message(encrypted)

            # Parse decrypted XML/JSON
            import json
            try:
                raw_data = json.loads(decrypted)
            except json.JSONDecodeError:
                # Handle XML format
                raw_data = self._parse_xml(decrypted)

        # Handle URL verification
        if "echostr" in raw_data:
            logger.info("wecom_url_verification_received")
            msg_signature = raw_data.get("msg_signature", "")
            timestamp = raw_data.get("timestamp", "")
            nonce = raw_data.get("nonce", "")

            result = self._verify_signature(msg_signature, timestamp, nonce, raw_data["echostr"])
            if result is False:
                raise ValueError("Signature verification failed")

            return WeComMessage(
                content=str(result) if isinstance(result, bytes) else result,
                sender_id="wecom_system",
                _metadata={"echo_verification": True},
            )

        # Parse message data
        msg_type = raw_data.get("MsgType", "").lower()
        event = raw_data.get("Event", "").lower()

        # Handle events
        if event:
            return WeComMessage(
                _content=f"event:{event}",
                _sender_id=raw_data.get("FromUserName", "unknown"),
                _message_type=MessageType.SYSTEM,
                _metadata={"event": event, "raw_data": raw_data},
            )

        # Parse content based on type
        if msg_type == "text":
            content = raw_data.get("Content", "")
        elif msg_type == "markdown":
            content = raw_data.get("Content", "")
        else:
            content = raw_data.get("Content", raw_data.get("MediaId", ""))

        return WeComMessage(
            _channel_id="wecom",
            _content=content,
            _sender_id=raw_data.get("FromUserName", "unknown"),
            _message_type=self._parse_wecom_message_type(msg_type),
            _timestamp=datetime.fromtimestamp(raw_data.get("CreateTime", 0)),
            _metadata={
                "raw_data": raw_data,
                "message_type": msg_type,
                "agent_id": raw_data.get("AgentID", ""),
            },
            msg_id=raw_data.get("MsgId", ""),
            agent_id=str(raw_data.get("AgentID", "")),
            corp_id=raw_data.get("ToUserName", ""),
        )

    def _parse_xml(self, xml_str: str) -> dict[str, Any]:
        """Parse XML string to dictionary."""
        import xml.etree.ElementTree as ET

        result = {}
        try:
            root = ET.fromstring(xml_str)
            for child in root:
                result[child.tag] = child.text or ""
        except ET.ParseError as e:
            logger.error("wecom_xml_parse_error", error=str(e))

        return result

    async def send(self, message: OutboundMessage) -> bool:
        """Send a message to WeCom.

        Args:
            message: OutboundMessage to send

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Get access token
            token = await self._get_access_token()

            # Build request
            url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
            params = {"access_token": token}
            headers = {"Content-Type": "application/json"}

            # Build message content based on type
            if message.message_type == MessageType.TEXT:
                msg_content = {"touser": message.recipient_id, "msgtype": "text", "text": {"content": message.content}}
            elif message.message_type == MessageType.TEXT and "\n" in message.content:
                # Use markdown if content has newlines
                msg_content = {
                    "touser": message.recipient_id,
                    "msgtype": "markdown",
                    "markdown": {"content": message.content},
                }
            elif message.message_type == MessageType.IMAGE:
                # Upload image first
                media_id = await self._upload_media(message.content, "image")
                msg_content = {
                    "touser": message.recipient_id,
                    "msgtype": "image",
                    "image": {"media_id": media_id},
                }
            else:
                # Default to text
                msg_content = {"touser": message.recipient_id, "msgtype": "text", "text": {"content": message.content}}

            # Add agent_id
            if self._config.agent_id:
                msg_content["agentid"] = int(self._config.agent_id)

            # Enable safe flag
            msg_content["safe"] = 0

            async with self._client as client:
                response = await client.post(url, params=params, headers=headers, json=msg_content)
                response.raise_for_status()
                result = response.json()

            success = result.get("errcode") == 0
            if success:
                logger.info(
                    "wecom_message_sent",
                    recipient=message.recipient_id,
                    type=msg_content.get("msgtype"),
                )
            else:
                logger.error(
                    "wecom_message_send_failed",
                    errcode=result.get("errcode"),
                    errmsg=result.get("errmsg"),
                )

            return success

        except Exception as e:
            logger.error("wecom_message_send_error", error=str(e))
            return False

    async def _upload_media(self, media_data: str, media_type: str) -> str:
        """Upload media to WeCom and return media_id.

        Args:
            media_data: Media URL or file path
            media_type: Type of media ('image', 'voice', 'video', 'file')

        Returns:
            WeCom media_id
        """
        token = await self._get_access_token()
        url = "https://qyapi.weixin.qq.com/cgi-bin/media/upload"
        params = {"access_token": token, "type": media_type}

        # Determine media source
        if media_data.startswith("http"):
            # Download from URL
            async with self._client as client:
                image_response = await client.get(media_data)
                media_bytes = image_response.content
            files = {"media": ("file", media_bytes)}
        else:
            # Local file path
            with open(media_data, "rb") as f:
                files = {"media": f}

        async with self._client as client:
            response = await client.post(url, params=params, files=files)
            response.raise_for_status()
            result = response.json()

        if result.get("errcode", 0) != 0:
            raise ValueError(f"Failed to upload media: {result}")

        return result["media_id"]

    async def health_check(self) -> bool:
        """Check WeCom connection health.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try to get access token
            await self._get_access_token()

            # Try to get agent status
            token = await self._get_access_token()
            url = "https://qyapi.weixin.qq.com/cgi-bin/agent/get"
            params = {"access_token": token, "agentid": self._config.agent_id}

            async with self._client as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()

            healthy = result.get("errcode") == 0
            if healthy:
                logger.info("wecom_health_check_passed")
            else:
                logger.warning("wecom_health_check_failed", errcode=result.get("errcode"))

            return healthy

        except Exception as e:
            logger.error("wecom_health_check_error", error=str(e))
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
        logger.info("wecom_adapter_closed")

    # Card message helper
    async def send_text_card(
        self,
        recipient_id: str,
        title: str,
        description: str,
        url: str,
        btn_txt: str = "详情",
    ) -> bool:
        """Send a text card (rich card) message.

        Args:
            recipient_id: Recipient's user ID
            title: Card title
            description: Card description
            url: Click URL
            btn_txt: Button text

        Returns:
            True if sent successfully
        """
        token = await self._get_access_token()
        url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
        params = {"access_token": token}

        msg_content = {
            "touser": recipient_id,
            "msgtype": "textcard",
            "agentid": int(self._config.agent_id) if self._config.agent_id else None,
            "textcard": {
                "title": title,
                "description": description,
                "url": url,
                "btntxt": btn_txt,
            },
        }

        # Remove None values
        msg_content = {k: v for k, v in msg_content.items() if v is not None}

        async with self._client as client:
            response = await client.post(url, params=params, json=msg_content)
            response.raise_for_status()
            result = response.json()

        success = result.get("errcode") == 0
        if success:
            logger.info("wecom_text_card_sent", recipient=recipient_id)

        return success
