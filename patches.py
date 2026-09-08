#!/usr/bin/env python3
"""Patches applied to the Hermes gateway code (image built from Dockerfile).

1. onboarding: onboarding.profile_build "off" turns the first-message intro
   OFF completely (without the patch, "off" still sends a "mention /help" note).
2. pdf: when a binary document (PDF) arrives, the gateway auto-extracts the text
   via pdftotext and injects it into context — a chat-only agent (no
   terminal/file tools) can read the document with zero tools (mirrors the
   auto-vision behavior for images).
3. whatsapp bridge: swap fetchLatestBaileysVersion (fetches from GitHub, hits
   429 rate limits) for fetchLatestWaWebVersion (fetches web.whatsapp.com/sw.js),
   removing the GitHub dependency from the WhatsApp connection.
4. notices: suppress ALL internal Hermes notices on WhatsApp
   (_deliver_platform_notice becomes a no-op on that platform) — contacts on
   the allowlist are served by the agent, and no stock message (sethome,
   credits/usage, whitelist) should ever reach them.
"""
p = "/opt/hermes-agent/gateway/run.py"
s = open(p, encoding="utf-8").read()

# --- Patch 1: onboarding intro off ---
old1 = '''                else:
                    turn_sidecar_notes.append(_intro_note)
            except Exception as _pb_err:'''
new1 = '''                elif profile_build_mode(_onb_cfg) != "off":
                    turn_sidecar_notes.append(_intro_note)
            except Exception as _pb_err:'''
n1 = s.count(old1)
assert n1 == 1, "onboarding patch anchor count=%d (expected 1)" % n1
s = s.replace(old1, new1, 1)

# --- Patch 2: PDF auto-extract ---
old2 = '''    return (
        f"[The user sent a document: '{display_name}'. It is saved at: {agent_path}. "
        f"Its text is not inlined here (it's a binary format such as PDF or DOCX). "
        f"To read it, extract the document's text yourself — for example with the "
        f"terminal tool or the ocr-and-documents skill — before answering, instead "
        f"of asking the user to paste the contents.]"
    )'''
new2 = '''    try:
        import subprocess as _sp
        import shutil as _sh
        _is_pdf = (mtype == "application/pdf") or str(agent_path).lower().endswith(".pdf")
        if _is_pdf and _sh.which("pdftotext"):
            _proc = _sp.run(["pdftotext", str(agent_path), "-"], capture_output=True, timeout=30)
            if _proc.returncode == 0:
                _text = _proc.stdout.decode("utf-8", errors="replace").strip()
                if _text:
                    return (
                        f"[The user sent a document: '{display_name}'. Auto-extracted text:\\n{_text}\\n(end of document). "
                        f"The file is saved at: {agent_path}]"
                    )
    except Exception:
        pass
    return (
        f"[The user sent a document: '{display_name}'. It is saved at: {agent_path}. "
        f"Its text is not inlined here (it's a binary format such as PDF or DOCX). "
        f"To read it, extract the document's text yourself — for example with the "
        f"terminal tool or the ocr-and-documents skill — before answering, instead "
        f"of asking the user to paste the contents.]"
    )'''
n2 = s.count(old2)
assert n2 == 1, "pdf patch anchor count=%d (expected 1)" % n2
s = s.replace(old2, new2, 1)

# --- Patch 4: no Hermes notices to WhatsApp (sethome, credits/usage, etc.) ---
old4 = '''    async def _deliver_platform_notice(self, source, content: str) -> None:
        """Deliver a setup/operational notice using platform-specific privacy rules."""
        adapter = self._adapter_for_source(source)'''
new4 = '''    async def _deliver_platform_notice(self, source, content: str) -> None:
        """Deliver a setup/operational notice using platform-specific privacy rules."""
        # attendant: suppress ALL default Hermes notices on WhatsApp (sethome,
        # credits/usage band pushes, etc.) — contacts only see the agent reply.
        if getattr(source, "platform", None) == Platform.WHATSAPP:
            logger.debug(
                "Suppressing Hermes platform notice on WhatsApp: %s",
                str(content)[:120],
            )
            return
        adapter = self._adapter_for_source(source)'''
n4 = s.count(old4)
assert n4 == 1, "platform-notice patch anchor count=%d (expected 1)" % n4
s = s.replace(old4, new4, 1)

open(p, "w", encoding="utf-8").write(s)

# --- Patch 3: WhatsApp bridge version fetch (GitHub → web.whatsapp.com) ---
bp = "/opt/hermes-agent/scripts/whatsapp-bridge/bridge.js"
bs = open(bp, encoding="utf-8").read()
old3 = "fetchLatestBaileysVersion"
new3 = "fetchLatestWaWebVersion"
n3 = bs.count(old3)
assert n3 == 2, "bridge patch anchor count=%d (expected 2)" % n3
bs = bs.replace(old3, new3)
open(bp, "w", encoding="utf-8").write(bs)

print("patches ok: onboarding intro off + pdf auto-extract + bridge version via web.whatsapp.com + no Hermes notices on WhatsApp")
