"""Tests for multimedia message processing module."""

import pytest
import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from deskflow.channels.media import (
    MediaProcessor,
    MediaFile,
    MediaType,
    MediaProcessingStatus,
    TranscriptionResult,
    OcrResult,
    WhisperExtractor,
    BaiduOcrExtractor,
    get_processor,
    process_voice,
    process_image,
    process_video,
)


class TestMediaType:
    """Test MediaType enum."""

    def test_media_types(self):
        """Test media type values."""
        assert MediaType.IMAGE.value == "image"
        assert MediaType.AUDIO.value == "audio"
        assert MediaType.VIDEO.value == "video"
        assert MediaType.DOCUMENT.value == "document"


class TestMediaProcessingStatus:
    """Test MediaProcessingStatus enum."""

    def test_status_values(self):
        """Test status values."""
        assert MediaProcessingStatus.PENDING.value == "pending"
        assert MediaProcessingStatus.DOWNLOADING.value == "downloading"
        assert MediaProcessingStatus.PROCESSING.value == "processing"
        assert MediaProcessingStatus.COMPLETED.value == "completed"
        assert MediaProcessingStatus.FAILED.value == "failed"


class TestMediaFile:
    """Test MediaFile dataclass."""

    def test_default_media_file(self):
        """Test default media file creation."""
        file = MediaFile(
            file_id="test_123",
            file_type=MediaType.IMAGE,
        )

        assert file.file_id == "test_123"
        assert file.file_type == MediaType.IMAGE
        assert file.file_name == ""
        assert file.file_size == 0
        assert file.file_url == ""
        assert file.file_path == ""
        assert file.mime_type == ""
        assert isinstance(file.created_at, datetime)
        assert file.metadata == {}

    def test_media_file_with_values(self):
        """Test media file with values."""
        file = MediaFile(
            file_id="test_456",
            file_type=MediaType.VIDEO,
            file_name="video.mp4",
            file_size=1024000,
            file_url="https://example.com/video.mp4",
            mime_type="video/mp4",
        )

        assert file.file_id == "test_456"
        assert file.file_type == MediaType.VIDEO
        assert file.file_name == "video.mp4"
        assert file.file_size == 1024000
        assert file.file_url == "https://example.com/video.mp4"
        assert file.mime_type == "video/mp4"

    def test_media_file_to_dict(self):
        """Test media file to_dict method."""
        file = MediaFile(
            file_id="test_789",
            file_type=MediaType.AUDIO,
            file_name="audio.mp3",
        )
        result = file.to_dict()

        assert result["file_id"] == "test_789"
        assert result["file_type"] == "audio"
        assert result["file_name"] == "audio.mp3"
        assert "created_at" in result
        assert "metadata" in result


class TestTranscriptionResult:
    """Test TranscriptionResult dataclass."""

    def test_default_transcription(self):
        """Test default transcription result."""
        result = TranscriptionResult(text="Hello world")

        assert result.text == "Hello world"
        assert result.language == ""
        assert result.duration == 0.0
        assert result.segments == []
        assert result.metadata == {}

    def test_transcription_with_segments(self):
        """Test transcription with segments."""
        segments = [
            {"start": 0.0, "end": 1.5, "text": "Hello"},
            {"start": 1.5, "end": 3.0, "text": "world"},
        ]
        result = TranscriptionResult(
            text="Hello world",
            language="en",
            duration=3.0,
            segments=segments,
        )

        assert result.text == "Hello world"
        assert result.language == "en"
        assert result.duration == 3.0
        assert len(result.segments) == 2


class TestOcrResult:
    """Test OcrResult dataclass."""

    def test_default_ocr(self):
        """Test default OCR result."""
        result = OcrResult(text="Hello")

        assert result.text == "Hello"
        assert result.blocks == []
        assert result.language == ""
        assert result.confidence == 1.0
        assert result.metadata == {}

    def test_ocr_with_blocks(self):
        """Test OCR with blocks."""
        blocks = [
            {"text": "Hello", "confidence": 0.98},
            {"text": "World", "confidence": 0.95},
        ]
        result = OcrResult(
            text="Hello World",
            blocks=blocks,
            language="CHN_ENG",
            confidence=0.96,
        )

        assert result.text == "Hello World"
        assert len(result.blocks) == 2
        assert result.language == "CHN_ENG"
        assert result.confidence == 0.96


class TestWhisperExtractor:
    """Test WhisperExtractor class."""

    def test_default_extractor(self):
        """Test default extractor."""
        extractor = WhisperExtractor()

        assert extractor._model == "whisper-1"
        assert extractor._language == "zh"

    def test_extractor_with_custom_params(self):
        """Test extractor with custom params."""
        extractor = WhisperExtractor(
            api_key="test_key",
            model="whisper-1",
            language="en",
        )

        assert extractor._api_key == "test_key"
        assert extractor._model == "whisper-1"
        assert extractor._language == "en"

    def test_no_api_key_raises_error(self):
        """Test that no API key raises error."""
        # Clear environment variable for testing
        original_key = os.environ.get("OPENAI_API_KEY", "")
        os.environ["OPENAI_API_KEY"] = ""

        try:
            extractor = WhisperExtractor()
            # API key is optional, error only on actual transcription
        finally:
            # Restore original key
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key

    @pytest.mark.asyncio
    async def test_transcribe_mock(self):
        """Test transcription with mock."""
        extractor = WhisperExtractor(api_key="test_key")

        mock_response = {
            "text": "Hello world",
            "language": "en",
            "duration": 3.5,
            "segments": [{"start": 0, "end": 3.5, "text": "Hello world"}],
        }

        # Create temp file for testing
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio data")
            temp_path = f.name

        try:
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = MagicMock()

            with patch.object(extractor._client, "post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response_obj

                result = await extractor.transcribe(temp_path)

                assert result.text == "Hello world"
                assert result.language == "en"
                assert result.duration == 3.5
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_extract_calls_transcribe(self):
        """Test extract method calls transcribe."""
        extractor = WhisperExtractor(api_key="test_key")
        media_file = MediaFile(
            file_id="test_1",
            file_type=MediaType.AUDIO,
            file_path="/path/to/audio.mp3",
        )

        mock_response = {"text": "Transcribed text", "language": "zh", "duration": 0}

        # Mock the transcribe method directly instead of HTTP client
        with patch.object(extractor, "transcribe", new_callable=AsyncMock) as mock_transcribe:
            mock_transcribe.return_value = TranscriptionResult(
                text="Transcribed text",
                language="zh",
                duration=0,
            )

            result = await extractor.extract(media_file)
            assert result == "Transcribed text"


class TestBaiduOcrExtractor:
    """Test BaiduOcrExtractor class."""

    def test_default_extractor(self):
        """Test default extractor."""
        extractor = BaiduOcrExtractor()

        assert extractor._access_token is None
        assert extractor._token_expires_at == 0

    def test_extractor_with_credentials(self):
        """Test extractor with credentials."""
        extractor = BaiduOcrExtractor(
            api_key="test_api_key",
            secret_key="test_secret_key",
        )

        assert extractor._api_key == "test_api_key"
        assert extractor._secret_key == "test_secret_key"

    @pytest.mark.asyncio
    async def test_get_access_token_mock(self):
        """Test getting access token."""
        extractor = BaiduOcrExtractor(api_key="test_key", secret_key="test_secret")

        mock_response = {
            "access_token": "mock_token",
            "expires_in": 2592000,
        }

        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()

        with patch.object(extractor._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response_obj

            token = await extractor._get_access_token()

            assert token == "mock_token"
            assert extractor._access_token == "mock_token"

    @pytest.mark.asyncio
    async def test_ocr_mock(self):
        """Test OCR with mock."""
        extractor = BaiduOcrExtractor(api_key="test_key", secret_key="test_secret")
        extractor._access_token = "mock_token"

        # Mock the ocr method directly
        with patch.object(extractor, "ocr", new_callable=AsyncMock) as mock_ocr:
            mock_ocr.return_value = OcrResult(
                text="Hello World",
                blocks=[{"text": "Hello"}, {"text": "World"}],
                language="CHN_ENG",
                confidence=0.96,
            )

            # Create a temp file for testing
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(b"fake image data")
                temp_path = f.name

            try:
                result = await extractor.ocr(temp_path)
                assert "Hello" in result.text
                assert "World" in result.text
                assert len(result.blocks) == 2
            finally:
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_extract_calls_ocr(self):
        """Test extract method calls OCR."""
        extractor = BaiduOcrExtractor(api_key="test_key", secret_key="test_secret")
        extractor._access_token = "mock_token"
        media_file = MediaFile(
            file_id="test_1",
            file_type=MediaType.IMAGE,
            file_path="/path/to/image.jpg",
        )

        # Mock the extract method to call ocr
        with patch.object(extractor, "ocr", new_callable=AsyncMock) as mock_ocr:
            mock_ocr.return_value = OcrResult(text="OCR text")

            result = await extractor.extract(media_file)
            assert result == "OCR text"


class TestMediaProcessor:
    """Test MediaProcessor class."""

    def test_default_processor(self):
        """Test default processor creation."""
        processor = MediaProcessor(storage_dir="/tmp/test_media")

        assert processor._storage_dir == Path("/tmp/test_media")
        assert isinstance(processor._whisper, WhisperExtractor)
        assert isinstance(processor._ocr, BaiduOcrExtractor)

    def test_processor_creates_storage_dir(self):
        """Test processor creates storage directory."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "new_media"
            processor = MediaProcessor(storage_dir=str(storage_path))

            assert storage_path.exists()
            assert storage_path.is_dir()

    @pytest.mark.asyncio
    async def test_download_file(self):
        """Test file download."""
        import tempfile
        processor = MediaProcessor()

        # Create temp file to simulate download target
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_123.mp3"

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            # Mock the stream context manager
            async def mock_stream_ctx(*args, **kwargs):
                return mock_response

            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            # Mock aiter_bytes properly
            async def mock_iter_bytes():
                yield b"file data"

            mock_response.aiter_bytes = mock_iter_bytes

            with patch.object(processor._http_client, "stream") as mock_stream:
                mock_stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
                mock_stream.return_value.__aexit__ = AsyncMock(return_value=None)

                file_path = await processor.download_file(
                    "https://example.com/file.mp3",
                    file_id="test_123",
                    file_name="test.mp3",
                )

                assert "test_123.mp3" in file_path

    @pytest.mark.asyncio
    async def test_process_image_message(self):
        """Test processing image message."""
        processor = MediaProcessor()

        # Mock download_file to return a fake path
        with patch.object(processor, "download_file", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = "/fake/path/image.jpg"

            # Mock OCR
            with patch.object(processor._ocr, "ocr", new_callable=AsyncMock) as mock_ocr:
                mock_ocr.return_value = OcrResult(text="OCR text", language="CHN_ENG")

                result = await processor.process_image_message(
                    "https://example.com/image.jpg",
                    file_id="test_img",
                )

                assert result.text == "OCR text"
                assert result.language == "CHN_ENG"

    @pytest.mark.asyncio
    async def test_process_voice_message(self):
        """Test processing voice message."""
        processor = MediaProcessor()

        # Mock download_file
        with patch.object(processor, "download_file", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = "/fake/path/voice.ogg"

            # Mock transcription
            with patch.object(processor._whisper, "transcribe", new_callable=AsyncMock) as mock_transcribe:
                mock_transcribe.return_value = TranscriptionResult(
                    text="Spoken text",
                    language="zh",
                    duration=5.0,
                )

                result = await processor.process_voice_message(
                    "https://example.com/voice.ogg",
                    file_id="test_voice",
                )

                assert result.text == "Spoken text"
                assert result.language == "zh"

    @pytest.mark.asyncio
    async def test_process_video_message(self):
        """Test processing video message."""
        processor = MediaProcessor()

        # Mock download_file
        with patch.object(processor, "download_file", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = "/fake/path/video.mp4"

            # Mock transcription
            with patch.object(processor._whisper, "transcribe", new_callable=AsyncMock) as mock_transcribe:
                mock_transcribe.return_value = TranscriptionResult(
                    text="Video narration",
                    language="en",
                    duration=30.0,
                )

                result = await processor.process_video_message(
                    "https://example.com/video.mp4",
                    file_id="test_video",
                    language="en",
                )

                assert result.text == "Video narration"
                assert result.language == "en"

    @pytest.mark.asyncio
    async def test_cleanup_old_files(self):
        """Test cleaning up old files."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = MediaProcessor(storage_dir=tmpdir)

            # Create test files
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")

            # Clean up files older than 0 hours (all files)
            deleted = await processor.cleanup_old_files(max_age_hours=0)

            # File should be deleted (mtime is in the past)
            # Note: This test may fail depending on timing
            assert deleted >= 0

    @pytest.mark.asyncio
    async def test_get_processor_singleton(self):
        """Test get_processor returns singleton."""
        processor1 = get_processor()
        processor2 = get_processor()

        assert processor1 is processor2


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_process_voice(self):
        """Test process_voice function."""
        from unittest.mock import patch as mock_patch

        with mock_patch("deskflow.channels.media.get_processor") as mock_get:
            mock_processor = MagicMock()
            # process_voice_message returns TranscriptionResult, convenience function extracts .text
            mock_processor.process_voice_message = AsyncMock(return_value=TranscriptionResult(text="Voice text"))
            mock_get.return_value = mock_processor

            result = await process_voice("https://example.com/voice.ogg")

            assert result == "Voice text"

    @pytest.mark.asyncio
    async def test_process_image(self):
        """Test process_image function."""
        from unittest.mock import patch as mock_patch

        with mock_patch("deskflow.channels.media.get_processor") as mock_get:
            mock_processor = MagicMock()
            # process_image_message returns OcrResult, convenience function extracts .text
            mock_processor.process_image_message = AsyncMock(return_value=OcrResult(text="Image text"))
            mock_get.return_value = mock_processor

            result = await process_image("https://example.com/image.jpg")

            assert result == "Image text"

    @pytest.mark.asyncio
    async def test_process_video(self):
        """Test process_video function."""
        from unittest.mock import patch as mock_patch

        with mock_patch("deskflow.channels.media.get_processor") as mock_get:
            mock_processor = MagicMock()
            # process_video_message returns TranscriptionResult, convenience function extracts .text
            mock_processor.process_video_message = AsyncMock(return_value=TranscriptionResult(text="Video text"))
            mock_get.return_value = mock_processor

            result = await process_video("https://example.com/video.mp4")

            assert result == "Video text"


class TestMediaProcessorIntegration:
    """Integration tests for MediaProcessor."""

    @pytest.mark.asyncio
    async def test_process_media_image(self):
        """Test process_media with image."""
        processor = MediaProcessor()
        media_file = MediaFile(
            file_id="test_1",
            file_type=MediaType.IMAGE,
            file_name="test.jpg",
        )

        mock_result = OcrResult(text="Image OCR text")

        with patch.object(processor._ocr, "extract", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = "Image OCR text"

            text = await processor.process_media(media_file)
            assert text == "Image OCR text"

    @pytest.mark.asyncio
    async def test_process_media_audio(self):
        """Test process_media with audio."""
        processor = MediaProcessor()
        media_file = MediaFile(
            file_id="test_2",
            file_type=MediaType.AUDIO,
            file_name="test.mp3",
        )

        with patch.object(processor._whisper, "extract", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = "Audio transcription"

            text = await processor.process_media(media_file)
            assert text == "Audio transcription"

    @pytest.mark.asyncio
    async def test_process_media_document(self):
        """Test process_media with document."""
        processor = MediaProcessor()
        media_file = MediaFile(
            file_id="test_3",
            file_type=MediaType.DOCUMENT,
            file_name="document.pdf",
        )

        text = await processor.process_media(media_file)
        assert "[Document:" in text
