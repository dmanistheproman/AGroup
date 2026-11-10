"""Business rules that must hold for any data set (X-05): run on generated data with any seed."""
import sqlite3
from contextlib import closing

import pytest

from backend.data_checks import check_database
from backend.data_generator import generate


@pytest.fixture(scope="module")
def database(tmp_path_factory):
    path = tmp_path_factory.mktemp("checks") / "data.sqlite3"
    generate(path, seed=2026, scale=0.1, log=lambda *_: None)
    return path


def corrupt(path, tmp_path, sql, *args):
    copy = tmp_path / "broken.sqlite3"
    copy.write_bytes(path.read_bytes())
    with closing(sqlite3.connect(copy)) as connection, connection:
        connection.execute(sql, args)
    return copy


def test_generated_data_keeps_every_rule(database):
    assert check_database(database) == []


@pytest.mark.parametrize("seed", [1, 77])
def test_other_seeds_keep_every_rule(tmp_path, seed):
    path = tmp_path / f"seed-{seed}.sqlite3"
    generate(path, seed=seed, scale=0.05, log=lambda *_: None)
    assert check_database(path) == []


def test_a_merged_ticket_must_point_at_a_live_ticket(database, tmp_path):
    broken = corrupt(database, tmp_path, "UPDATE support_ticket SET merged_into_id = 'TKT-9999' WHERE request_id IN "
                                         "(SELECT request_id FROM request WHERE status = 'MERGED' LIMIT 1)")
    assert any("merged" in p for p in check_database(broken))


def test_an_audited_change_must_be_allowed_by_the_lifecycle(database, tmp_path):
    broken = corrupt(database, tmp_path, "INSERT INTO audit_log VALUES ('LOG-99999', 'user-helpdesk', 'SUPPORT_TICKET', "
                                         "'TKT-1001', 'STATUS_CHANGED', 'CLOSED', 'OPEN', NULL, '2026-11-08T00:00:00')")
    assert any("CLOSED -> OPEN" in p for p in check_database(broken))


def test_a_change_that_needs_a_reason_must_have_one(database, tmp_path):
    broken = corrupt(database, tmp_path, "UPDATE audit_log SET reason = NULL WHERE to_status = 'ESCALATED'")
    assert any("reason" in p for p in check_database(broken))


def test_favourites_need_an_existing_project(database, tmp_path):
    broken = corrupt(database, tmp_path, "INSERT INTO favourite VALUES ('FAV-99999', 'CUS-101', 9999, '2026-11-08')")
    assert any("favourite" in p.lower() for p in check_database(broken))


def test_notifications_need_an_existing_recipient(database, tmp_path):
    broken = corrupt(database, tmp_path, "UPDATE notification SET recipient_id = 'nobody' WHERE notification_id = "
                                         "(SELECT MIN(notification_id) FROM notification)")
    assert any("recipient" in p for p in check_database(broken))


def test_payments_belong_to_accepted_quotations(database, tmp_path):
    broken = corrupt(database, tmp_path, "UPDATE offer SET status = 'DRAFT' WHERE offer_id = 'QT-103'")
    assert any("payment" in p.lower() for p in check_database(broken))


def test_only_participants_write_in_a_conversation(database, tmp_path):
    broken = corrupt(database, tmp_path, "UPDATE message SET author_id = 'user-manager' WHERE thread_id = "
                                         "(SELECT thread_id FROM conversation LIMIT 1)")
    assert any("conversation" in p for p in check_database(broken))


def test_internal_notes_are_written_by_staff(database, tmp_path):
    broken = corrupt(database, tmp_path, "UPDATE internal_note SET author_id = 'CUS-101' WHERE note_id = "
                                         "(SELECT MIN(note_id) FROM internal_note)")
    assert any("note" in p for p in check_database(broken))


def test_a_folder_holds_only_saved_projects_of_its_owner(database, tmp_path):
    broken = corrupt(database, tmp_path, "INSERT INTO collection_item(item_id, collection_id, project_id, item_type) "
                                         "SELECT 'CI-99999', collection_id, 9999, 'PROJECT' FROM collection "
                                         "WHERE kind = 'FOLDER' LIMIT 1")
    assert any("folder" in p.lower() for p in check_database(broken))


@pytest.mark.parametrize("target_type, change", [("ENQUIRY", "'DECLINED', 'CONFIRMED'"),
                                                 ("VERIFICATION_REQUEST", "'APPROVED', 'REJECTED'"),
                                                 ("DESIGN_PROPOSAL", "'UNDER_REVIEW', 'DRAFT'")])
def test_enquiry_verification_and_proposal_changes_follow_their_lifecycles(database, tmp_path, target_type, change):
    broken = corrupt(database, tmp_path, f"INSERT INTO audit_log VALUES ('LOG-99998', 'user-admin', '{target_type}', "
                                         f"'X-1', 'STATUS_CHANGED', {change}, 'test', '2026-11-08T00:00:00')")
    assert any(target_type in p and "not an allowed change" in p for p in check_database(broken))


def test_no_activity_before_a_project_is_published(database, tmp_path):
    broken = corrupt(database, tmp_path, "INSERT INTO activities SELECT 'ACT-EARLY', CAST(substr(target_id, 5) AS INTEGER), "
                                         "'VIEW', '2000-01-01T00:00:00.000000Z', 'test' FROM audit_log "
                                         "WHERE target_type = 'PROJECT' AND to_status = 'PUBLISHED' LIMIT 1")
    assert any("before the project was first published" in p for p in check_database(broken))
