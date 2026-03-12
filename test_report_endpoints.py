from datetime import datetime

import httpx
import pytest

from webcrawler.api import main as api_main
from webcrawler.storage.database import Database
from webcrawler.storage.models import CrawledURL, LinkData


@pytest.mark.asyncio
async def test_named_reports_endpoints(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "reports_api.db"))
    monkeypatch.setattr(api_main, "database", db)

    try:
        session = db.create_session(start_url="https://example.com")
        sid = session.session_id

        db.save_url(
            sid,
            CrawledURL(
                url="https://example.com/",
                content_type="text/html; charset=utf-8",
                status_code=200,
                link_score=12.5,
                crawled_at=datetime.now(),
            ),
        )
        db.save_url(
            sid,
            CrawledURL(
                url="https://example.com/missing",
                content_type="text/html; charset=utf-8",
                status_code=404,
                link_score=1.0,
                crawled_at=datetime.now(),
            ),
        )
        db.save_link(
            sid,
            LinkData(
                source_url="https://example.com/",
                target_url="https://external.example.org/",
                is_internal=False,
            ),
        )

        transport = httpx.ASGITransport(app=api_main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            catalog = await client.get(f"/reports/{sid}")
            assert catalog.status_code == 200
            payload = catalog.json()
            assert payload["total_reports"] == 16

            response_codes = await client.get(f"/reports/{sid}/response_codes")
            assert response_codes.status_code == 200
            summary = response_codes.json()["data"]["summary"]
            assert summary["2xx"] == 1
            assert summary["4xx"] == 1

            external_all = await client.get(f"/reports/{sid}/external_all")
            assert external_all.status_code == 200
            assert external_all.json()["data"]["total"] == 1

            link_score = await client.get(f"/reports/{sid}/link_score")
            assert link_score.status_code == 200
            rows = link_score.json()["data"]["rows"]
            assert rows[0]["url"] == "https://example.com/"

            csv_export = await client.get(f"/reports/{sid}/response_codes/csv")
            assert csv_export.status_code == 200
            assert csv_export.headers["content-type"].startswith("text/csv")
            assert "url,status_code,status_text" in csv_export.text

            json_export = await client.get(f"/reports/{sid}/response_codes/json")
            assert json_export.status_code == 200
            assert json_export.headers["content-type"].startswith("application/json")
            json_payload = json_export.json()
            assert json_payload["summary"]["2xx"] == 1
            assert json_payload["summary"]["4xx"] == 1

            xlsx_export = await client.get(f"/reports/{sid}/response_codes/xlsx")
            assert xlsx_export.status_code in (200, 501)
            if xlsx_export.status_code == 200:
                assert xlsx_export.headers["content-type"].startswith(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                assert len(xlsx_export.content) > 100
            else:
                assert "openpyxl" in xlsx_export.json()["detail"].lower()

            issues_csv = await client.get(f"/reports/{sid}/issues_report/csv")
            assert issues_csv.status_code == 200
            assert "category,url,issue,severity" in issues_csv.text
            assert "Missing title tag" in issues_csv.text

            unknown = await client.get(f"/reports/{sid}/unknown_report")
            assert unknown.status_code == 404
    finally:
        db.close()
