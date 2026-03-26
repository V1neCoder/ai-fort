import sys
import io
import base64
import zipfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shutil
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "backend"))
import server  # noqa: E402


class ToolRegistryTests(unittest.TestCase):
    def test_registry_parses_real_registered_tools(self):
        registry = server.ToolRegistry()

        material_tool = registry.get_tool("material_apply_preset")
        self.assertIsNotNone(material_tool)
        self.assertEqual(material_tool["id"], "material_apply_preset")
        self.assertTrue(any(param["name"] == "preset" for param in material_tool["parameters"]))
        self.assertIsNone(registry.get_tool("material_master"))

    def test_execute_tool_uses_keyword_arguments(self):
        registry = server.ToolRegistry()
        captured = {}

        def fake_post_command(port, command, payload, timeout=30.0):
            captured["port"] = port
            captured["command"] = command
            captured["code"] = payload["code"]
            return {"success": True, "result": {"result": {"status": "ok"}, "stdout": "", "stderr": ""}}

        with patch.object(server, "discover_uefn_listener_port", return_value=8765), patch.object(server, "mcp_listener_post_command", side_effect=fake_post_command):
            result = registry.execute_tool("material_apply_preset", {"preset": "gold"})

        self.assertTrue(result["success"])
        self.assertEqual(captured["command"], "execute_python")
        self.assertIn("tb.run('material_apply_preset', **{'preset': 'gold'})", captured["code"])


class ChatSessionStoreTests(unittest.TestCase):
    def test_store_persists_messages_and_summary(self):
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"chat_store_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        store = server.ChatSessionStore(tmpdir / "chat_sessions.json")
        session = store.create_session()

        updated = store.append_messages(
            session["id"],
            [
                {
                    "id": "u1",
                    "role": "user",
                    "content": "Color this red and keep the selection grouped.",
                    "timestamp": "2026-03-23T12:00:00Z",
                    "attachments": [],
                    "toolResult": None,
                },
                {
                    "id": "a1",
                    "role": "assistant",
                    "content": "Applied the team_red preset.",
                    "timestamp": "2026-03-23T12:00:05Z",
                    "attachments": [],
                    "toolResult": {
                        "tool": "material_apply_preset",
                        "output": {"success": True, "result": {"status": "completed"}},
                    },
                },
            ],
            provider="gemini",
            model="gemini-2.5-flash",
        )

        self.assertEqual(updated["title"], "Color this red and keep the selection grouped")
        self.assertIn("Recent user requests:", updated["memory_summary"])
        self.assertIn("material_apply_preset", updated["memory_summary"])

        reloaded = store.get_session(session["id"])
        self.assertEqual(len(reloaded["messages"]), 2)
        self.assertEqual(reloaded["last_provider"], "gemini")
        self.assertEqual(reloaded["last_model"], "gemini-2.5-flash")

    def test_store_can_rename_and_clear_session(self):
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"chat_store_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        store = server.ChatSessionStore(tmpdir / "chat_sessions.json")
        session = store.create_session()

        store.append_messages(
            session["id"],
            [
                {
                    "id": "u1",
                    "role": "user",
                    "content": "Inspect the selected actors.",
                    "timestamp": "2026-03-23T12:00:00Z",
                    "attachments": [],
                    "toolResult": None,
                }
            ],
            provider="groq",
            model="llama-3.3-70b-versatile",
        )

        updated = store.update_session(session["id"], title="Scene Audit", clear_messages=True)

        self.assertEqual(updated["title"], "Scene Audit")
        self.assertEqual(updated["messages"], [])
        self.assertEqual(updated["memory_summary"], "")

    def test_search_sessions_finds_related_chats(self):
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"chat_store_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        store = server.ChatSessionStore(tmpdir / "chat_sessions.json")
        session = store.create_session(title="Combat Arena Polish")
        store.append_messages(
            session["id"],
            [
                {
                    "id": "u1",
                    "role": "user",
                    "content": "Tune the combat arena lighting and red materials.",
                    "timestamp": "2026-03-23T12:00:00Z",
                    "attachments": [],
                    "toolResult": None,
                }
            ],
            provider="groq",
            model="llama-3.3-70b-versatile",
        )

        hits = store.search_sessions("arena lighting", limit=3)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], "Combat Arena Polish")


class KnowledgeStoreTests(unittest.TestCase):
    def test_knowledge_store_persists_and_searches_items(self):
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"knowledge_store_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        store = server.KnowledgeStore(tmpdir / "knowledge_store.json")

        created = store.add_item(
            item_type="text",
            source_type="manual",
            title="Lighting preference",
            content="Use strong warm rim lighting for arena intros.",
            tags=["lighting", "arena"],
        )
        store.add_item(
            item_type="text",
            source_type="manual",
            title="Verse note",
            content="Tracker device should reset every round.",
            tags=["verse", "device"],
        )

        hits = store.search("arena lighting", limit=5)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], "Lighting preference")

        updated = store.update_item(created["id"], quality=0)
        self.assertEqual(updated["quality"], 0)
        self.assertEqual(store.search("arena lighting", limit=5), [])

    def test_knowledge_store_learns_preferences_and_tool_outcomes(self):
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"knowledge_store_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        store = server.KnowledgeStore(tmpdir / "knowledge_store.json")

        store.remember_interaction(
            chat_id="chat-1",
            chat_title="Island Setup",
            user_message="Remember that I always want fast, stable models by default.",
            assistant_message={
                "toolResult": {
                    "tool": "material_apply_preset",
                    "output": {"success": True, "result": {"status": "completed"}},
                }
            },
        )

        hits = store.search("fast stable models", limit=5)
        self.assertTrue(any(item["source_type"] == "preference" for item in hits))
        tool_hits = store.search("material_apply_preset", limit=5)
        self.assertTrue(any(item["source_type"] == "tool_outcome" for item in tool_hits))

    def test_knowledge_store_remembers_attachment_text_and_ocr(self):
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"knowledge_store_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        store = server.KnowledgeStore(tmpdir / "knowledge_store.json")

        store.remember_attachments(
            chat_id="chat-2",
            chat_title="Visual Notes",
            attachments=[
                {"name": "notes.txt", "type": "file", "content": "The tower should glow red."},
                {"name": "shot.png", "type": "image", "analysisText": "BUILD RED"},
            ],
        )

        hits = store.search("glow red", limit=5)
        self.assertTrue(any(item["source_type"] == "attachment_text" for item in hits))
        ocr_hits = store.search("build red", limit=5)
        self.assertTrue(any(item["source_type"] == "attachment_ocr" for item in ocr_hits))

    def test_knowledge_store_remembers_binary_attachment_analysis(self):
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"knowledge_store_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        store = server.KnowledgeStore(tmpdir / "knowledge_store.json")

        store.remember_attachments(
            chat_id="chat-3",
            chat_title="Document Notes",
            attachments=[
                {
                    "name": "design-brief.pdf",
                    "type": "binary",
                    "mimeType": "application/pdf",
                    "analysisText": "The castle door glows red at sunset.",
                }
            ],
        )

        hits = store.search("castle door", limit=5)
        self.assertTrue(any(item["source_type"] == "attachment_analysis" for item in hits))

    def test_knowledge_store_remembers_attachments_beyond_six_items(self):
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"knowledge_store_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        store = server.KnowledgeStore(tmpdir / "knowledge_store.json")

        attachments = []
        for index in range(8):
            attachments.append({
                "name": f"note-{index}.txt",
                "type": "file",
                "content": f"File {index} says keep the lantern {'blue' if index < 7 else 'red'}.",
            })

        store.remember_attachments(
            chat_id="chat-5",
            chat_title="Attachment Fanout",
            attachments=attachments,
        )

        hits = store.search("lantern red", limit=10)
        self.assertTrue(any("note-7.txt" in item["title"] for item in hits))

    def test_knowledge_store_remembers_web_pages(self):
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"knowledge_store_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        store = server.KnowledgeStore(tmpdir / "knowledge_store.json")

        store.remember_attachments(
            chat_id="chat-4",
            chat_title="Web Notes",
            attachments=[
                {
                    "name": "Castle Guide",
                    "type": "file",
                    "sourceUrl": "https://example.com/castle",
                    "content": "The castle gate should glow red at dusk.",
                }
            ],
        )

        hits = store.search("gate glow red", limit=5)
        self.assertTrue(any(item["source_type"] == "web_page" for item in hits))


class ProviderModelTests(unittest.TestCase):
    def test_invalid_explicit_model_falls_back_to_provider_default(self):
        original_provider = server._llm_provider
        original_client = server._llm_client
        try:
            server._llm_provider = None
            server._llm_client = None
            with patch.dict(server.os.environ, {
                "AI_PROVIDER": "groq",
                "GROQ_API_KEY": "test-key",
                "AI_MODEL": "llama3.1-8b",
            }, clear=False):
                self.assertEqual(server._get_active_model(), "llama-3.3-70b-versatile")
        finally:
            server._llm_provider = original_provider
            server._llm_client = original_client

    def test_validate_requested_model_rejects_wrong_provider_model(self):
        with self.assertRaises(ValueError):
            server._validate_requested_model("groq", "gemini-2.5-flash")

    def test_resolve_llm_request_target_prefers_gemini_for_pdf_attachments(self):
        active_client = object()
        gemini_client = object()
        with patch.object(server, "_get_active_provider", return_value="groq"), \
             patch.object(server, "_get_active_model", return_value="llama-3.3-70b-versatile"), \
             patch.object(server, "_get_llm_client", return_value=active_client), \
             patch.object(server, "_create_llm_client_for_provider", side_effect=lambda provider: gemini_client if provider == "gemini" else None), \
             patch.object(server, "_get_runtime_model_for_provider", side_effect=lambda provider: "gemini-2.5-flash" if provider == "gemini" else "llama-3.3-70b-versatile"):
            client, provider, model = server._resolve_llm_request_target(
                [{"name": "brief.pdf", "type": "binary", "mimeType": "application/pdf"}],
                [],
            )

        self.assertIs(client, gemini_client)
        self.assertEqual(provider, "gemini")
        self.assertEqual(model, "gemini-2.5-flash")

    def test_chat_completion_with_retry_retries_transient_errors(self):
        calls = {"count": 0}

        class FakeResponse:
            usage = None

            class Choice:
                class Message:
                    content = "Recovered reply."

                message = Message()

            choices = [Choice()]

        class RetryableError(RuntimeError):
            status_code = 429

        class FakeCompletions:
            @staticmethod
            def create(**kwargs):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise RetryableError("rate limit")
                return FakeResponse()

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            chat = FakeChat()

        with patch.object(server.time, "sleep", return_value=None):
            response = server._chat_completion_with_retry(
                FakeClient(),
                "groq",
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "hello"}],
            )

        self.assertEqual(calls["count"], 2)
        self.assertEqual(response.choices[0].message.content, "Recovered reply.")


class ChatEndpointTests(unittest.TestCase):
    def test_chat_endpoint_persists_attachment_content_and_runtime_provider(self):
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"chat_endpoint_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))

        original_chat_store = server.chat_store
        original_knowledge_store = server.knowledge_store
        server.chat_store = server.ChatSessionStore(tmpdir / "chat_sessions.json")
        server.knowledge_store = server.KnowledgeStore(tmpdir / "knowledge_store.json")
        self.addCleanup(lambda: setattr(server, "chat_store", original_chat_store))
        self.addCleanup(lambda: setattr(server, "knowledge_store", original_knowledge_store))

        with patch.object(server, "_ai_chat", return_value={
            "reply": "I can see the uploaded image and will use it.",
            "_provider": "gemini",
            "_model": "gemini-2.5-flash",
        }):
            client = server.app.test_client()
            response = client.post("/api/chat", json={
                "message": "Use the attached image.",
                "attachments": [
                    {
                        "name": "preview.png",
                        "type": "image",
                        "mime_type": "image/png",
                        "size": 1234,
                        "content": "data:image/png;base64,AAAA",
                    }
                ],
            })

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["provider"], "gemini")
        self.assertEqual(payload["model"], "gemini-2.5-flash")

        saved_chat = payload["chat"]
        self.assertEqual(saved_chat["last_provider"], "gemini")
        self.assertEqual(saved_chat["last_model"], "gemini-2.5-flash")
        self.assertEqual(saved_chat["messages"][0]["attachments"][0]["name"], "preview.png")
        self.assertEqual(saved_chat["messages"][0]["attachments"][0]["type"], "image")
        self.assertEqual(saved_chat["messages"][0]["attachments"][0]["mimeType"], "image/png")
        self.assertEqual(saved_chat["messages"][0]["attachments"][0]["content"], "data:image/png;base64,AAAA")

    def test_direct_attachment_text_question_returns_file_content(self):
        result = server._ai_chat(
            "What text is in the attached file? Reply with the exact sentence only.",
            [{"name": "note.txt", "type": "file", "content": "The tower should glow red."}],
            [],
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["reply"], "The tower should glow red.")

    def test_direct_attachment_exact_question_surfaces_conflicting_candidates(self):
        result = server._ai_chat(
            "What does the image say? Reply with the exact text.",
            [
                {"name": "shot-a.png", "type": "image", "analysisText": "BUILD RED"},
                {"name": "shot-b.png", "type": "image", "analysisText": "BUILD BLUE"},
            ],
            [],
        )

        self.assertIsNotNone(result)
        self.assertIn("conflicting extracted evidence", result["reply"].lower())
        self.assertIn("[Attachment 1 §1]", result["reply"])
        self.assertIn("[Attachment 2 §1]", result["reply"])

    def test_direct_attachment_which_file_question_returns_top_match(self):
        result = server._ai_chat(
            "Which file mentions the red bridge?",
            [
                {"name": "blue-note.txt", "type": "file", "content": "The gate stays blue."},
                {"name": "red-note.txt", "type": "file", "content": "The red bridge glows at sunset."},
            ],
            [],
        )

        self.assertIsNotNone(result)
        self.assertIn("red-note.txt", result["reply"])
        self.assertIn("strongest match", result["reply"].lower())
        self.assertIn("[Attachment 1]", result["reply"])

    def test_image_chat_falls_back_to_ocr_when_hosted_vision_fails(self):
        with patch.object(server, "_resolve_llm_request_target", return_value=(object(), "gemini", "gemini-2.5-flash")), \
             patch.object(server, "_gemini_generate_content_chat", side_effect=RuntimeError("quota exceeded")), \
             patch.object(server, "_answer_with_attachment_analysis_context", return_value={"reply": "BUILD RED", "_provider": "groq", "_model": "llama-3.3-70b-versatile"}):
            result = server._ai_chat(
                "What does this screenshot say?",
                [{"name": "shot.png", "type": "image", "content": "data:image/png;base64,AAAA"}],
                [],
            )

        self.assertEqual(result["reply"], "BUILD RED")
        self.assertEqual(result["_provider"], "groq")

    def test_prepare_chat_attachment_extracts_pdf_text(self):
        with patch.object(server, "_extract_pdf_text_from_bytes", return_value="Design note: make the tower glow red."):
            attachment = server._prepare_chat_attachment({
                "name": "brief.pdf",
                "type": "binary",
                "mime_type": "application/pdf",
                "content": "data:application/pdf;base64,AAAA",
            })

        self.assertEqual(attachment["analysisText"], "Design note: make the tower glow red.")
        self.assertIn("PDF", attachment["analysisSummary"])

    def test_extract_pdf_text_samples_late_pages(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, _stream):
                self.pages = [FakePage(f"Page {index} filler") for index in range(1, 12)]
                self.pages[-1] = FakePage("Appendix: the gateway trim should be amber.")

        with patch.object(server, "_HAS_PYPDF", True), patch.object(server, "_PdfReader", FakeReader):
            extracted = server._extract_pdf_text_from_bytes(b"%PDF-1.4 fake")

        self.assertIn("Appendix: the gateway trim should be amber.", extracted)
        self.assertIn("Page 11", extracted)

    def test_prepare_chat_attachment_reuses_cached_analysis(self):
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"attachment_cache_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))

        original_cache = server.attachment_analysis_cache
        server.attachment_analysis_cache = server.AttachmentAnalysisCache(tmpdir / "attachment_analysis_cache.json")
        self.addCleanup(lambda: setattr(server, "attachment_analysis_cache", original_cache))

        attachment_payload = {
            "name": "brief.pdf",
            "type": "binary",
            "mime_type": "application/pdf",
            "content": "data:application/pdf;base64,AAAA",
        }

        with patch.object(server, "_extract_pdf_text_from_bytes", return_value="Cached PDF text."):
            first = server._prepare_chat_attachment(dict(attachment_payload))

        self.assertEqual(first["analysisText"], "Cached PDF text.")

        with patch.object(server, "_extract_pdf_text_from_bytes", side_effect=AssertionError("cache should be reused")):
            second = server._prepare_chat_attachment(dict(attachment_payload))

        self.assertEqual(second["analysisText"], "Cached PDF text.")
        self.assertTrue(second.get("attachmentFingerprint"))

    def test_prepare_chat_attachment_adds_local_visual_caption(self):
        with patch.object(server, "_extract_text_from_image_attachments", return_value="BUILD RED"), \
             patch.object(server, "_extract_semantic_descriptions_from_image_attachments", return_value="A white screenshot with the words BUILD RED in black text."), \
             patch.object(server, "_extract_handwriting_from_image_attachments", return_value="BUILD RED"), \
             patch.object(server, "_extract_visual_metadata_from_image_attachments", return_value={"width": 640, "height": 360, "orientation": "landscape", "dominantColorNames": ["white", "red"]}):
            attachment = server._prepare_chat_attachment({
                "name": "shot.png",
                "type": "image",
                "mime_type": "image/png",
                "content": "data:image/png;base64,AAAA",
            })

        self.assertEqual(attachment["analysisCaption"], "A white screenshot with the words BUILD RED in black text.")
        self.assertEqual(attachment["analysisHandwriting"], "BUILD RED")
        self.assertEqual(attachment["analysisMeta"]["width"], 640)
        self.assertIn("Image description:", attachment["analysisSummary"])
        self.assertIn("Visible text:", attachment["analysisSummary"])

    def test_ocr_multistage_prefers_high_quality_variant(self):
        original_variant = object()
        strong_variant = object()
        noisy_variant = object()

        variant_outputs = {
            id(original_variant): ["BUI1D", "R3D"],
            id(strong_variant): ["BUILD", "RED"],
            id(noisy_variant): ["@@@"],
        }

        with patch.object(
            server,
            "_build_ocr_image_variants",
            return_value=[
                ("original_upscaled", original_variant),
                ("high_contrast_sharpened", strong_variant),
                ("binary_threshold", noisy_variant),
            ],
        ), patch.object(
            server,
            "_run_rapidocr_on_pil_image",
            side_effect=lambda engine, image, variant_label="original": variant_outputs.get(id(image), []),
        ):
            result = server._ocr_pil_image_multistage(object(), object())

        self.assertEqual(result["text"], "BUILD\nRED")
        self.assertEqual(result["variant"], "high_contrast_sharpened")

    def test_prepare_chat_attachment_merges_structured_visual_analysis(self):
        with patch.object(server, "_extract_text_from_image_attachments", return_value="RED GATE"), \
             patch.object(server, "_extract_structured_visual_analysis_from_image_attachments", return_value={
                 "analysisText": "REDGATE",
                 "analysisCaption": "A red gate centered on a white background.",
                 "analysisMeta": {
                     "detectedObjects": ["gate"],
                     "visionSource": "florence2",
                 },
             }), \
             patch.object(server, "_extract_handwriting_from_image_attachments", return_value=""), \
             patch.object(server, "_extract_visual_metadata_from_image_attachments", return_value={
                 "width": 640,
                 "height": 360,
                 "orientation": "landscape",
             }):
            attachment = server._prepare_chat_attachment({
                "name": "concept.png",
                "type": "image",
                "mime_type": "image/png",
                "content": "data:image/png;base64,AAAA",
            })

        self.assertEqual(attachment["analysisText"], "RED GATE")
        self.assertEqual(attachment["analysisCaption"], "A red gate centered on a white background.")
        self.assertEqual(attachment["analysisMeta"]["detectedObjects"], ["gate"])
        self.assertEqual(attachment["analysisMeta"]["visionSource"], "florence2")
        self.assertEqual(attachment["analysisMeta"]["width"], 640)

    def test_prepare_chat_attachment_scanned_pdf_adds_handwriting_and_visual_context(self):
        with patch.object(server, "_extract_pdf_text_from_bytes", return_value=""), \
             patch.object(server, "_extract_scanned_pdf_analysis_from_bytes", return_value={
                 "analysisText": "OCR:\nPage 1: castle note\n\nHandwriting guess:\nPage 1: make the gate red",
                 "analysisHandwriting": "Page 1: make the gate red",
                 "analysisCaption": "Page 1: a handwritten castle design note",
                 "analysisMeta": {"pageCount": 1, "pageVisualDiagnostics": ["Page 1: 1200x1600; portrait"]},
             }):
            attachment = server._prepare_chat_attachment({
                "name": "note.pdf",
                "type": "binary",
                "mime_type": "application/pdf",
                "content": "data:application/pdf;base64,AAAA",
            })

        self.assertIn("make the gate red", attachment["analysisText"])
        self.assertEqual(attachment["analysisHandwriting"], "Page 1: make the gate red")
        self.assertEqual(attachment["analysisCaption"], "Page 1: a handwritten castle design note")
        self.assertEqual(attachment["analysisMeta"]["pageCount"], 1)

    def test_scanned_pdf_analysis_tracks_ocr_variant_diagnostics(self):
        fake_image = server._PILImage.new("RGB", (320, 480), "white")
        with patch.object(server, "_render_pdf_pages_to_pil_images", return_value=[fake_image]), \
             patch.object(server, "_combine_structured_visual_analyses", return_value={}), \
             patch.object(server, "_caption_pil_images", return_value=[]), \
             patch.object(server, "_extract_handwriting_from_pil_images", return_value=[]), \
             patch.object(server, "_get_ocr_engine", return_value=object()), \
             patch.object(server, "_ocr_pil_image_multistage", return_value={"text": "Castle PDF RED", "variant": "binary_threshold"}):
            result = server._extract_scanned_pdf_analysis_from_bytes(b"%PDF-1.4 fake")

        self.assertIn("Castle PDF RED", result["analysisText"])
        self.assertIn("ocrDiagnostics", result["analysisMeta"])
        self.assertIn("binary_threshold", result["analysisMeta"]["ocrDiagnostics"][0])

    def test_prepare_chat_attachment_extracts_docx_text(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "word/document.xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                    <w:body>
                        <w:p><w:r><w:t>Castle DOCX RED</w:t></w:r></w:p>
                    </w:body>
                </w:document>""",
            )
        data_url = "data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

        attachment = server._prepare_chat_attachment({
            "name": "brief.docx",
            "type": "binary",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "content": data_url,
        })

        self.assertIn("Castle DOCX RED", attachment["analysisText"])
        self.assertIn("DOCX", attachment["analysisSummary"])

    def test_prepare_chat_attachment_extracts_xlsx_text(self):
        from openpyxl import Workbook

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Castle"
        worksheet.append(["Zone", "Color"])
        worksheet.append(["Bridge", "Red"])

        buffer = io.BytesIO()
        workbook.save(buffer)
        data_url = "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

        attachment = server._prepare_chat_attachment({
            "name": "castle.xlsx",
            "type": "binary",
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "content": data_url,
        })

        self.assertIn("Sheet: Castle", attachment["analysisText"])
        self.assertIn("Bridge | Red", attachment["analysisText"])
        self.assertIn("XLSX", attachment["analysisSummary"])

    def test_prepare_chat_attachment_extracts_pptx_text(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "ppt/slides/slide1.xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
                    <p:cSld>
                        <p:spTree>
                            <p:sp>
                                <p:txBody>
                                    <a:p><a:r><a:t>Castle PPTX RED</a:t></a:r></a:p>
                                </p:txBody>
                            </p:sp>
                        </p:spTree>
                    </p:cSld>
                </p:sld>""",
            )

        data_url = "data:application/vnd.openxmlformats-officedocument.presentationml.presentation;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        attachment = server._prepare_chat_attachment({
            "name": "castle.pptx",
            "type": "binary",
            "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "content": data_url,
        })

        self.assertIn("Castle PPTX RED", attachment["analysisText"])
        self.assertIn("PPTX", attachment["analysisSummary"])

    def test_prepare_chat_attachment_extracts_zip_manifest(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("README.md", "# Castle Archive\nThe bridge should glow red.")
            archive.writestr("config/settings.json", '{"theme":"red"}')

        data_url = "data:application/zip;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        attachment = server._prepare_chat_attachment({
            "name": "castle-assets.zip",
            "type": "binary",
            "mime_type": "application/zip",
            "content": data_url,
        })

        self.assertIn("README.md", attachment["analysisText"])
        self.assertIn("glow red", attachment["analysisText"].lower())
        self.assertIn("Archive", attachment["analysisSummary"])

    def test_prepare_chat_attachment_extracts_epub_text(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr(
                "OEBPS/chapter1.xhtml",
                """<?xml version="1.0" encoding="utf-8"?>
                <html xmlns="http://www.w3.org/1999/xhtml">
                    <body><h1>Castle Guide</h1><p>The castle bridge glows red.</p></body>
                </html>""",
            )

        data_url = "data:application/epub+zip;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        attachment = server._prepare_chat_attachment({
            "name": "castle-guide.epub",
            "type": "binary",
            "mime_type": "application/epub+zip",
            "content": data_url,
        })

        self.assertIn("Castle Guide", attachment["analysisText"])
        self.assertIn("glows red", attachment["analysisText"])
        self.assertIn("EPUB", attachment["analysisSummary"])

    def test_prepare_chat_attachment_infers_markdown_type_from_filename(self):
        attachment = server._prepare_chat_attachment({
            "name": "castle-notes.md",
            "type": "file",
            "mime_type": "text/plain",
            "content": "# Castle Notes\nThe bridge should glow red.",
        })

        self.assertEqual(attachment["mimeType"], "text/markdown")
        self.assertIn("Castle Notes", attachment["analysisText"])
        self.assertEqual(attachment["analysisSummary"], "Castle Notes")

    def test_build_gemini_parts_puts_pdf_before_prompt_text(self):
        parts = server._build_gemini_generate_content_parts(
            "Summarize this PDF.",
            [{
                "name": "brief.pdf",
                "type": "binary",
                "mimeType": "application/pdf",
                "content": "data:application/pdf;base64,QUJDRA==",
                "analysisText": "Castle PDF RED",
            }],
        )

        self.assertIn("inline_data", parts[0])
        self.assertEqual(parts[1]["text"], "Summarize this PDF.")

    def test_attachment_analysis_fallback_uses_extracted_context(self):
        class FakeClient:
            pass

        fake_client = FakeClient()

        class FakeResponse:
            class Usage:
                prompt_tokens = 11
                completion_tokens = 7

            usage = Usage()

            class Choice:
                class Message:
                    content = "The screenshot says BUILD RED."

                message = Message()

            choices = [Choice()]

        class FakeCompletions:
            @staticmethod
            def create(**kwargs):
                return FakeResponse()

        class FakeChat:
            completions = FakeCompletions()

        fake_client.chat = FakeChat()

        with patch.object(server, "_resolve_text_fallback_target", return_value=(fake_client, "groq", "llama-3.3-70b-versatile")):
            result = server._answer_with_attachment_analysis_context(
                "What does this screenshot say?",
                [{"name": "shot.png", "type": "image", "analysisText": "BUILD RED", "analysisSummary": "Image with detected text: BUILD RED"}],
                preferred_provider="groq",
            )

        self.assertEqual(result["reply"], "The screenshot says BUILD RED.")
        self.assertEqual(result["_provider"], "groq")

    def test_direct_document_question_prefers_extracted_binary_text(self):
        result = server._ai_chat(
            "What does this doc say? Reply with the exact text.",
            [{
                "name": "castle-note.docx",
                "type": "binary",
                "content": "data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,AAAA",
                "analysisText": "DOCX castle note red bridge",
            }],
            [],
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["reply"], "DOCX castle note red bridge")

    def test_direct_image_question_can_use_visual_caption(self):
        result = server._ai_chat(
            "Describe this image.",
            [{
                "name": "concept.png",
                "type": "image",
                "analysisCaption": "A red bridge in front of a castle gate.",
            }],
            [],
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["reply"], "A red bridge in front of a castle gate.")

    def test_direct_image_description_prefers_caption_over_ocr(self):
        result = server._ai_chat(
            "Describe this image.",
            [{
                "name": "concept.png",
                "type": "image",
                "analysisCaption": "A red bridge in front of a castle gate.",
                "analysisText": "RED GATE",
            }],
            [],
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["reply"], "A red bridge in front of a castle gate.")

    def test_direct_handwriting_question_prefers_handwriting_guess(self):
        result = server._ai_chat(
            "What does the handwriting say?",
            [{
                "name": "note.png",
                "type": "image",
                "analysisCaption": "A handwritten note on white paper.",
                "analysisText": "unclear",
                "analysisHandwriting": "Make the building red.",
            }],
            [],
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["reply"], "Make the building red.")

    def test_direct_visual_review_reports_color_match(self):
        result = server._ai_chat(
            "Does this match the request to make the building red?",
            [{
                "name": "result.png",
                "type": "image",
                "analysisCaption": "A red building with a white roof.",
                "analysisMeta": {
                    "dominantColorNames": ["red", "white"],
                    "detectedObjects": ["building"],
                },
            }],
            [],
        )

        self.assertIsNotNone(result)
        self.assertIn("Likely matches the requested color change", result["reply"])
        self.assertIn("Detected colors: red, white.", result["reply"])

    def test_direct_visual_comparison_reports_differences(self):
        result = server._ai_chat(
            "What changed between these images?",
            [
                {
                    "name": "before.png",
                    "type": "image",
                    "analysisCaption": "A blue gate with a stone wall.",
                    "analysisText": "BLUE GATE",
                    "analysisMeta": {
                        "dominantColorNames": ["blue", "gray"],
                        "detectedObjects": ["gate"],
                    },
                },
                {
                    "name": "after.png",
                    "type": "image",
                    "analysisCaption": "A red gate with a stone wall.",
                    "analysisText": "RED GATE",
                    "analysisMeta": {
                        "dominantColorNames": ["red", "gray"],
                        "detectedObjects": ["gate"],
                    },
                },
            ],
            [],
        )

        self.assertIsNotNone(result)
        self.assertIn("Visual comparison:", result["reply"])
        self.assertIn("blue, gray -> red, gray", result["reply"])
        self.assertIn('Visible text changed: "BLUE GATE" -> "RED GATE".', result["reply"])

    def test_attachment_reasoning_context_includes_request_alignment_review(self):
        context = server._render_attachment_reasoning_context(
            [{
                "name": "result.png",
                "type": "image",
                "analysisCaption": "A red building with a white roof.",
                "analysisMeta": {
                    "dominantColorNames": ["red", "white"],
                    "detectedObjects": ["building"],
                },
            }],
            message="Does this match the request to make the building red?",
        )

        self.assertIn("REQUEST ALIGNMENT REVIEW:", context)
        self.assertIn("Likely matches the requested color change", context)

    def test_resolve_effective_turn_attachments_reuses_recent_attachment_for_followup(self):
        history = [{
            "role": "user",
            "content": "What is wrong here?",
            "attachments": [{
                "name": "result.png",
                "type": "image",
                "mimeType": "image/png",
                "analysisCaption": "A white stepped wall with visible triangular roof gaps.",
                "analysisMeta": {
                    "dominantColorNames": ["white", "blue"],
                    "detectedObjects": ["building", "roof"],
                },
                "content": "data:image/png;base64,AAAA",
            }],
        }]

        effective = server._resolve_effective_turn_attachments("could u fix it", [], history)

        self.assertEqual(len(effective), 1)
        self.assertEqual(effective[0]["name"], "result.png")
        self.assertIn("triangular roof gaps", effective[0]["analysisCaption"])

    def test_ai_chat_followup_uses_recent_attachment_context_in_prompt(self):
        captured = {}

        class FakeResponse:
            usage = None

            class Choice:
                class Message:
                    content = "I'll fix the roof gap in UEFN."
                    tool_calls = []

                message = Message()

            choices = [Choice()]

        def fake_completion(client, provider, *, model, messages, **kwargs):
            captured["messages"] = messages
            return FakeResponse()

        with patch.object(server, "_resolve_llm_request_target", return_value=(object(), "groq", "llama-3.3-70b-versatile")), \
             patch.object(server, "_chat_completion_with_retry", side_effect=fake_completion), \
             patch.object(server, "_track_usage", return_value=None):
            result = server._ai_chat(
                "could u fix it",
                [],
                [{
                    "role": "user",
                    "content": "What is wrong here?",
                    "attachments": [{
                        "name": "result.png",
                        "type": "image",
                        "mimeType": "image/png",
                        "analysisCaption": "A white stepped wall with visible triangular roof gaps.",
                        "analysisMeta": {"detectedObjects": ["building", "roof"]},
                        "content": "data:image/png;base64,AAAA",
                    }],
                }],
            )

        self.assertEqual(result["reply"], "I'll fix the roof gap in UEFN.")
        self.assertIn("result.png", captured["messages"][-1]["content"])
        self.assertIn("triangular roof gaps", captured["messages"][-1]["content"])

    def test_build_execution_precheck_block_uses_selection_and_attachment_issue(self):
        with patch.object(server, "discover_uefn_listener_port", return_value=8765), \
             patch.object(server, "_get_uefn_context", return_value={
                 "connected": True,
                 "selected_actors": [{"name": "SM_Roof_Left"}, {"name": "SM_Roof_Right"}],
                 "level": {"world_name": "CastleMap", "actor_count": 63},
             }):
            block = server._build_execution_precheck_block(
                "fix it",
                [{
                    "name": "result.png",
                    "type": "image",
                    "mimeType": "image/png",
                    "analysisSummary": "Image description: stepped wall with visible roof gaps",
                    "analysisMeta": {"detectedObjects": ["building", "roof"]},
                }],
            )

        self.assertIn("LIVE EXECUTION PRECHECK:", block)
        self.assertIn("SM_Roof_Left", block)
        self.assertIn("CastleMap", block)
        self.assertIn("stepped wall with visible roof gaps", block)

    def test_ai_chat_attachment_fix_requests_do_not_force_required_tool_choice(self):
        captured = {}

        class FakeResponse:
            usage = None

            class Choice:
                class Message:
                    content = "I'll inspect the target and fix it."
                    tool_calls = []

                message = Message()

            choices = [Choice()]

        def fake_completion(client, provider, *, model, messages, tools=None, tool_choice=None, **kwargs):
            captured["tool_choice"] = tool_choice
            return FakeResponse()

        with patch.object(server, "_resolve_llm_request_target", return_value=(object(), "groq", "llama-3.3-70b-versatile")), \
             patch.object(server, "_maybe_execute_direct_action", return_value=None), \
             patch.object(server, "_chat_completion_with_retry", side_effect=fake_completion), \
             patch.object(server, "_track_usage", return_value=None), \
             patch.object(server, "discover_uefn_listener_port", return_value=8765), \
             patch.object(server, "_get_uefn_context", return_value={"connected": True, "selected_actors": [], "level": {}}), \
             patch.object(server, "_chat_uefn_query", return_value={"success": False}):
            server._ai_chat(
                "fix it",
                [{
                    "name": "result.png",
                    "type": "image",
                    "mimeType": "image/png",
                    "analysisCaption": "A roof seam with a visible hole.",
                    "content": "data:image/png;base64,AAAA",
                }],
                [],
            )

        self.assertEqual(captured["tool_choice"], "auto")

    def test_ai_chat_structure_requests_force_required_tool_choice_and_tool_routing(self):
        captured = {}

        class FakeResponse:
            usage = None

            class Choice:
                class Message:
                    content = "I will build the structure with the shared planner."
                    tool_calls = []

                message = Message()

            choices = [Choice()]

        def fake_completion(client, provider, *, model, messages, tools=None, tool_choice=None, **kwargs):
            captured["tool_choice"] = tool_choice
            captured["messages"] = messages
            return FakeResponse()

        with patch.object(server, "_resolve_llm_request_target", return_value=(object(), "groq", "llama-3.3-70b-versatile")), \
             patch.object(server, "_maybe_execute_direct_action", return_value=None), \
             patch.object(server, "_chat_completion_with_retry", side_effect=fake_completion), \
             patch.object(server, "_track_usage", return_value=None), \
             patch.object(server, "discover_uefn_listener_port", return_value=8765), \
             patch.object(server, "_get_uefn_context", return_value={"connected": True, "selected_actors": [], "level": {}}), \
             patch.object(server, "_chat_uefn_query", return_value={"success": False}):
            server._ai_chat(
                "build me a wide industrial warehouse with a steep roof",
                [],
                [],
            )

        self.assertEqual(captured["tool_choice"], "required")
        system_prompt = "\n".join(str(message.get("content") or "") for message in captured["messages"] if message.get("role") == "system")
        self.assertIn("TOOL ROUTING GUIDANCE:", system_prompt)
        self.assertIn("build_structure_action", system_prompt)
        self.assertIn('structure="warehouse"', system_prompt)

    def test_handle_tool_call_blocks_unsafe_broad_python_mutation(self):
        result = server._handle_tool_call("execute_python_in_uefn", {
            "code": (
                "import unreal\n"
                "actors = unreal.EditorLevelLibrary.get_all_level_actors()\n"
                "for actor in actors:\n"
                "    actor.set_actor_location(unreal.Vector(0,0,0), False, False)\n"
                "result = 'done'\n"
            )
        })

        self.assertIn("Blocked unsafe Python action", result["error"])

    def test_execute_action_blocks_blocks_unsafe_broad_python_mutation(self):
        results = server._execute_action_blocks(
            "```action\n"
            "{\"action\": \"execute_python_in_uefn\", \"code\": \"import unreal\\nactors = unreal.EditorLevelLibrary.get_all_level_actors()\\nfor actor in actors:\\n    actor.set_actor_location(unreal.Vector(0,0,0), False, False)\\nresult = 'done'\"}\n"
            "```"
        )

        self.assertEqual(len(results), 1)
        self.assertIn("Blocked unsafe Python action", results[0]["error"])

    def test_execute_action_blocks_supports_action_aliases_and_ignores_result_json(self):
        with patch.object(server, "_execute_apply_material", return_value={"success": True, "result": "ok"}) as fake_apply:
            results = server._execute_action_blocks(
                "```json\n"
                "{\"result\": \"Created basic geometry for a waterfall.\"}\n"
                "```\n\n"
                "```action\n"
                "{\"action\": \"apply_material_action\", \"actor_pattern\": \"Waterfall_*\", \"material\": \"water\"}\n"
                "```"
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["action"], "apply_material")
        fake_apply.assert_called_once()

    def test_attachment_reasoning_context_adds_summary_coverage_for_broad_summary_requests(self):
        attachment = {
            "name": "pascal-editor.pdf",
            "type": "file",
            "mimeType": "text/plain",
            "content": (
                ("Intro: Pascal Editor is a 3D building editor built with React Three Fiber and WebGPU. " * 80)
                + ("Middle: It persists graph data to IndexedDB, supports undo and redo, and maps node ids to Three.js objects. " * 80)
                + ("Ending: The later sections document camera controls, registry internals, serialization rules, and package boundaries across the monorepo. " * 80)
            ),
        }

        context = server._render_attachment_reasoning_context(
            [attachment],
            message="read this and tell me what this is about",
        )

        self.assertIn("SUMMARY COVERAGE:", context)
        self.assertIn("React Three Fiber and WebGPU", context)
        self.assertIn("IndexedDB, supports undo and redo", context)
        self.assertIn("camera controls, registry internals, serialization rules", context)

    def test_attachment_dossier_includes_late_relevant_attachment(self):
        attachments = []
        for index in range(8):
            attachments.append({
                "name": f"note-{index}.txt",
                "type": "file",
                "mimeType": "text/plain",
                "content": f"Attachment {index} says the bridge stays blue.",
            })
        attachments[-1]["content"] = "Attachment 7 says the bridge turns red at sunset."

        dossier = server._build_attachment_dossier("Which file mentions the bridge turning red?", attachments)

        self.assertIn("note-7.txt", dossier["dossier"])
        self.assertIn("bridge turns red", dossier["dossier"])

    def test_attachment_reasoning_context_keeps_late_attachments(self):
        attachments = []
        for index in range(8):
            attachments.append({
                "name": f"report-{index}.txt",
                "type": "file",
                "mimeType": "text/plain",
                "content": f"Report {index}: default placeholder text.",
            })
        attachments[-1]["content"] = "Report 7: the tower door glows green."

        context = server._render_attachment_reasoning_context(
            attachments,
            message="Which report says the tower door glows green?",
        )

        self.assertIn("report-7.txt", context)
        self.assertIn("tower door glows green", context)

    def test_attachment_dossier_can_pull_evidence_from_late_long_text_sections(self):
        long_prefix = "intro section " * 1200
        late_fact = "The final appendix says the portal trim must be amber."
        attachments = [{
            "name": "design-spec.txt",
            "type": "file",
            "mimeType": "text/plain",
            "content": long_prefix + late_fact,
        }]

        dossier = server._build_attachment_dossier(
            "Which file says the portal trim must be amber?",
            attachments,
        )

        self.assertIn("design-spec.txt", dossier["dossier"])
        self.assertIn("portal trim must be amber", dossier["dossier"])

    def test_attachment_dossier_includes_evidence_refs_and_confidence(self):
        dossier = server._build_attachment_dossier(
            "Which file says the bridge turns red?",
            [{
                "name": "bridge-note.txt",
                "type": "file",
                "mimeType": "text/plain",
                "content": "Bridge status report. The bridge turns red at sunset.",
            }],
        )

        self.assertIn("TOP SUPPORTING EVIDENCE", dossier["dossier"])
        self.assertIn("[Attachment 1 §1]", dossier["dossier"])
        self.assertIn("Evidence confidence for this turn:", dossier["dossier"])
        self.assertEqual(dossier["confidence"]["label"], "high")

    def test_attachment_conflicts_detect_text_disagreement(self):
        conflicts = server._detect_attachment_conflicts(
            "What does this image say? Reply with the exact text.",
            [
                {
                    "name": "shot-a.png",
                    "type": "image",
                    "_dossierRank": 1,
                    "analysisText": "BUILD RED",
                },
                {
                    "name": "shot-b.png",
                    "type": "image",
                    "_dossierRank": 2,
                    "analysisText": "BUILD BLUE",
                },
            ],
        )

        self.assertTrue(conflicts)
        self.assertIn("Potential text conflict", conflicts[0])

    def test_keyword_attachment_reply_uses_compiled_analysis(self):
        reply = server._keyword_chat(
            "Which file mentions the red bridge?",
            [
                {
                    "name": "blue-note.txt",
                    "type": "file",
                    "mimeType": "text/plain",
                    "content": "The gate stays blue.",
                },
                {
                    "name": "red-note.txt",
                    "type": "file",
                    "mimeType": "text/plain",
                    "content": "The red bridge glows at sunset.",
                },
            ],
            [],
        )["reply"]

        self.assertIn("I analyzed 2 attachment(s)", reply)
        self.assertIn("red-note.txt", reply)
        self.assertIn("red bridge", reply.lower())
        self.assertIn("Evidence confidence:", reply)
        self.assertIn("Best supporting evidence:", reply)

    def test_chat_status_reports_structured_local_vision(self):
        client = server.app.test_client()
        response = client.get("/api/chat/status")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("local_structured_vlm", payload)
        self.assertIn("enabled", payload["local_structured_vlm"])
        self.assertIn("model", payload["local_structured_vlm"])
        self.assertIn("local_model_prewarm", payload)
        self.assertIn("components", payload["local_model_prewarm"])
        self.assertIn("hosted_llm_retries", payload)
        self.assertIn("attachment_analysis_cache", payload)
        self.assertIn("entries", payload["attachment_analysis_cache"])

    def test_health_reports_structured_local_vision_feature(self):
        client = server.app.test_client()
        response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["api_version"], "2.4")
        self.assertTrue(payload["features"]["structured_local_vision"])
        self.assertTrue(payload["features"]["hosted_llm_retries"])
        self.assertTrue(payload["features"]["local_model_prewarm"])
        self.assertTrue(payload["features"]["fast_startup_ping"])

    def test_ping_reports_fast_startup_feature(self):
        client = server.app.test_client()
        response = client.get("/api/ping")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["api_version"], "2.4")
        self.assertTrue(payload["features"]["fast_startup_ping"])

    def test_analyze_chat_attachments_returns_evidence_and_confidence(self):
        original_chat_store = server.chat_store
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"attachment_index_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        server.chat_store = server.ChatSessionStore(tmpdir / "chat_sessions.json")
        self.addCleanup(lambda: setattr(server, "chat_store", original_chat_store))

        session = server.chat_store.create_session(title="Attachment Review")
        server.chat_store.append_messages(
            session["id"],
            [
                {
                    "id": "u1",
                    "role": "user",
                    "content": "Review the uploaded files.",
                    "timestamp": "2026-03-23T12:00:00Z",
                    "attachments": [
                        {
                            "name": "brief.txt",
                            "type": "file",
                            "mimeType": "text/plain",
                            "content": "The castle bridge should glow red at dusk.",
                        }
                    ],
                    "toolResult": None,
                }
            ],
            provider="groq",
            model="llama-3.3-70b-versatile",
        )

        result = server._analyze_chat_attachments(session["id"], query="bridge red", limit=4)

        self.assertEqual(result["count"], 1)
        self.assertTrue(result["evidence"])
        self.assertIn("reference", result["evidence"][0])
        self.assertIn("confidence", result)

    def test_local_model_prewarm_worker_updates_component_status(self):
        original_status = server._copy_local_model_prewarm_status()
        original_thread = server._local_model_prewarm_thread
        self.addCleanup(lambda: setattr(server, "_local_model_prewarm_thread", original_thread))
        self.addCleanup(lambda: setattr(server, "_local_model_prewarm_status", original_status))

        server._local_model_prewarm_status = {
            "enabled": True,
            "running": False,
            "started_at": "",
            "completed_at": "",
            "components": {
                "ocr": {"status": "pending", "ready": False, "detail": ""},
                "structured_vlm": {"status": "pending", "ready": False, "detail": "", "model": server.LOCAL_STRUCTURED_VLM_MODEL_ID},
                "vlm": {"status": "pending", "ready": False, "detail": "", "model": server.LOCAL_VLM_MODEL_ID},
                "handwriting": {"status": "pending", "ready": False, "detail": "", "model": server.LOCAL_HTR_MODEL_ID},
            },
        }

        with patch.object(server, "LOCAL_MODEL_PREWARM_ENABLED", True), \
             patch.object(server, "LOCAL_MODEL_PREWARM_DELAY_SECONDS", 0.0), \
             patch.object(server, "_get_ocr_engine", return_value=object()), \
             patch.object(server, "_get_local_structured_vlm", return_value=(object(), object())), \
             patch.object(server, "_get_local_vlm_pipeline", return_value=object()), \
             patch.object(server, "_get_local_htr_pipeline", return_value=(object(), object())):
            server._prewarm_local_models_worker()

        status = server._copy_local_model_prewarm_status()
        self.assertFalse(status["running"])
        self.assertTrue(status["completed_at"])
        self.assertEqual(status["components"]["structured_vlm"]["status"], "ready")
        self.assertTrue(status["components"]["handwriting"]["ready"])

    def test_chat_endpoint_imports_url_content_into_attachments(self):
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"chat_endpoint_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))

        original_chat_store = server.chat_store
        original_knowledge_store = server.knowledge_store
        server.chat_store = server.ChatSessionStore(tmpdir / "chat_sessions.json")
        server.knowledge_store = server.KnowledgeStore(tmpdir / "knowledge_store.json")
        self.addCleanup(lambda: setattr(server, "chat_store", original_chat_store))
        self.addCleanup(lambda: setattr(server, "knowledge_store", original_knowledge_store))

        fetched_attachment = {
            "name": "Castle Guide",
            "type": "file",
            "mimeType": "text/html",
            "sourceUrl": "https://example.com/castle",
            "content": "The castle gate should glow red at dusk.",
            "analysisSummary": "Castle Guide",
            "analysisKeywords": ["castle", "gate", "red"],
        }

        with patch.object(server, "_fetch_web_attachment_from_url", return_value=fetched_attachment), patch.object(server, "_ai_chat", return_value={
            "reply": "I read the linked page.",
            "_provider": "groq",
            "_model": "llama-3.3-70b-versatile",
        }):
            client = server.app.test_client()
            response = client.post("/api/chat", json={
                "message": "Read this site https://example.com/castle",
                "attachments": [],
            })

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        saved_attachment = payload["chat"]["messages"][0]["attachments"][0]
        self.assertEqual(saved_attachment["sourceUrl"], "https://example.com/castle")
        self.assertEqual(saved_attachment["analysisSummary"], "Castle Guide")
        knowledge_hits = server.knowledge_store.search("gate glow red", limit=5)
        self.assertTrue(any(item["source_type"] == "web_page" for item in knowledge_hits))

    def test_handle_tool_call_can_analyze_chat_attachments(self):
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        tmpdir = fixtures_root / f"chat_store_{uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))

        original_chat_store = server.chat_store
        server.chat_store = server.ChatSessionStore(tmpdir / "chat_sessions.json")
        self.addCleanup(lambda: setattr(server, "chat_store", original_chat_store))

        session = server.chat_store.create_session(title="Attachment Search")
        server.chat_store.append_messages(
            session["id"],
            [
                {
                    "id": "u1",
                    "role": "user",
                    "content": "Use the attached screenshot.",
                    "timestamp": "2026-03-23T12:00:00Z",
                    "attachments": [
                        {
                            "name": "shot.png",
                            "type": "image",
                            "mimeType": "image/png",
                            "analysisSummary": "Image with detected text: BUILD RED",
                            "analysisText": "BUILD RED",
                            "analysisKeywords": ["build", "red"],
                            "content": "data:image/png;base64,AAAA",
                        }
                    ],
                    "toolResult": None,
                }
            ],
            provider="groq",
            model="llama-3.3-70b-versatile",
        )

        result = server._handle_tool_call("analyze_chat_attachments", {
            "chat_id": session["id"],
            "query": "build red",
            "limit": 5,
        })

        self.assertTrue(result["success"])
        self.assertEqual(result["results"]["count"], 1)
        self.assertEqual(result["results"]["attachments"][0]["name"], "shot.png")

    def test_chat_functions_and_project_overview_expose_server_actions(self):
        function_names = {
            item["function"]["name"]
            for item in server._CHAT_FUNCTIONS
            if item.get("type") == "function"
        }
        with patch.object(server, "_get_uefn_context", return_value={
            "connected": True,
            "project": {"project_name": "DemoProject"},
            "level": {"world_name": "DemoLevel"},
            "selected_actors": [],
        }):
            overview = server._get_project_overview()
        action_ids = {item["id"] for item in overview["server_actions"]}

        self.assertIn("build_house_action", function_names)
        self.assertIn("build_structure_action", function_names)
        self.assertIn("terrain_action", function_names)
        self.assertIn("import_attached_models", function_names)
        self.assertIn("build_house_action", action_ids)
        self.assertIn("build_structure_action", action_ids)
        self.assertIn("apply_material_action", function_names)
        self.assertIn("terrain_action", action_ids)
        self.assertIn("import_attached_models", action_ids)

    def test_handle_tool_call_can_execute_build_house_action(self):
        with patch.object(server, "_execute_build_house", return_value={"success": True, "summary": "built house"}) as fake_build_house:
            result = server._handle_tool_call("build_house_action", {
                "request": "build a modern house here",
                "style": "modern",
            })

        self.assertTrue(result["success"])
        self.assertEqual(result["summary"], "built house")
        fake_build_house.assert_called_once()

    def test_handle_tool_call_can_execute_build_structure_action(self):
        with patch.object(server, "_execute_build_structure_request", return_value={"success": True, "summary": "built pavilion"}) as fake_build_structure:
            result = server._handle_tool_call("build_structure_action", {
                "request": "build a garden pavilion here",
                "structure": "pavilion",
                "style": "garden",
            })

        self.assertTrue(result["success"])
        self.assertEqual(result["summary"], "built pavilion")
        fake_build_structure.assert_called_once()

    def test_generate_structure_spec_supports_expanded_families_and_modifiers(self):
        spec, variation = server._generate_structure_spec_from_request(
            {
                "structure": "warehouse",
                "size": "large",
            },
            message="build a wide industrial warehouse with a steep roof",
            chat_id="chat-warehouse",
            support_context={
                "center_x": 1200.0,
                "center_y": 2400.0,
                "support_z": 0.0,
                "support_surface_kind": "support_surface",
                "support_level": 0,
                "support_actor_label": "GridPlane4",
            },
        )

        self.assertEqual(spec.structure_type, "warehouse")
        self.assertEqual(spec.label_prefix, "UCA_Warehouse")
        self.assertEqual(variation["style"], "industrial")
        self.assertGreater(spec.width_cm, 1400.0)
        self.assertGreater(spec.roof_pitch_deg, 15.0)
        self.assertEqual(variation["body_material"], "metal")
        self.assertEqual(variation["roof_material"], "metal")

    def test_handle_tool_call_can_execute_terrain_action(self):
        with patch.object(server, "_execute_terrain_control", return_value={"success": True, "summary": "created terrain"}) as fake_terrain:
            result = server._handle_tool_call("terrain_action", {
                "operation": "create",
                "terrain_type": "ridge",
                "size": {"x": 6000, "y": 2200},
            })

        self.assertTrue(result["success"])
        self.assertEqual(result["summary"], "created terrain")
        fake_terrain.assert_called_once()

    def test_handle_tool_call_can_import_attached_models_from_active_context(self):
        server._set_active_tool_context(message="import these models into uefn", attachments=[{
            "name": "castle-wall.fbx",
            "type": "binary",
            "mimeType": "application/octet-stream",
            "content": "data:application/octet-stream;base64,AAAA",
        }], chat_id="chat-123")
        self.addCleanup(server._clear_active_tool_context)

        with patch.object(server, "_maybe_import_and_place_model_attachments", return_value={
            "reply": "Imported 1 model into /Game/CodexImports/Test.",
            "tool_result": {
                "tool": "import_models",
                "output": {
                    "success": True,
                    "dest_path": "/Game/CodexImports/Test",
                    "asset_paths": ["/Game/CodexImports/Test/castle_wall"],
                },
            },
        }) as fake_import:
            result = server._handle_tool_call("import_attached_models", {"request": "import these models"})

        self.assertTrue(result["success"])
        self.assertIn("/Game/CodexImports/Test", result["reply"])
        fake_import.assert_called_once()


class ModelImportExecutionTests(unittest.TestCase):
    def test_execute_action_blocks_supports_build_house(self):
        reply = """I am building the house now.
```action
{"action": "build_house", "request": "build a cozy house here", "style": "cottage"}
```"""

        with patch.object(server, "_execute_build_house", return_value={"success": True, "result": {"zone_id": "zone_house_test"}}) as fake_build_house:
            results = server._execute_action_blocks(reply)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["action"], "build_house")
        self.assertTrue(results[0]["success"])
        fake_build_house.assert_called_once()

    def test_generative_build_delegates_house_requests_to_shared_house_executor(self):
        with patch.object(server, "_execute_build_house", return_value={"success": True, "summary": "built via shared planner"}) as fake_build_house, \
             patch.object(server, "discover_uefn_listener_port", return_value=8765):
            result = server._execute_generative_build({
                "structure": "house",
                "position": {"x": 4000, "y": 4200, "z": 0},
                "size": "medium",
                "material": "brick",
            })

        self.assertTrue(result["success"])
        fake_build_house.assert_called_once()
        delegated_action = fake_build_house.call_args.args[0]
        self.assertEqual(delegated_action["position"]["x"], 4000)
        self.assertEqual(delegated_action["material"], "brick")

    def test_generative_build_delegates_planned_structure_requests_to_shared_structure_executor(self):
        with patch.object(server, "_execute_build_structure_request", return_value={"success": True, "summary": "built shared pavilion"}) as fake_build_structure, \
             patch.object(server, "discover_uefn_listener_port", return_value=8765):
            result = server._execute_generative_build({
                "structure": "pavilion",
                "position": {"x": 4100, "y": 4150, "z": 0},
                "size": "large",
                "material": "wood",
            })

        self.assertTrue(result["success"])
        fake_build_structure.assert_called_once()
        delegated_action = fake_build_structure.call_args.args[0]
        self.assertEqual(delegated_action["position"]["x"], 4100)
        self.assertEqual(delegated_action["structure"], "pavilion")
        self.assertEqual(delegated_action["material"], "wood")

    def test_direct_action_shortcuts_explicit_structure_build_requests(self):
        with patch.object(server, "_maybe_import_and_place_model_attachments", return_value=None), \
             patch.object(server, "_execute_build_structure_request", return_value={"success": True, "summary": "built direct gazebo"}) as fake_build_structure:
            result = server._maybe_execute_direct_action("build me a gazebo here")

        self.assertTrue(result["success"])
        fake_build_structure.assert_called_once()
        delegated_action = fake_build_structure.call_args.args[0]
        self.assertEqual(delegated_action["structure"], "gazebo")

    def test_system_prompt_includes_shared_house_generation_grounding(self):
        prompt = server._build_system_prompt(chat_title="House Chat", chat_memory="User likes varied houses.")
        self.assertIn("build_house_action", prompt)
        self.assertIn("build_structure_action", prompt)
        self.assertIn("House Generation Grounding", prompt)
        self.assertIn("Structure Generation Grounding", prompt)
        self.assertIn("Tool Execution Grounding", prompt)
        self.assertIn("Do not generate the exact same house every time.", prompt)
        self.assertIn("Use shared geometry planners and managed actions for structures whenever possible.", prompt)

    def test_generative_build_supports_waterfall_structure(self):
        captured = {}

        def fake_post_command(port, command, payload, timeout=30.0):
            captured["port"] = port
            captured["command"] = command
            captured["code"] = payload["code"]
            return {"success": True, "result": {"status": "ok"}}

        with patch.object(server, "discover_uefn_listener_port", return_value=8765), \
             patch.object(server, "mcp_listener_post_command", side_effect=fake_post_command):
            result = server._execute_generative_build({
                "structure": "waterfall",
                "position": {"x": 6000, "y": 6000, "z": 0},
                "size": "medium",
                "material": "cliff",
            })

        self.assertTrue(result["success"])
        self.assertEqual(captured["command"], "execute_python")
        self.assertIn("Waterfall_Cascade_Main", captured["code"])
        self.assertIn("set_actor_rotation", captured["code"])
        self.assertIn(server.MATERIAL_CATALOG["water"], captured["code"])

    def test_direct_action_builds_waterfall_scene_with_hills_deterministically(self):
        terrain_calls = []
        build_calls = []

        with patch.object(server, "discover_uefn_listener_port", return_value=8765), \
             patch.object(server, "_get_uefn_context", return_value={
                 "connected": True,
                 "selected_actors": [],
                 "viewport": {
                     "location": {"x": 1000.0, "y": 2000.0, "z": 900.0},
                     "rotation": {"yaw": 90.0},
                 },
             }), \
             patch.object(server, "_execute_terrain_control", side_effect=lambda action: terrain_calls.append(action) or {"success": True, "result": {"status": "ok"}}), \
             patch.object(server, "_execute_generative_build", side_effect=lambda action: build_calls.append(action) or {"success": True, "result": {"status": "ok"}}):
            result = server._maybe_execute_direct_action("create me a waterfall with hills")

        self.assertIsNotNone(result)
        self.assertIn("continuous waterfall", result["reply"])
        self.assertEqual(len(terrain_calls), 1)
        self.assertEqual(terrain_calls[0]["terrain_type"], "ridge")
        self.assertFalse(terrain_calls[0]["decorate"])
        self.assertEqual(terrain_calls[0]["material"], "grass")
        self.assertEqual(len(build_calls), 1)
        self.assertEqual(build_calls[0]["structure"], "waterfall")
        self.assertEqual(build_calls[0]["material"], "cliff")
        self.assertEqual(terrain_calls[0]["position"]["y"], 4200.0)
        self.assertEqual(build_calls[0]["position"]["y"], 4200.0)
        self.assertGreater(build_calls[0]["position"]["z"], terrain_calls[0]["position"]["z"])

    def test_direct_action_imports_attached_fbx_into_uefn(self):
        attachment = {
            "name": "castle wall.fbx",
            "type": "binary",
            "mimeType": "application/octet-stream",
            "content": "data:application/octet-stream;base64," + base64.b64encode(b"fake-fbx-bytes").decode("ascii"),
        }
        calls = []

        def fake_handle_tool_call(name, arguments):
            calls.append((name, arguments))
            return {
                "success": True,
                "result": {
                    "result": {
                        "dest_path": "/Game/CodexImports/20260324/castle_wall/Meshes",
                        "records": [{
                            "source_file": "C:/runtime/castle wall.fbx",
                            "mesh_paths": ["/Game/CodexImports/20260324/castle_wall/Meshes/castle_wall"],
                            "material_paths": ["/Game/CodexImports/20260324/castle_wall/Meshes/M_castle_wall"],
                            "texture_paths": ["/Game/CodexImports/20260324/castle_wall/Meshes/T_castle_wall_D"],
                        }],
                        "mesh_paths": ["/Game/CodexImports/20260324/castle_wall/Meshes/castle_wall"],
                        "material_paths": ["/Game/CodexImports/20260324/castle_wall/Meshes/M_castle_wall"],
                        "texture_paths": ["/Game/CodexImports/20260324/castle_wall/Meshes/T_castle_wall_D"],
                    }
                },
            }

        with patch.object(server, "discover_uefn_listener_port", return_value=8765), \
             patch.object(server, "_handle_tool_call", side_effect=fake_handle_tool_call):
            result = server._maybe_execute_direct_action("import this model into uefn", [attachment])

        self.assertIsNotNone(result)
        self.assertIn("Imported 1 model", result["reply"])
        self.assertIn("source materials and textures", result["reply"])
        self.assertEqual(calls[0][0], "execute_python_in_uefn")
        self.assertIn("import_materials = True", calls[0][1]["code"])
        self.assertIn("/Game/CodexImports/", calls[0][1]["code"])

    def test_direct_action_imports_zipped_fbx_and_places_it_along_terrain_curve(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("Meshes/Rock_A.fbx", b"rock-a")
            zf.writestr("Meshes/Rock_B.fbx", b"rock-b")
        attachment = {
            "name": "terrain_models.zip",
            "type": "binary",
            "mimeType": "application/zip",
            "content": "data:application/zip;base64," + base64.b64encode(zip_buffer.getvalue()).decode("ascii"),
        }
        calls = []

        def fake_handle_tool_call(name, arguments):
            calls.append((name, arguments))
            return {
                "success": True,
                "result": {
                    "result": {
                        "dest_path": "/Game/CodexImports/20260324/ImportedBatch/Meshes",
                        "records": [
                            {
                                "source_file": "C:/runtime/Rock_A.fbx",
                                "mesh_paths": ["/Game/CodexImports/20260324/ImportedBatch/Meshes/Rock_A"],
                                "material_paths": [],
                                "texture_paths": [],
                            },
                            {
                                "source_file": "C:/runtime/Rock_B.fbx",
                                "mesh_paths": ["/Game/CodexImports/20260324/ImportedBatch/Meshes/Rock_B"],
                                "material_paths": [],
                                "texture_paths": [],
                            },
                        ],
                        "mesh_paths": [
                            "/Game/CodexImports/20260324/ImportedBatch/Meshes/Rock_A",
                            "/Game/CodexImports/20260324/ImportedBatch/Meshes/Rock_B",
                        ],
                        "material_paths": [],
                        "texture_paths": [],
                    }
                },
            }

        def fake_execute_tool(tool_name, params):
            calls.append((tool_name, params))
            return {"success": True, "result": {"status": "ok", "placed": 6}}

        with patch.object(server, "discover_uefn_listener_port", return_value=8765), \
             patch.object(server, "_handle_tool_call", side_effect=fake_handle_tool_call), \
             patch.object(server.tool_registry, "execute_tool", side_effect=fake_execute_tool):
            result = server._maybe_execute_direct_action(
                "import these models and place them along the terrain spline",
                [attachment],
            )

        self.assertIsNotNone(result)
        self.assertIn("ground snap pass", result["reply"])
        execute_calls = [call for call in calls if call[0] == "execute_python_in_uefn"]
        self.assertGreaterEqual(len(execute_calls), 2)
        self.assertIn("snap_objects_to_floor()", execute_calls[-1][1]["code"])

    def test_tool_search_boosts_import_and_spline_tools_for_model_curve_queries(self):
        results = server.tool_registry.search_tools("import fbx model along terrain spline curve")
        top_ids = [tool["id"] for tool in results[:8]]
        self.assertIn("import_fbx", top_ids)
        self.assertTrue(any(tool_id in top_ids for tool_id in ("spline_place_props", "scatter_road_edge")))


class TerrainGenerationTests(unittest.TestCase):
    def test_resolve_terrain_tile_grid_prefers_long_strip_layout(self):
        self.assertEqual(server._resolve_terrain_tile_grid(12000, 2400, 6), (6, 1))
        self.assertEqual(server._resolve_terrain_tile_grid(2400, 12000, 6), (1, 6))

    def test_flat_terrain_spec_uses_plane_surface_and_foundation_fill(self):
        spec = server._build_terrain_piece_specs(
            terrain_type="flat",
            size_x=6000,
            size_y=2000,
            height=120,
            elevation=300,
            label="Terrain_Test",
            material_name="grass",
            material_path="/Game/Grass",
            subdivisions=4,
        )

        top_pieces = [piece for piece in spec["pieces"] if piece["mesh_path"] == "/Engine/BasicShapes/Plane"]
        foundation_pieces = [piece for piece in spec["pieces"] if "Foundation" in piece["label"]]
        layer_pieces = [piece for piece in spec["pieces"] if "_Layer_" in piece["label"]]

        self.assertEqual(spec["grid"], {"x": 4, "y": 1})
        self.assertGreaterEqual(len(top_pieces), 4)
        self.assertEqual(len(foundation_pieces), 1)
        self.assertEqual(foundation_pieces[0]["material_path"], server._get_material_path("dirt"))
        self.assertTrue(any(piece["label"].startswith("Terrain_Test_Top") for piece in top_pieces))
        self.assertGreaterEqual(len(layer_pieces), 2)
        self.assertGreaterEqual(len(spec["material_layers"]), 2)
        self.assertIn("lush", spec["biome"])

    def test_slope_terrain_spec_uses_ramped_surface_and_progressive_fill(self):
        spec = server._build_terrain_piece_specs(
            terrain_type="slope",
            size_x=9000,
            size_y=2400,
            height=0,
            elevation=600,
            label="Terrain_Slope",
            material_name="rock",
            material_path="/Game/Rock",
            subdivisions=3,
        )

        ramp_pieces = [piece for piece in spec["pieces"] if piece["label"] == "Terrain_Slope_SlopeSurface"]
        fill_pieces = [piece for piece in spec["pieces"] if "_Fill_" in piece["label"]]

        self.assertEqual(len(ramp_pieces), 1)
        self.assertNotEqual(ramp_pieces[0]["pitch"], 0.0)
        self.assertEqual(ramp_pieces[0]["roll"], 0.0)
        self.assertGreaterEqual(len(fill_pieces), 2)
        self.assertTrue(all(piece["mesh_path"] == "/Engine/BasicShapes/Cube" for piece in fill_pieces))

    def test_ridge_terrain_spec_uses_sloped_shoulders_and_continuous_ridge_top(self):
        spec = server._build_terrain_piece_specs(
            terrain_type="ridge",
            size_x=12000,
            size_y=2400,
            height=80,
            elevation=500,
            label="Terrain_Ridge",
            material_name="terrain",
            material_path="/Game/Terrain",
            subdivisions=1,
        )

        shoulders = [piece for piece in spec["pieces"] if "Shoulder" in piece["label"] and "Layer" not in piece["label"]]
        ridge_top = [piece for piece in spec["pieces"] if piece["label"] == "Terrain_Ridge_RidgeTop"]
        shoulder_layers = [piece for piece in spec["pieces"] if "Shoulder" in piece["label"] and "Layer" in piece["label"]]

        self.assertTrue(spec["continuous"])
        self.assertEqual(len(shoulders), 2)
        self.assertTrue(all(piece["mesh_path"] == "/Engine/BasicShapes/Plane" for piece in shoulders))
        self.assertTrue(any(abs(piece["roll"]) > 0.1 or abs(piece["pitch"]) > 0.1 for piece in shoulders))
        expected_edge_path = server._get_material_path(server._terrain_edge_material_name("terrain"))
        self.assertTrue(all(piece["material_path"] == expected_edge_path for piece in shoulders))
        self.assertEqual(shoulder_layers, [])
        self.assertEqual(len(ridge_top), 1)
        self.assertEqual(ridge_top[0]["mesh_path"], "/Engine/BasicShapes/Plane")

    def test_environment_plan_selects_biome_matched_assets(self):
        profile = server._terrain_biome_profile("grass", "ridge")
        assets = [
            "/Game/Meshes/Nature/SM_PineTall_01",
            "/Game/Meshes/Nature/SM_BoulderLarge_01",
            "/Game/Meshes/Nature/SM_BushDense_01",
            "/Game/Meshes/Nature/SM_Fern_01",
        ]

        plan = server._build_terrain_environment_plan(
            label="Terrain_Ridge",
            material_name="grass",
            terrain_type="ridge",
            px=0.0,
            py=0.0,
            pz=0.0,
            size_x=12000.0,
            size_y=2400.0,
            top_z=300.0,
            decoration_presets=profile["decoration_presets"],
            available_assets=assets,
        )

        self.assertIn("trees", plan["selected_assets"])
        self.assertIn("rocks", plan["selected_assets"])
        self.assertTrue(any(op["tool"] == "scatter_along_path" for op in plan["operations"]))
        self.assertTrue(any(op["category"] == "shrubs" for op in plan["operations"]))
        self.assertFalse(any(op["category"] == "trees" for op in plan["operations"]))

    def test_scene_context_adjusts_environment_scale_and_density(self):
        presets = [
            {"category": "trees", "count": 10, "radius_scale": 0.46, "min_separation": 850.0, "scale": (0.9, 1.18)},
            {"category": "rocks", "count": 8, "radius_scale": 0.42, "min_separation": 420.0, "scale": (0.82, 1.18)},
        ]
        scene_context = {
            "counts": {"trees": 8, "structures": 12, "roads": 2},
            "scale_means": {"trees": 1.65, "rocks": 1.25},
            "total_nearby": 28,
        }

        adjusted = server._apply_scene_context_to_decoration_presets(
            presets,
            scene_context,
            size_x=3200.0,
            size_y=2200.0,
            terrain_type="flat",
        )

        tree_preset = next(item for item in adjusted if item["category"] == "trees")
        rock_preset = next(item for item in adjusted if item["category"] == "rocks")

        self.assertLess(tree_preset["count"], 10)
        self.assertGreater(tree_preset["scale"][0], 1.2)
        self.assertGreater(rock_preset["scale"][0], 1.0)
        self.assertLess(tree_preset["radius_scale"], 0.46)

    def test_apply_scene_context_keeps_narrow_ridge_dressing_proportional(self):
        presets = [
            {"category": "trees", "count": 8, "radius_scale": 0.46, "min_separation": 900.0, "scale": (0.95, 1.2)},
            {"category": "rocks", "count": 7, "radius_scale": 0.38, "min_separation": 360.0, "scale": (0.82, 1.2)},
            {"category": "shrubs", "count": 10, "radius_scale": 0.3, "min_separation": 240.0, "scale": (0.7, 1.0)},
        ]
        adjusted = server._apply_scene_context_to_decoration_presets(
            presets,
            {"counts": {}, "scale_means": {}, "total_nearby": 0},
            size_x=12000.0,
            size_y=2400.0,
            terrain_type="ridge",
        )

        tree_preset = next(item for item in adjusted if item["category"] == "trees")
        rock_preset = next(item for item in adjusted if item["category"] == "rocks")
        shrub_preset = next(item for item in adjusted if item["category"] == "shrubs")

        self.assertEqual(tree_preset["count"], 0)
        self.assertLessEqual(rock_preset["count"], 4)
        self.assertLessEqual(rock_preset["scale"][1], 0.84)
        self.assertLessEqual(rock_preset["radius_scale"], 0.14)
        self.assertLessEqual(shrub_preset["count"], 5)
        self.assertLessEqual(shrub_preset["scale"][1], 0.74)
        self.assertLessEqual(shrub_preset["radius_scale"], 0.12)

    def test_environment_plan_uses_nearby_scene_context(self):
        profile = server._terrain_biome_profile("grass", "flat")
        assets = [
            "/Game/Meshes/Nature/SM_PineTall_01",
            "/Game/Meshes/Nature/SM_BoulderLarge_01",
            "/Game/Meshes/Nature/SM_BushDense_01",
        ]
        fake_scene = {
            "counts": {"trees": 6, "structures": 5},
            "scale_means": {"trees": 1.45, "rocks": 1.18},
            "total_nearby": 18,
        }

        with patch.object(server, "_collect_nearby_environment_context", return_value=fake_scene):
            plan = server._build_terrain_environment_plan(
                label="Terrain_Context",
                material_name="grass",
                terrain_type="flat",
                px=100.0,
                py=200.0,
                pz=0.0,
                size_x=4000.0,
                size_y=3200.0,
                top_z=120.0,
                decoration_presets=profile["decoration_presets"],
                available_assets=assets,
            )

        self.assertEqual(plan["scene_context"], fake_scene)
        tree_ops = [op for op in plan["operations"] if op["category"] == "trees"]
        self.assertTrue(tree_ops)
        self.assertGreaterEqual(tree_ops[0]["scale_min"], 1.1)

    def test_environment_plan_skips_tree_scatter_on_narrow_ridge(self):
        profile = server._terrain_biome_profile("grass", "ridge")
        assets = [
            "/Game/Meshes/Nature/SM_PineTall_01",
            "/Game/Meshes/Nature/SM_BoulderLarge_01",
            "/Game/Meshes/Nature/SM_BushDense_01",
        ]

        plan = server._build_terrain_environment_plan(
            label="Terrain_SkinnyRidge",
            material_name="grass",
            terrain_type="ridge",
            px=0.0,
            py=0.0,
            pz=0.0,
            size_x=12000.0,
            size_y=2400.0,
            top_z=300.0,
            decoration_presets=profile["decoration_presets"],
            available_assets=assets,
        )

        self.assertFalse(any(op["category"] == "trees" for op in plan["operations"]))
        rock_ops = [op for op in plan["operations"] if op["category"] == "rocks"]
        self.assertTrue(rock_ops)
        self.assertTrue(all(op["spread"] <= 288.0 for op in rock_ops if op["tool"] == "scatter_along_path"))
        self.assertTrue(all(op["scale_max"] <= 0.84 for op in rock_ops))

    def test_execute_terrain_control_reports_layers_and_environment_details(self):
        scatter_calls = []

        def fake_post_command(port, command, payload, timeout=30.0):
            self.assertEqual(command, "execute_python")
            self.assertIn("spawn_actor_from_class", payload["code"])
            return {"success": True, "result": {"status": "ok"}}

        def fake_execute_tool(name, params):
            scatter_calls.append((name, params))
            count = params.get("count") or (len(params.get("path_points") or []) * int(params.get("count_per_point") or 0))
            return {"success": True, "result": {"placed": count}}

        with patch.object(server, "discover_uefn_listener_port", return_value=8765), \
             patch.object(server, "mcp_listener_post_command", side_effect=fake_post_command), \
             patch.object(server, "_list_project_static_mesh_assets", return_value=[
                 "/Game/Meshes/Nature/SM_PineTall_01",
                 "/Game/Meshes/Nature/SM_BoulderLarge_01",
                 "/Game/Meshes/Nature/SM_BushDense_01",
             ]), \
             patch.object(server.tool_registry, "execute_tool", side_effect=fake_execute_tool):
            result = server._execute_terrain_control({
                "action": "terrain",
                "operation": "create",
                "terrain_type": "ridge",
                "position": {"x": 0, "y": 0, "z": 0},
                "size": {"x": 12000, "y": 2400},
                "material": "grass",
                "elevation": 450,
                "decorate": True,
                "label": "Terrain_RidgeTest",
            })

        self.assertTrue(result["success"])
        self.assertGreaterEqual(len(result["details"]["material_layers"]), 2)
        self.assertTrue(result["details"]["environment_assets"])
        self.assertTrue(scatter_calls)
        self.assertIn("layered materials", result["summary"])


if __name__ == "__main__":
    unittest.main()
