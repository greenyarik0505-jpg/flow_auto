# Claude Code Instructions for Google Flow

This project automates Google Flow video (Veo 3.1 & Gemini Omni) and image (Imagen 4) generation across multiple Google accounts (1..34+).

## Capabilities & Tooling

Claude Code can generate media using either:
1. **MCP Tools (`google-flow`):**
   - `gflow_generate_video(prompt, model, aspect, duration)`
   - `gflow_generate_image(prompt, model, aspect, count)`
   - `gflow_get_credits()`
   - `gflow_auth_status(profile)`
   - `gflow_list_models()`

2. **CLI Executables:**
   - Video: `.\generate.bat <profile> "<prompt>"` or `.\generate.bat "<prompt>" --profile auto`
   - Image: `.\generate_image.bat <profile> "<prompt>"` or `.\generate_image.bat "<prompt>" --profile auto`
   - Account Status: `.\list_profiles.bat`
   - Reset Limit Cache: `.\generate.bat --reset-limits`
   - Account Authorization: `.\login.bat <id>`

## Guidelines
- Always use `omni-flash` for fast, fluid motion up to 10s.
- Always use `nano-pro` or `image4` for high-fidelity images.
- When generating without a specific account, use `--profile auto` to automatically rotate across accounts if quota (HTTP 429) is reached.
- Output files are stored in `D:\flow_auto\output\videos\` and `D:\flow_auto\output\images\`.
