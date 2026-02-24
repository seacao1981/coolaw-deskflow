"""Multimedia message processing API routes."""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Any

from deskflow.channels.media import (
    MediaProcessor,
    MediaFile,
    MediaType,
    TranscriptionResult,
    OcrResult,
    WhisperExtractor,
    BaiduOcrExtractor,
    get_processor,
)
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/media", tags=["media"])


class MediaProcessRequest(BaseModel):
    """Media processing request."""

    file_url: str = Field(..., description="File URL to process")
    file_type: str = Field(..., description="File type: image, audio, video, document")
    file_id: str | None = Field(None, description="Optional file ID")
    file_name: str | None = Field(None, description="Optional file name")
    language: str | None = Field(None, description="Language for OCR/transcription")


class MediaProcessResponse(BaseModel):
    """Media processing response."""

    success: bool
    file_id: str = ""
    file_type: str = ""
    extracted_text: str = ""
    language: str = ""
    duration: float = 0.0
    confidence: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class VoiceProcessResponse(BaseModel):
    """Voice processing response."""

    success: bool
    text: str = ""
    language: str = ""
    duration: float = 0.0
    segments: list[dict[str, Any]] = Field(default_factory=list)


class ImageOcrResponse(BaseModel):
    """Image OCR response."""

    success: bool
    text: str = ""
    language: str = ""
    confidence: float = 0.0
    blocks: list[dict[str, Any]] = Field(default_factory=list)


class MediaConfig(BaseModel):
    """Media processor configuration."""

    storage_dir: str = Field("data/media", description="Media storage directory")
    whisper_model: str = Field("whisper-1", description="Whisper model name")
    whisper_language: str = Field("zh", description="Default transcription language")
    ocr_language: str = Field("CHN_ENG", description="Default OCR language")
    max_file_size: int = Field(20971520, description="Maximum file size in bytes (20MB)")
    cleanup_interval_hours: int = Field(24, description="Cleanup interval in hours")


@router.post("/process", response_model=MediaProcessResponse)
async def process_media(request: MediaProcessRequest) -> MediaProcessResponse:
    """Process media file and extract text.

    This endpoint handles image OCR, voice transcription, and video transcription.
    """
    try:
        processor = get_processor()

        # Map file type
        type_mapping = {
            "image": MediaType.IMAGE,
            "audio": MediaType.AUDIO,
            "video": MediaType.VIDEO,
            "document": MediaType.DOCUMENT,
        }
        media_type = type_mapping.get(request.file_type.lower(), MediaType.DOCUMENT)

        # Create media file
        media_file = MediaFile(
            file_id=request.file_id or "",
            file_type=media_type,
            file_name=request.file_name or "",
            file_url=request.file_url,
        )

        # Process media
        extracted_text = await processor.process_media(media_file)

        # Determine language based on type
        language = request.language or ("zh" if media_type in (MediaType.AUDIO, MediaType.VIDEO) else "CHN_ENG")

        return MediaProcessResponse(
            success=True,
            file_id=media_file.file_id,
            file_type=media_type.value,
            extracted_text=extracted_text,
            language=language,
        )

    except ValueError as e:
        logger.error("media_process_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("media_process_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice", response_model=VoiceProcessResponse)
async def process_voice(
    file_url: str = Form(..., description="Voice file URL"),
    file_id: str | None = Form(None, description="Optional file ID"),
    language: str = Form("zh", description="Transcription language"),
) -> VoiceProcessResponse:
    """Process voice message and return transcription."""
    try:
        processor = get_processor()
        result = await processor.process_voice_message(file_url, file_id)

        return VoiceProcessResponse(
            success=True,
            text=result.text,
            language=result.language or language,
            duration=result.duration,
            segments=result.segments,
        )

    except ValueError as e:
        logger.error("voice_process_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("voice_process_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/image", response_model=ImageOcrResponse)
async def process_image(
    file_url: str = Form(..., description="Image file URL"),
    file_id: str | None = Form(None, description="Optional file ID"),
    language: str = Form("CHN_ENG", description="OCR language type"),
) -> ImageOcrResponse:
    """Process image and return OCR result."""
    try:
        processor = get_processor()
        result = await processor.process_image_message(file_url, file_id, language)

        return ImageOcrResponse(
            success=True,
            text=result.text,
            language=result.language or language,
            confidence=result.confidence,
            blocks=result.blocks,
        )

    except ValueError as e:
        logger.error("image_process_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("image_process_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/video", response_model=VoiceProcessResponse)
async def process_video(
    file_url: str = Form(..., description="Video file URL"),
    file_id: str | None = Form(None, description="Optional file ID"),
    language: str = Form("zh", description="Transcription language"),
) -> VoiceProcessResponse:
    """Process video and return transcription."""
    try:
        processor = get_processor()
        result = await processor.process_video_message(file_url, file_id, language)

        return VoiceProcessResponse(
            success=True,
            text=result.text,
            language=result.language or language,
            duration=result.duration,
            segments=result.segments,
        )

    except ValueError as e:
        logger.error("video_process_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("video_process_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/voice", response_model=VoiceProcessResponse)
async def upload_and_process_voice(
    file: UploadFile = File(..., description="Voice file to upload"),
    language: str = Form("zh", description="Transcription language"),
) -> VoiceProcessResponse:
    """Upload voice file and return transcription."""
    try:
        import uuid
        import tempfile

        processor = get_processor()

        # Generate file ID and path
        file_id = uuid.uuid4().hex[:16]
        ext = file.filename.split(".")[-1] if file.filename else "ogg"
        file_name = f"voice_{file_id}.{ext}"

        # Save uploaded file
        temp_path = processor._storage_dir / file_name
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Transcribe
        result = await processor._whisper.transcribe(str(temp_path), language)

        return VoiceProcessResponse(
            success=True,
            text=result.text,
            language=result.language or language,
            duration=result.duration,
            segments=result.segments,
        )

    except ValueError as e:
        logger.error("voice_upload_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("voice_upload_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/image", response_model=ImageOcrResponse)
async def upload_and_process_image(
    file: UploadFile = File(..., description="Image file to upload"),
    language: str = Form("CHN_ENG", description="OCR language type"),
) -> ImageOcrResponse:
    """Upload image and return OCR result."""
    try:
        import uuid

        processor = get_processor()

        # Generate file ID and path
        file_id = uuid.uuid4().hex[:16]
        ext = file.filename.split(".")[-1] if file.filename else "jpg"
        file_name = f"image_{file_id}.{ext}"

        # Save uploaded file
        temp_path = processor._storage_dir / file_name
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # OCR
        result = await processor._ocr.ocr(str(temp_path), language)

        return ImageOcrResponse(
            success=True,
            text=result.text,
            language=result.language or language,
            confidence=result.confidence,
            blocks=result.blocks,
        )

    except ValueError as e:
        logger.error("image_upload_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("image_upload_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/video", response_model=VoiceProcessResponse)
async def upload_and_process_video(
    file: UploadFile = File(..., description="Video file to upload"),
    language: str = Form("zh", description="Transcription language"),
) -> VoiceProcessResponse:
    """Upload video and return transcription."""
    try:
        import uuid

        processor = get_processor()

        # Generate file ID and path
        file_id = uuid.uuid4().hex[:16]
        ext = file.filename.split(".")[-1] if file.filename else "mp4"
        file_name = f"video_{file_id}.{ext}"

        # Save uploaded file
        temp_path = processor._storage_dir / file_name
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Transcribe
        result = await processor._whisper.transcribe(str(temp_path), language)

        return VoiceProcessResponse(
            success=True,
            text=result.text,
            language=result.language or language,
            duration=result.duration,
            segments=result.segments,
        )

    except ValueError as e:
        logger.error("video_upload_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("video_upload_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config", response_model=MediaConfig)
async def get_config() -> MediaConfig:
    """Get media processor configuration."""
    return MediaConfig()


@router.post("/cleanup")
async def cleanup_old_files(max_age_hours: int = 24) -> dict[str, Any]:
    """Clean up old media files.

    Args:
        max_age_hours: Maximum age in hours
    """
    try:
        processor = get_processor()
        deleted_count = await processor.cleanup_old_files(max_age_hours)

        return {
            "success": True,
            "deleted_count": deleted_count,
            "max_age_hours": max_age_hours,
        }

    except Exception as e:
        logger.error("media_cleanup_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """Get media storage statistics."""
    try:
        processor = get_processor()
        storage_dir = processor._storage_dir

        total_size = 0
        file_count = 0
        file_types = {}

        for file_path in storage_dir.glob("*"):
            try:
                total_size += file_path.stat().st_size
                file_count += 1
                ext = file_path.suffix.lower()
                file_types[ext] = file_types.get(ext, 0) + 1
            except Exception:
                pass

        return {
            "storage_dir": str(storage_dir),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "file_count": file_count,
            "file_types": file_types,
        }

    except Exception as e:
        logger.error("media_stats_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
