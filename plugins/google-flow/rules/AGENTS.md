# Google Flow Operator & Agent Guidelines

When the Google Flow plugin is active, follow these operational guidelines for all AI video and image generation workflows:

## 1. Tool Selection Hierarchy

- **Video Generation (Veo 3.1 & Gemini Omni):**
  - **Via MCP:** Use `gflow_generate_video`.
    - `prompt`: Detailed cinematic description with lighting, camera movement, and atmosphere.
    - `model`: 
      - `"omni-flash"` (Gemini Omni 1.1 Flash) — recommended default for fast, fluid motion and long durations (up to 10s).
      - `"veo-quality"` (Veo 3.1 High Quality) — for maximum cinematic photorealism.
      - `"veo-fast"` — for quick drafts.
    - `aspect`: `"16:9"` (horizontal/desktop) or `"9:16"` (vertical/reels/shorts).
    - `duration`: 4, 6, 8, or 10 seconds.
  - **Via CLI / Terminal:** Run `.\generate.bat <profile> "<prompt>"` or `.\generate.bat "<prompt>" --profile auto`.

- **Image Generation (Imagen 4 & Nano Banana):**
  - **Via MCP:** Use `gflow_generate_image`.
    - `prompt`: Detailed prompt describing subject, environment, lighting, and style.
    - `model`: `"nano-pro"` (default high quality), `"image4"` (Imagen 4 photorealistic).
    - `aspect`: `"16:9"`, `"9:16"`, `"1:1"`, `"4:3"`, `"3:4"`.
    - `count`: 1 to 4 variations.
  - **Via CLI / Terminal:** Run `.\generate_image.bat <profile> "<prompt>"` or `.\generate_image.bat "<prompt>" --profile auto`.

- **Account & Quota Management:**
  - Check credits: Call `gflow_get_credits` or run `.\list_profiles.bat`.
  - Check auth: Call `gflow_auth_status` with `profile`.
  - If a profile returns HTTP 429 (quota exhausted), immediately switch to the next active profile in the pool (`auto-rotation`).
  - Reset limits: Run `.\generate.bat --reset-limits`.

## 2. Multi-Account Best Practices (1..34+ Profiles)

- Each Google account is isolated into its own persistent container (`profile_<name>`).
- Accounts do not share cookies or sessions, preventing Google detection and cross-account contamination.
- When the user specifies an account (e.g. `10` or `2`), route exclusively to that profile without touching others.
- When the user asks to generate without specifying an account, use `auto` to rotate through ready profiles.

## 3. Media Storage & Output

- Generated videos are saved to `D:\flow_auto\output\videos\`.
- Generated images are saved to `D:\flow_auto\output\images\`.
- Always report the local output file path and provide direct clickable links using `file:///D:/flow_auto/output/...`.
