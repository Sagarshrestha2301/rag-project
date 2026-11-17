"""Verify the Step 7 task 1 routes and the existing chat response shape.

Usage:
    .venv\\Scripts\\python.exe -m ui.test_server
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from urllib.parse import quote

from fastapi.testclient import TestClient

from ui import server


class ServerTests(unittest.TestCase):
    def test_existing_static_and_pdf_routes_remain_available(self) -> None:
        name = server.INDEX["docs"][0]["doc"]
        with TestClient(server.app) as client:
            page = client.get("/")
            script = client.get("/static/app.js")
            config = client.get("/api/config")
            docs = client.get("/api/docs")
            pdf = client.get(f"/pdf/{quote(name)}")
            missing = client.get("/pdf/not-a-corpus-document.pdf")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(script.status_code, 200)
        self.assertEqual(config.status_code, 200)
        self.assertEqual(docs.status_code, 200)
        self.assertIn("model", config.json())
        self.assertIn("docs", docs.json())
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.headers["content-type"], "application/pdf")
        self.assertEqual(missing.status_code, 404)

    def test_chat_calls_generation_answer_with_prior_history(self) -> None:
        page = server.INDEX["pages"][0]
        record = {
            "answer": "The figure is 540 mm [1].",
            "status": "verified",
            "seconds": 1.25,
            "timing": {"prompt_tokens": 12, "answer_tokens": 4},
            "cached": False,
            "search_question": "and in 1990?",
            "passages": [{
                "n": 1, "doc": page["doc"], "page": page["page"],
                "label": page["label"], "score": 2.5,
            }],
        }
        messages = [
            {"role": "user", "content": "What was the rainfall?"},
            {"role": "assistant", "content": "The report says 540 mm."},
            {"role": "user", "content": "and in 1990?"},
        ]

        with patch.object(server.generation, "answer", return_value=record) as answer:
            with TestClient(server.app) as client:
                response = client.post(
                    "/api/chat", json={"messages": messages, "temperature": 0.0})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/x-ndjson")
        event = json.loads(response.text.strip())
        self.assertEqual(event["message"]["content"], record["answer"])
        self.assertTrue(event["done"])
        self.assertEqual(event["status"], "verified")
        self.assertEqual(event["sources"][0]["n"], 1)
        self.assertEqual(event["sources"][0]["doc"], page["doc"])

        answer.assert_called_once()
        self.assertEqual(answer.call_args.args, ("and in 1990?",))
        self.assertIs(answer.call_args.kwargs["index"], server.INDEX)
        self.assertEqual(answer.call_args.kwargs["history"], messages[:2])
        self.assertEqual(answer.call_args.kwargs["temperature"], 0.0)


if __name__ == "__main__":
    unittest.main()
