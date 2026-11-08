"""ID-05 boundary regression: a real multipart upload through HTTP — the kind of gap a unit-test fake cannot show.
This test uses the real FileUploadService and writes a small file under uploads/Proposal/, deleted afterwards."""
import io
import os

from backend import server as portal


def test_create_proposal_with_real_multipart_upload():
    client = portal.create_app().test_client()
    client.post("/api/auth/login", json={"email": "designer@demo.agroup", "password": "demo"})  # session identity
    res = client.post("/api/proposals", data={
        "title": "Boundary check",
        "client_name": "Alex Tan",
        "description": "Multipart upload through the HTTP boundary.",
        "images": (io.BytesIO(b"\xff\xd8\xff\xe0demo-bytes"), "style-board.jpg"),
    }, content_type="multipart/form-data")
    assert res.status_code == 201, res.get_data(as_text=True)
    proposal = res.get_json()["proposal"]
    assert proposal["attachments"] and proposal["attachments"][0].endswith("style-board.jpg")
    try:
        os.remove(proposal["attachments"][0])
    except OSError:
        pass
