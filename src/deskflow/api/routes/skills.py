"""Skills management API routes."""

from __future__ import annotations

import os
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])

ICON_MAP = {
    "browser": "globe",
    "desktop": "code",
    "file": "folder",
    "memory": "shield",
    "plan": "file-text",
    "skill": "code",
    "tool": "terminal",
    "user": "file",
    "web": "globe",
    "search": "search",
    "default": "file-text",
}

COLOR_MAP = {
    "browser": "blue",
    "desktop": "purple",
    "file": "green",
    "memory": "cyan",
    "plan": "amber",
    "skill": "rose",
    "tool": "amber",
    "user": "purple",
    "web": "blue",
    "search": "cyan",
    "default": "gray",
}

SYSTEM_SKILLS = [
    {"name": "shell", "description": "Execute shell commands", "type": "system", "version": "v1.0.0", "is_active": True, "icon": "terminal", "color": "amber"},
    {"name": "file", "description": "Read and write files", "type": "system", "version": "v1.0.0", "is_active": True, "icon": "folder", "color": "green"},
    {"name": "web", "description": "Search the web", "type": "system", "version": "v1.0.0", "is_active": True, "icon": "globe", "color": "blue"},
    {"name": "sticker", "description": "Send stickers", "type": "system", "version": "v1.0.0", "is_active": True, "icon": "file", "color": "purple"},
]

SKILL_TEMPLATES = {
    "document_processor": {"name": "Document Processor", "description": "Process PDF, Word, and Excel documents", "type": "utility", "version": "v0.1.0", "icon": "file-text", "color": "cyan"},
    "code_runner": {"name": "Code Runner", "description": "Execute Python code in sandbox", "type": "utility", "version": "v0.1.0", "icon": "code", "color": "rose"},
    "image_analyzer": {"name": "Image Analyzer", "description": "Analyze images using AI vision", "type": "ai", "version": "v0.1.0", "icon": "image", "color": "purple"},
}


def _get_state() -> Any:
    from deskflow.app import get_app_state
    return get_app_state()


def _get_skills_dir() -> Path:
    state = _get_state()
    from deskflow.config import AppConfig
    config: AppConfig = state.config
    return config.get_project_root() / "skills"


def _get_icon_and_color(skill_name: str) -> tuple[str, str]:
    name_lower = skill_name.lower()
    for category, icon in ICON_MAP.items():
        if category in name_lower:
            return icon, COLOR_MAP.get(category, "gray")
    return "default", "gray"


def validate_skill_package(skill_json: dict) -> tuple[bool, str]:
    required_fields = ["name", "description", "version"]
    for field in required_fields:
        if field not in skill_json:
            return False, f"Missing required field: {field}"
    name = skill_json.get("name", "")
    if not name or len(name) > 50:
        return False, "Skill name must be 1-50 characters"
    version = skill_json.get("version", "")
    if not version.startswith("v"):
        return False, "Version must start with 'v'"
    return True, ""


@router.get("")
async def list_skills():
    """List all available skills."""
    state = _get_state()
    skills_dir = _get_skills_dir()
    registered_tools = []
    if state.tools:
        for tool_name in state.tools._tools.keys():
            registered_tools.append(tool_name.lower())

    skills = []
    for skill in SYSTEM_SKILLS:
        skill_data = skill.copy()
        skill_data["is_active"] = skill["name"].lower() in registered_tools
        skills.append(skill_data)

    try:
        from deskflow.skills.registry import default_registry
        if default_registry:
            registry_skills = default_registry.list_all()
            for skill_entry in registry_skills:
                if any(s["name"] == skill_entry.name for s in SYSTEM_SKILLS):
                    continue
                icon, color = _get_icon_and_color(skill_entry.name)
                skills.append({
                    "name": skill_entry.name,
                    "description": skill_entry.description,
                    "type": "system" if skill_entry.system else "user",
                    "version": "v1.0.0",
                    "is_active": not skill_entry.disable_model_invocation,
                    "icon": icon,
                    "color": color,
                })
    except Exception as e:
        logger.warning("skill_registry_load_failed", error=str(e))

    if skills_dir.exists():
        for item in skills_dir.iterdir():
            if item.is_dir() and not item.name.startswith("_") and item.name not in ["system"]:
                meta_file = item / "skill.json"
                if meta_file.exists():
                    try:
                        with open(meta_file) as f:
                            meta = json.load(f)
                        skill_name = meta.get("name", item.name)
                        if any(s["name"] == skill_name for s in skills):
                            continue
                        skills.append({
                            "name": skill_name,
                            "description": meta.get("description", "User skill"),
                            "type": meta.get("type", "user"),
                            "version": meta.get("version", "v0.1.0"),
                            "is_active": True,
                            "icon": meta.get("icon", "file"),
                            "color": meta.get("color", "purple"),
                            "installed_at": meta.get("installed_at"),
                        })
                    except Exception:
                        pass
                else:
                    if any(s["name"] == item.name for s in skills):
                        continue
                    skills.append({
                        "name": item.name,
                        "description": "User-defined skill",
                        "type": "user",
                        "version": "v0.1.0",
                        "is_active": True,
                        "icon": "file",
                        "color": "purple",
                    })

    return {"skills": skills, "total": len(skills)}


@router.get("/{skill_name}")
async def get_skill(skill_name: str):
    """Get details of a specific skill."""
    for skill in SYSTEM_SKILLS:
        if skill["name"] == skill_name:
            return skill

    try:
        from deskflow.skills.registry import default_registry
        if default_registry:
            skill_entry = default_registry.get(skill_name)
            if skill_entry:
                icon, color = _get_icon_and_color(skill_name)
                return {
                    "name": skill_entry.name,
                    "description": skill_entry.description,
                    "type": "system" if skill_entry.system else "user",
                    "version": "v1.0.0",
                    "is_active": not skill_entry.disable_model_invocation,
                    "icon": icon,
                    "color": color,
                    "body": skill_entry.get_body() or "",
                }
    except Exception:
        pass

    skills_dir = _get_skills_dir()
    skill_path = skills_dir / skill_name
    if skill_path.exists() and skill_path.is_dir():
        meta_file = skill_path / "skill.json"
        if meta_file.exists():
            try:
                with open(meta_file) as f:
                    return json.load(f)
            except Exception:
                return {"name": skill_name, "description": "User skill", "type": "user"}

    raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")


@router.post("/{skill_name}/toggle")
async def toggle_skill(skill_name: str, action: str = "toggle"):
    """Enable or disable a skill."""
    state = _get_state()
    skill_found = False
    for skill in SYSTEM_SKILLS:
        if skill["name"] == skill_name:
            skill_found = True
            break

    if not skill_found:
        try:
            from deskflow.skills.registry import default_registry
            if default_registry:
                skill_entry = default_registry.get(skill_name)
                if skill_entry:
                    skill_found = True
        except Exception:
            pass

    if not skill_found:
        skills_dir = _get_skills_dir()
        if not (skills_dir / skill_name).exists():
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    if skill_name in ["shell", "file", "web", "sticker"]:
        return {"success": False, "message": f"System skill '{skill_name}' cannot be disabled", "is_active": True}

    return {"success": True, "message": f"Skill '{skill_name}' toggled", "is_active": action != "disable"}


@router.post("/install")
async def install_skill(request: dict):
    """Install a new skill."""
    skills_dir = _get_skills_dir()
    skills_dir.mkdir(parents=True, exist_ok=True)

    template_name = request.get("template_name")
    if template_name:
        if template_name not in SKILL_TEMPLATES:
            raise HTTPException(status_code=400, detail=f"Unknown skill template: {template_name}")
        template = SKILL_TEMPLATES[template_name]
        source_url = template.get("source_url")
        if source_url:
            return await _install_from_github(source_url, skills_dir)
        skill_dir = skills_dir / template_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_json = {
            "name": template["name"],
            "description": template["description"],
            "type": template["type"],
            "version": template["version"],
            "icon": template["icon"],
            "color": template["color"],
            "installed_at": datetime.now().isoformat(),
        }
        with open(skill_dir / "skill.json", "w", encoding="utf-8") as f:
            json.dump(skill_json, f, indent=2)
        logger.info("skill_installed_from_template", name=template_name)
        return {"success": True, "message": f"Skill '{template_name}' installed", "skill_name": template_name}

    source_url = request.get("source_url")
    if source_url:
        return await _install_from_github(source_url, skills_dir)

    skill_data = request.get("skill_data")
    if skill_data:
        return await _install_from_upload(skill_data, skills_dir)

    raise HTTPException(status_code=400, detail="Must provide template_name, source_url, or skill_data")


async def _install_from_github(source_url: str, skills_dir: Path) -> dict:
    """Install skill from GitHub repository."""
    if "github.com" not in source_url:
        raise HTTPException(status_code=400, detail="Only GitHub URLs are supported")

    parts = source_url.rstrip("/").split("/")
    if len(parts) < 5:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")

    owner = parts[3]
    repo = parts[4]
    skill_name = repo.replace("deskflow-skill-", "").replace("deskflow-", "").replace("-", "_")
    zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip"

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(zip_url)
            if response.status_code != 200:
                zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/master.zip"
                response = await client.get(zip_url)
                if response.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Failed to download: {response.status_code}")
            zip_content = response.content
    except httpx.TimeoutException:
        raise HTTPException(status_code=400, detail="Download timeout")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Download failed: {str(e)}")

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / "skill.zip"
        with open(zip_path, "wb") as f:
            f.write(zip_content)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        skill_json_path = None
        for root, dirs, files in os.walk(tmpdir):
            if "skill.json" in files:
                skill_json_path = Path(root) / "skill.json"
                break

        if not skill_json_path:
            skill_json = {"name": skill_name, "description": f"Skill from {repo}", "type": "user", "version": "v0.1.0", "source": source_url, "installed_at": datetime.now().isoformat()}
        else:
            with open(skill_json_path, "r", encoding="utf-8") as f:
                skill_json = json.load(f)
            is_valid, error = validate_skill_package(skill_json)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Invalid skill package: {error}")

        skill_dir = skills_dir / skill_name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        skill_dir.mkdir(parents=True, exist_ok=True)

        extracted_dir = Path(tmpdir) / f"{repo}-main"
        if not extracted_dir.exists():
            extracted_dir = Path(tmpdir) / f"{repo}-master"

        if extracted_dir.exists():
            for item in extracted_dir.iterdir():
                if item.name in [".git", "__pycache__", ".pytest_cache", "node_modules"]:
                    continue
                dest = skill_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

        skill_json["installed_at"] = datetime.now().isoformat()
        skill_json["source"] = source_url
        with open(skill_dir / "skill.json", "w", encoding="utf-8") as f:
            json.dump(skill_json, f, indent=2)

    logger.info("skill_installed_from_github", name=skill_name, source=source_url)
    return {"success": True, "message": f"Skill '{skill_name}' installed", "skill_name": skill_name, "source": source_url}


async def _install_from_upload(skill_data: str, skills_dir: Path) -> dict:
    """Install skill from uploaded zip file."""
    import base64
    try:
        zip_content = base64.b64decode(skill_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 data")

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / "skill.zip"
        with open(zip_path, "wb") as f:
            f.write(zip_content)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        skill_json_path = None
        skill_name = None
        for root, dirs, files in os.walk(tmpdir):
            if "skill.json" in files:
                skill_json_path = Path(root) / "skill.json"
                with open(skill_json_path, "r", encoding="utf-8") as f:
                    skill_json = json.load(f)
                    skill_name = skill_json.get("name", Path(root).name)
                break

        if not skill_json_path:
            raise HTTPException(status_code=400, detail="skill.json not found")

        is_valid, error = validate_skill_package(skill_json)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid skill package: {error}")

        skill_dir = skills_dir / skill_name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        skill_dir.mkdir(parents=True, exist_ok=True)

        for item in Path(tmpdir).iterdir():
            if item.name in [".git", "__pycache__", ".pytest_cache", "node_modules"]:
                continue
            dest = skill_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        skill_json["installed_at"] = datetime.now().isoformat()
        with open(skill_dir / "skill.json", "w", encoding="utf-8") as f:
            json.dump(skill_json, f, indent=2)

    logger.info("skill_installed_from_upload", name=skill_name)
    return {"success": True, "message": f"Skill '{skill_name}' installed", "skill_name": skill_name}
