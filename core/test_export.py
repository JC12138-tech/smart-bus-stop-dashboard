import pytest

@pytest.mark.django_db
def test_export_xlsx(client):
    resp = client.get("/export.xlsx")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
