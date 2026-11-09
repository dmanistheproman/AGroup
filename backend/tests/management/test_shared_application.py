"""Regression coverage for management in the group's normal application."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json

import pytest

from backend.entities.project_category import ProjectCategory
from backend.repositories.project_repo import ProjectRepo
from backend.server import create_app
from backend.services.management_rules import SINGAPORE


@pytest.fixture
def app(tmp_path):
    return create_app(config={"TESTING": True, "SECRET_KEY": "integration-test",
                              "DATABASE": str(tmp_path / "shared.sqlite3"), "SEED_DEMO": False})


def signed_in(app, email):
    client = app.test_client()
    assert client.post('/api/auth/login', json={"email": email, "password": "demo"}).status_code == 200
    return client


def send(client, path, values, method='POST'):
    token = client.get('/api/session').json['csrfToken']
    return client.open(path, method=method, json=values, headers={'X-CSRF-Token': token})


def category(client, name):
    result = send(client, '/api/management/categories', {'name': name})
    assert result.status_code == 201
    return result.json['category']


def project(client, category_id, title='Shared project'):
    response = client.post('/api/projects', data={
        'title': title, 'description': 'A project used to check shared category assignments.',
        'category_id': category_id, 'owner_id': 'spoofed-owner', 'firm': 'spoofed-company',
    })
    assert response.status_code == 201, response.json
    return response.json['project']


def test_management_requires_the_manager_role_and_ends_access_on_logout(app):
    assert app.test_client().get('/api/management/categories').status_code == 401
    for email in ('customer@demo.agroup', 'designer@demo.agroup', 'admin@demo.agroup', 'helpdesk@demo.agroup'):
        assert signed_in(app, email).get('/api/management/categories').status_code == 403
    manager = signed_in(app, 'manager@demo.agroup')
    assert manager.get('/api/management/categories').status_code == 200
    manager.post('/api/auth/logout')
    assert manager.get('/api/management/categories').status_code == 401


def test_designer_project_merge_delete_and_restart_share_one_database(app):
    manager = signed_in(app, 'manager@demo.agroup')
    designer = signed_in(app, 'designer@demo.agroup')
    source, target = category(manager, 'Modern Style'), category(manager, 'Modern')
    created = project(designer, source['id'])
    assert created['firm'] == 'Form & Field' and created['owner_id'] == 'user-form-field'
    review = manager.get('/api/management/categories/' + source['id'] + '/projects').json
    assert review['projects'][0]['title'] == created['title']
    merged = send(manager, '/api/management/categories/merge', {
        'sourceId': source['id'], 'targetId': target['id'], 'sourceVersion': 1, 'targetVersion': 1,
    })
    assert merged.status_code == 200 and merged.json['movedCount'] == 1
    assert designer.get('/api/projects').json[0]['category_id'] == target['id']
    available = designer.get('/api/project-categories').json['categories']
    assert [item['id'] for item in available] == [target['id']]
    restarted = create_app(config={'TESTING': True, 'SECRET_KEY': 'test', 'DATABASE': app.config['DATABASE'], 'SEED_DEMO': False})
    retained = signed_in(restarted, 'designer@demo.agroup').get('/api/projects').json
    assert retained[0]['category_id'] == target['id']


def test_archiving_blocks_designer_assignments_even_after_the_form_was_loaded(app):
    manager = signed_in(app, 'manager@demo.agroup')
    designer = signed_in(app, 'designer@demo.agroup')
    source = category(manager, 'Archive me')
    assert designer.get('/api/project-categories').json['categories'][0]['id'] == source['id']
    send(manager, '/api/management/categories/' + source['id'] + '/archive', {'version': 1})
    result = designer.post('/api/projects', data={'title': 'Blocked', 'description': 'Details', 'category_id': source['id']})
    assert result.status_code == 400
    assert designer.get('/api/projects').json == []


def test_activity_is_shared_by_management_reports_and_designer_statistics(app):
    manager = signed_in(app, 'manager@demo.agroup')
    designer = signed_in(app, 'designer@demo.agroup')
    source = category(manager, 'Activity')
    created = project(designer, source['id'])
    project_id = ProjectRepo.database_id(created['id'])
    for event_type in ('VIEW', 'FAVOURITE_ADD', 'ENQUIRY'):
        response = send(manager, '/api/activity', {'projectId': project_id, 'type': event_type, 'eventId': 'shared-event-' + event_type})
        assert response.status_code == 200
    stats = designer.get('/api/statistics').json['projects'][0]
    assert stats['lifetime_views'] == stats['period_views'] == 1
    assert stats['lifetime_favourites'] == stats['period_favourites'] == 1
    today = datetime.now(SINGAPORE).date().isoformat()
    report = send(manager, '/api/management/reports', {'period': 'daily', 'date': today}).json['report']
    assert [row['value'] for row in report['rows']] == [1, 1, 1, 1]


def test_shared_portfolio_restricts_other_designers_and_draft_discovery(app):
    manager = signed_in(app, 'manager@demo.agroup')
    designer = signed_in(app, 'designer@demo.agroup')
    other = signed_in(app, 'commonground@demo.agroup')
    created = project(designer, category(manager, 'Private draft')['id'])
    assert other.get('/api/projects').json == []
    assert other.get('/api/statistics').json['projects'] == []
    assert other.delete('/api/projects/' + created['id'] + '?confirm_impact=true').status_code == 403
    assert app.test_client().get('/api/catalog').json['projects'] == []
    assert designer.delete('/api/projects/' + created['id']).status_code == 200
    assert manager.get('/api/management/categories').json['categories'][0]['count'] == 0


def test_concurrent_reference_allocation_and_category_change_during_save(app):
    store = app.extensions['management_store']
    repo = ProjectRepo(store)
    with ThreadPoolExecutor(max_workers=4) as executor:
        references = list(executor.map(lambda _: repo.next_reference('IDP'), range(12)))
    assert len(set(references)) == 12
    categories = ProjectCategory(store)
    source = categories.create('Race condition', '')
    categories.change_status(source['id'], 1, 'Active', 'Archived')
    with pytest.raises(ValueError, match='not active'):
        repo.save({'id': references[0], 'title': 'Blocked', 'description': 'Details', 'category_id': source['id']})
    assert repo.all() == []


def test_frontend_assets_use_shared_app(app):
    client = app.test_client()
    for path in ('/', '/login.html', '/portal.html', '/js/management.js', '/js/api.js', '/css/management.css'):
        assert client.get(path).status_code == 200
    html = client.get('/portal.html').text
    assert 'js/management.js' in html and 'js/account.js' in html and 'js/icons.js' in html


def test_legacy_project_primary_category_survives_rename_and_merge(app):
    manager = signed_in(app, 'manager@demo.agroup')
    source, target = category(manager, 'Original style'), category(manager, 'Target style')
    secondary = category(manager, 'Alphabetically first')
    store = app.extensions['management_store']
    with store.transaction(write=True) as connection:
        connection.execute('INSERT INTO projects VALUES (?, ?, ?, ?, ?)',
                           (1, 'Existing project', 'Form & Field', json.dumps({'style': 'Original style'}), '2026-11-01T00:00:00Z'))
        for item in (source, target, secondary):
            connection.execute('INSERT INTO assignments VALUES (?, ?, ?)', (1, item['id'], '2026-11-01T00:00:00Z'))
    renamed = send(manager, '/api/management/categories/' + source['id'],
                   {'name': 'Renamed style', 'description': '', 'version': 1}, 'PATCH')
    assert renamed.status_code == 200
    assert manager.get('/api/catalog').json['projects'][0]['style'] == 'Renamed style'
    merged = send(manager, '/api/management/categories/merge', {
        'sourceId': source['id'], 'targetId': target['id'], 'sourceVersion': 2, 'targetVersion': 1,
    })
    assert merged.status_code == 200 and merged.json['duplicatesRemoved'] == 1
    assert manager.get('/api/catalog').json['projects'][0]['style'] == 'Target style'
    assert ProjectRepo(store).get('IDP-001')['category_id'] == target['id']
