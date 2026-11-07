"""ID-05 边界回归：HTTP 层真实 multipart 上传——单元测试的 fake 说不出的那类缝隙。
本测试走真实 FileUploadService，会在 uploads/Proposal/ 下写一个小文件，测完即删。"""
import io
import os

from backend import server as portal


def test_create_proposal_with_real_multipart_upload():
    client = portal.create_app().test_client()
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
