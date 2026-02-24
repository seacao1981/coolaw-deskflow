"""Multimedia message processing module.

Provides:
- Voice-to-text transcription using Whisper API
- Image OCR processing
- Video file download and transcription
- Media file download and management
"""

from __future__ import annotations

import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

import httpx

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class MediaProcessingStatus(Enum):
    """Media processing status."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MediaType(Enum):
    """Media file type."""

    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


@dataclass
class MediaFile:
    """Media file information."""

    file_id: str
    file_type: MediaType
    file_name: str = ""
    file_size: int = 0
    file_url: str = ""
    file_path: str = ""
    mime_type: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_id": self.file_id,
            "file_type": self.file_type.value,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_url": self.file_url,
            "file_path": self.file_path,
            "mime_type": self.mime_type,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class TranscriptionResult:
    """Transcription result."""

    text: str
    language: str = ""
    duration: float = 0.0
    segments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OcrResult:
    """OCR result."""

    text: str
    blocks: list[dict[str, Any]] = field(default_factory=list)
    language: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class MediaDownloader(Protocol):
    """Protocol for media downloaders."""

    async def download(self, file_id: str, file_path: str) -> str:
        """Download media file.

        Args:
            file_id: File ID from the platform
            file_path: Local file path to save

        Returns:
            Path to downloaded file
        """
        ...


class TextExtractor(Protocol):
    """Protocol for text extractors."""

    async def extract(self, media_file: MediaFile) -> str:
        """Extract text from media file.

        Args:
            media_file: Media file to process

        Returns:
            Extracted text content
        """
        ...


class WhisperExtractor:
    """Extract text from audio/video using Whisper API."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "whisper-1",
        language: str = "zh",
    ):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model
        self._language = language
        self._client = httpx.AsyncClient(timeout=60.0)

    async def transcribe(
        self,
        file_path: str,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio/video file using Whisper API.

        Args:
            file_path: Path to audio/video file
            language: Language code (e.g., 'zh', 'en')

        Returns:
            TranscriptionResult with transcribed text
        """
        if not self._api_key:
            raise ValueError("OpenAI API key not configured")

        try:
            with open(file_path, "rb") as f:
                files = {"file": (Path(file_path).name, f)}
                data = {
                    "model": self._model,
                    "language": language or self._language,
                    "response_format": "verbose_json",
                }

                async with self._client as client:
                    response = await client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        files=files,
                        data=data,
                    )
                    response.raise_for_status()
                    result = response.json()

            return TranscriptionResult(
                text=result.get("text", ""),
                language=result.get("language", self._language),
                duration=result.get("duration", 0.0),
                segments=result.get("segments", []),
                metadata={"model": self._model},
            )

        except Exception as e:
            logger.error("whisper_transcription_error", error=str(e))
            raise

    async def extract(self, media_file: MediaFile) -> str:
        """Extract text from audio/video file.

        Args:
            media_file: Media file to process

        Returns:
            Transcribed text
        """
        if not media_file.file_path:
            raise ValueError("Media file path required")

        result = await self.transcribe(media_file.file_path)
        return result.text


class BaiduOcrExtractor:
    """Extract text from images using Baidu OCR API."""

    def __init__(
        self,
        api_key: str = "",
        secret_key: str = "",
    ):
        self._api_key = api_key or os.environ.get("BAIDU_OCR_API_KEY", "")
        self._secret_key = secret_key or os.environ.get("BAIDU_OCR_SECRET_KEY", "")
        self._access_token: str | None = None
        self._token_expires_at: float = 0
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _get_access_token(self) -> str:
        """Get Baidu OCR access token."""
        if self._access_token and datetime.now().timestamp() < self._token_expires_at:
            return self._access_token

        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self._api_key,
            "client_secret": self._secret_key,
        }

        async with self._client as client:
            response = await client.post(url, params=params)
            response.raise_for_status()
            result = response.json()

        self._access_token = result.get("access_token", "")
        self._token_expires_at = datetime.now().timestamp() + result.get("expires_in", 2592000) - 3600

        return self._access_token

    async def ocr(
        self,
        image_path: str,
        language_type: str = "CHN_ENG",
    ) -> OcrResult:
        """Perform OCR on image.

        Args:
            image_path: Path to image file
            language_type: Language type (CHN_ENG, ENG, JAP, etc.)

        Returns:
            OcrResult with recognized text
        """
        if not self._api_key or not self._secret_key:
            raise ValueError("Baidu OCR credentials not configured")

        try:
            access_token = await self._get_access_token()
            url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={access_token}"

            with open(image_path, "rb") as f:
                image_data = f.read()

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
            }

            # Use image binary data
            import base64

            image_base64 = base64.b64encode(image_data).decode("utf-8")

            async with self._client as client:
                response = await client.post(
                    url,
                    headers=headers,
                    data={"image": image_base64, "language_type": language_type},
                )
                response.raise_for_status()
                result = response.json()

            if "error_code" in result:
                raise ValueError(f"Baidu OCR error: {result.get('error_msg', 'Unknown error')}")

            words_result = result.get("words_result", [])
            text = "\n".join([item.get("words", "") for item in words_result])

            return OcrResult(
                text=text,
                blocks=words_result,
                language=language_type,
                confidence=result.get("probability", 1.0),
                metadata={"words_count": result.get("words_result_num", 0)},
            )

        except Exception as e:
            logger.error("baidu_ocr_error", error=str(e))
            raise

    async def extract(self, media_file: MediaFile) -> str:
        """Extract text from image file.

        Args:
            media_file: Media file to process

        Returns:
            OCR recognized text
        """
        if not media_file.file_path:
            raise ValueError("Media file path required")

        result = await self.ocr(media_file.file_path)
        return result.text


class MediaProcessor:
    """Main media processor coordinating download and extraction."""

    def __init__(
        self,
        storage_dir: str = "data/media",
        whisper_extractor: WhisperExtractor | None = None,
        ocr_extractor: BaiduOcrExtractor | None = None,
    ):
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        self._whisper = whisper_extractor or WhisperExtractor()
        self._ocr = ocr_extractor or BaiduOcrExtractor()

        self._http_client = httpx.AsyncClient(timeout=30.0)

    async def download_file(
        self,
        file_url: str,
        file_id: str | None = None,
        file_name: str | None = None,
    ) -> str:
        """Download file from URL.

        Args:
            file_url: File URL to download
            file_id: Optional file ID (generated if not provided)
            file_name: Optional file name

        Returns:
            Path to downloaded file
        """
        file_id = file_id or uuid.uuid4().hex[:16]

        # Determine file extension from URL or use default
        if file_name:
            ext = Path(file_name).suffix or ".bin"
        else:
            ext = Path(file_url).suffix or ".bin"

        file_name = f"{file_id}{ext}"
        file_path = self._storage_dir / file_name

        logger.info("media_downloading", url=file_url, path=str(file_path))

        try:
            async with self._http_client as client:
                async with client.stream("GET", file_url) as response:
                    response.raise_for_status()
                    with open(file_path, "wb") as f:
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)

            logger.info("media_downloaded", path=str(file_path))
            return str(file_path)

        except Exception as e:
            logger.error("media_download_error", error=str(e))
            # Clean up partial file
            if file_path.exists():
                file_path.unlink()
            raise

    async def process_media(
        self,
        media_file: MediaFile,
    ) -> str:
        """Process media file and extract text.

        Args:
            media_file: Media file to process

        Returns:
            Extracted text content
        """
        logger.info(
            "media_processing_started",
            file_id=media_file.file_id,
            file_type=media_file.file_type.value,
        )

        try:
            # Download file if URL provided
            if media_file.file_url and not media_file.file_path:
                media_file.file_path = await self.download_file(
                    media_file.file_url,
                    media_file.file_id,
                    media_file.file_name,
                )

            # Process based on media type
            if media_file.file_type == MediaType.IMAGE:
                text = await self._ocr.extract(media_file)
                logger.info("ocr_completed", file_id=media_file.file_id, text_length=len(text))
                return text

            elif media_file.file_type in (MediaType.AUDIO, MediaType.VIDEO):
                text = await self._whisper.extract(media_file)
                logger.info("transcription_completed", file_id=media_file.file_id, text_length=len(text))
                return text

            elif media_file.file_type == MediaType.DOCUMENT:
                # For documents, just return file info
                return f"[Document: {media_file.file_name}]"

            else:
                logger.warning("media_unsupported_type", file_type=media_file.file_type.value)
                return ""

        except Exception as e:
            logger.error("media_processing_error", file_id=media_file.file_id, error=str(e))
            raise

    async def process_voice_message(
        self,
        file_url: str,
        file_id: str | None = None,
    ) -> TranscriptionResult:
        """Process voice message and return transcription.

        Args:
            file_url: Voice message file URL
            file_id: Optional file ID

        Returns:
            TranscriptionResult with transcribed text
        """
        media_file = MediaFile(
            file_id=file_id or uuid.uuid4().hex[:16],
            file_type=MediaType.AUDIO,
            file_name="voice_message.ogg",
            file_url=file_url,
        )

        file_path = await self.download_file(file_url, media_file.file_id, media_file.file_name)
        media_file.file_path = file_path

        return await self._whisper.transcribe(file_path)

    async def process_image_message(
        self,
        file_url: str,
        file_id: str | None = None,
        language: str = "CHN_ENG",
    ) -> OcrResult:
        """Process image message and return OCR result.

        Args:
            file_url: Image file URL
            file_id: Optional file ID
            language: OCR language type

        Returns:
            OcrResult with recognized text
        """
        media_file = MediaFile(
            file_id=file_id or uuid.uuid4().hex[:16],
            file_type=MediaType.IMAGE,
            file_name="image.jpg",
            file_url=file_url,
        )

        file_path = await self.download_file(file_url, media_file.file_id, media_file.file_name)
        media_file.file_path = file_path

        return await self._ocr.ocr(file_path, language)

    async def process_video_message(
        self,
        file_url: str,
        file_id: str | None = None,
        language: str = "zh",
    ) -> TranscriptionResult:
        """Process video message and return transcription.

        Args:
            file_url: Video file URL
            file_id: Optional file ID
            language: Transcription language

        Returns:
            TranscriptionResult with transcribed text
        """
        media_file = MediaFile(
            file_id=file_id or uuid.uuid4().hex[:16],
            file_type=MediaType.VIDEO,
            file_name="video.mp4",
            file_url=file_url,
        )

        file_path = await self.download_file(file_url, media_file.file_id, media_file.file_name)
        media_file.file_path = file_path

        return await self._whisper.transcribe(file_path, language)

    async def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """Clean up old media files.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of files deleted
        """
        deleted_count = 0
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

        for file_path in self._storage_dir.glob("*"):
            try:
                file_mtime = file_path.stat().st_mtime
                if file_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
                    logger.debug("media_file_cleaned", path=str(file_path))
            except Exception as e:
                logger.warning("media_file_cleanup_error", path=str(file_path), error=str(e))

        logger.info("media_cleanup_completed", deleted_count=deleted_count)
        return deleted_count

    async def close(self) -> None:
        """Close HTTP client."""
        await self._http_client.aclose()
        logger.info("media_processor_closed")


# Convenience functions for quick access

_default_processor: MediaProcessor | None = None


def get_processor(storage_dir: str = "data/media") -> MediaProcessor:
    """Get or create global media processor."""
    global _default_processor
    if _default_processor is None:
        _default_processor = MediaProcessor(storage_dir=storage_dir)
    return _default_processor


async def process_voice(file_url: str, file_id: str | None = None) -> str:
    """Process voice message and return transcribed text.

    Args:
        file_url: Voice file URL
        file_id: Optional file ID

    Returns:
        Transcribed text
    """
    processor = get_processor()
    result = await processor.process_voice_message(file_url, file_id)
    return result.text


async def process_image(file_url: str, file_id: str | None = None, language: str = "CHN_ENG") -> str:
    """Process image and return OCR text.

    Args:
        file_url: Image file URL
        file_id: Optional file ID
        language: OCR language type

    Returns:
        OCR recognized text
    """
    processor = get_processor()
    result = await processor.process_image_message(file_url, file_id, language)
    return result.text


async def process_video(file_url: str, file_id: str | None = None, language: str = "zh") -> str:
    """Process video and return transcribed text.

    Args:
        file_url: Video file URL
        file_id: Optional file ID
        language: Transcription language

    Returns:
        Transcribed text
    """
    processor = get_processor()
    result = await processor.process_video_message(file_url, file_id, language)
    return result.text
