---
name: google-flow
description: Automates high-fidelity AI video (Veo 3.1 & Gemini Omni) and image (Imagen 4 & Nano Banana) generation via Google Flow. Handles multi-account management (1..34+ profiles), zero-bot-detection persistent Chrome profiles, pinpoint account selection, and smart auto-rotation on quota exhaustion (HTTP 429).
---

# Google Flow Automation Skill

This skill guides AI agents (Antigravity, Claude Code, Codex, Cursor) in orchestrating Google Flow for text-to-video, image-to-video, and text-to-image generation across multiple Google accounts with automatic quota rotation.

## Architecture & Workflows

Google Flow automation operates via two interfaces:
1. **MCP Tools (`google-flow` server):** Native RPC function calling inside the AI context.
2. **CLI Scripts (`d:\flow_auto\`):** Standalone batch scripts with integrated auto-rotation, limit caching, and isolated persistent Chrome profiles.

### 1. Generating Video (Veo 3.1 / Gemini Omni)

#### Via MCP:
Call `gflow_generate_video`:
```json
{
  "prompt": "Cinematic drone shot of misty mountain peaks at sunset, anamorphic lens, warm golden hour rays, 4k photorealistic",
  "model": "omni-flash",
  "aspect": "16:9",
  "duration": 6
}
```

#### Via Command Line:
```powershell
# Auto-rotation across all active profiles:
.\generate.bat "Ваш промпт" --profile auto

# Pinpoint generation on account #2:
.\generate.bat 2 "Ваш промпт"

# Custom model and duration:
.\generate.bat "Ваш промпт" --model omni-flash --duration 8 --aspect 16:9
```

Supported Video Models:
- `omni-flash`: Gemini Omni 1.1 Flash (recommended default: fast, fluid, supports 4, 6, 8, 10s).
- `veo-quality`: Veo 3.1 High Quality (maximum photorealism, supports 4, 6, 8s).
- `veo-fast`: Fast draft previews.

### 2. Generating Images (Imagen 4 / Nano Banana)

#### Via MCP:
Call `gflow_generate_image`:
```json
{
  "prompt": "Hyperrealistic cyberpunk samurai walking through a rainy neon alley in Neo Tokyo, cinematic lighting, octane render, 8k",
  "model": "nano-pro",
  "aspect": "16:9",
  "count": 1
}
```

#### Via Command Line:
```powershell
# Auto-rotation across profiles:
.\generate_image.bat "Ваш промпт" --profile auto

# Specific account:
.\generate_image.bat 2 "Ваш промпт"
```

Supported Image Models:
- `nano-pro`: High quality, crisp details (default).
- `image4`: Imagen 4 photorealistic master quality.
- `nano2`: Fast draft.

### 3. Multi-Account Management (1..34+ Profiles)

- **Listing Accounts:**
  Run `.\list_profiles.bat` or call `gflow_auth_status`.
  Displays all Google accounts on the system, their Chrome names, Google emails, and Flow readiness.

- **Authorizing an Account:**
  Run `.\login.bat <id>` (e.g. `.\login.bat 2` or `.\login.bat 10`).
  Opens an isolated Chrome profile without automation flags. The user completes the one-time sign-in into Google Flow and closes the browser. The session is stored permanently in SQLite.

- **Quota / Limit Handling (HTTP 429):**
  When a profile exhausts its free credits (code 429), the engine automatically flags it with a 12-hour cooldown and continues with the next ready profile in the pool.
  To manually reset cooldowns, run:
  ```powershell
  .\generate.bat --reset-limits
  ```
