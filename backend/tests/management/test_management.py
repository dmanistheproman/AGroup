"""Regression checks for category integrity and the fourteen management stories."""

import csv
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from backend.server import create_app
from backend.controllers.management.merge_categories_controller import MergeCategoriesController
from backend.services.management_rules import BusinessError
from backend.entities.report_period import Period
from backend.entities.project_category import ProjectCategory
from backend.entities.project_category_assignment import ProjectCategoryAssignment
from backend.storage import SQLiteStore


class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.config = {"TESTING": True, "SECRET_KEY": "test-only", "SEED_DEMO": False,
                       "DATABASE": str(Path(self.folder.name) / "test.sqlite3")}
        self.app = create_app(config=self.config)
        self.client = self.app.test_client()
        self.client.post('/api/auth/login', json={'email': 'manager@demo.agroup', 'password': 'demo'})
        self.token = self.client.get('/api/session').json['csrfToken']
        self.store = self.app.extensions['management_store']
        self.entity = ProjectCategory(self.store)
        self.source = self.entity.create('Modern Style', 'Source category')
        self.target = self.entity.create('Modern', 'Target category')
        with self.store.transaction(write=True) as connection:
            dates = ['2026-10-01T00:00:00.000000Z', '2026-11-03T16:00:00.000000Z',
                     '2026-11-04T15:59:59.000000Z', '2026-11-04T16:00:00.000000Z']
            for project_id, created in enumerate(dates, 1):
                details = json.dumps({'style': 'Modern', 'image': 'living', 'type': 'HDB', 'location': 'Tampines'})
                connection.execute('INSERT INTO projects VALUES (?, ?, ?, ?, ?)',
                                   (project_id, f'Project {project_id}', 'Test Studio', details, created))
            for project_id, category_id in [(1, self.source['id']), (2, self.source['id']),
                                             (2, self.target['id']), (3, self.target['id'])]:
                ProjectCategoryAssignment.assign(connection, project_id, category_id)
            events = [('old-view', 1, 'VIEW', '2026-11-03T15:59:59.000000Z'),
                      ('start-view', 1, 'VIEW', '2026-11-03T16:00:00.000000Z'),
                      ('end-view', 2, 'VIEW', '2026-11-04T15:59:59.000000Z'),
                      ('excluded-view', 3, 'VIEW', '2026-11-04T16:00:00.000000Z'),
                      ('favourite', 2, 'FAVOURITE_ADD', '2026-11-04T00:00:00.000000Z'),
                      ('enquiry', 3, 'ENQUIRY', '2026-11-04T01:00:00.000000Z')]
            connection.executemany("INSERT INTO activities VALUES (?, ?, ?, ?, 'sample')", events)

    def send(self, path, values, method='POST'):
        return self.client.open('/api/management' + path, method=method, json=values,
                                headers={'X-CSRF-Token': self.token})

    def category(self, category_id):
        return next(item for item in self.client.get('/api/management/categories').json['categories']
                    if item['id'] == category_id)

    def merge(self):
        return self.send('/categories/merge', {'sourceId': self.source['id'], 'targetId': self.target['id'],
                                              'sourceVersion': 1, 'targetVersion': 1})

    def merge_state(self):
        state = {}
        with self.store.transaction() as connection:
            for table in ['categories', 'assignments', 'projects', 'activities', 'audit', 'reports']:
                rows = connection.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()
                state[table] = [dict(row) for row in rows]
        return state

    def report(self, **selection):
        response = self.send('/reports', {'period': 'daily', 'date': '2026-11-04', **selection})
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['report']

    def test_list_search_and_usage_are_based_on_assignments(self):
        categories = self.client.get('/api/management/categories?search=MODERN%20ST').json['categories']
        self.assertEqual([item['name'] for item in categories], ['Modern Style'])
        self.assertEqual(categories[0]['count'], 2)
        self.assertEqual(self.client.get('/api/management/categories?search=missing').json['categories'], [])
        usage = self.client.get('/api/management/categories/usage').json['categories']
        source = next(item for item in usage if item['id'] == self.source['id'])
        self.assertEqual((source['projects'], source['views'], source['favourites'], source['enquiries']), (2, 3, 1, 0))

    def test_creation_normalizes_names_and_rejects_duplicates(self):
        response = self.send('/categories', {'name': '  MODERN  ', 'description': ''})
        self.assertEqual(response.status_code, 409)
        response = self.send('/categories', {'name': '　Ｍｏｄｅｒｎ　', 'description': ''})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.send('/categories', {'name': ' ', 'description': ''}).status_code, 400)
        self.assertEqual(self.send('/categories', {'name': 'Industrial', 'description': 'Raw finishes'}).status_code, 201)

    def test_edit_rejects_stale_versions_and_duplicate_names(self):
        path = '/categories/' + self.source['id']
        self.assertEqual(self.send(path, {'name': 'Modern', 'description': '', 'version': 1}, 'PATCH').status_code, 409)
        update = self.send(path, {'name': 'Modern living', 'description': 'Updated', 'version': 1}, 'PATCH')
        self.assertEqual(update.json['category']['version'], 2)
        self.assertEqual(self.send(path, {'name': 'Stale edit', 'description': '', 'version': 1}, 'PATCH').status_code, 409)
        self.assertEqual(self.category(self.source['id'])['name'], 'Modern living')

    def test_archive_retains_links_blocks_new_assignments_and_restore_clears_feature(self):
        path = '/categories/' + self.source['id']
        archived = self.send(path + '/archive', {'version': 1}).json['category']
        self.assertEqual(archived['status'], 'Archived')
        self.assertEqual(self.category(self.source['id'])['count'], 2)
        with self.assertRaises(BusinessError):
            with self.store.transaction(write=True) as connection:
                ProjectCategoryAssignment.assign(connection, 4, self.source['id'])
        restored = self.send(path + '/restore', {'version': 2}).json['category']
        self.assertEqual(restored['status'], 'Active')

    def test_featured_categories_are_available_to_customer_catalog(self):
        self.send('/categories/' + self.target['id'] + '/feature', {'featured': True, 'version': 1})
        catalog = self.client.get('/api/catalog').json
        featured = [item['id'] for item in catalog['categories'] if item['featured']]
        self.assertEqual(featured, [self.target['id']])
        self.assertEqual(catalog['projects'][1]['categoryNames'], ['Modern', 'Modern Style'])

    def test_merge_deduplicates_links_and_preserves_projects_and_activity(self):
        before = self.report()['rows']
        self.entity.set_featured(self.source['id'], True, 1)
        target_before = self.entity.set_featured(self.target['id'], True, 1)
        original_records = self.merge_state()
        result = self.send('/categories/merge', {'sourceId': self.source['id'], 'targetId': self.target['id'],
                                               'sourceVersion': 2, 'targetVersion': 2})
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json['movedCount'], 2)
        self.assertEqual(result.json['duplicatesRemoved'], 1)
        self.assertEqual(self.category(self.source['id'])['status'], 'Merged')
        self.assertEqual(self.category(self.source['id'])['count'], 0)
        self.assertEqual(self.category(self.target['id'])['count'], 3)
        source_after = self.category(self.source['id'])
        self.assertEqual(source_after['merged_into_id'], self.target['id'])
        self.assertFalse(source_after['featured'])
        for field in ['name', 'description', 'featured', 'status']:
            self.assertEqual(result.json['target'][field], target_before[field])
        merged_records = self.merge_state()
        for table in ['projects', 'activities', 'reports']:
            self.assertEqual(merged_records[table], original_records[table])
        self.assertEqual(self.report()['rows'], before)
        review = self.client.get('/api/management/categories/' + self.source['id'] + '/projects').json
        self.assertEqual(review['projects'], [])
        self.assertEqual(review['target']['id'], self.target['id'])
        self.assertEqual(self.merge().status_code, 409)

    def test_merge_rolls_back_assignment_changes_if_source_update_fails(self):
        with self.store.transaction(write=True) as connection:
            connection.execute("""CREATE TRIGGER simulated_failure BEFORE UPDATE OF status ON categories
                WHEN NEW.status = 'Merged' BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            MergeCategoriesController(ProjectCategory(self.store)).merge_categories(self.source['id'], self.target['id'], 1, 1)
        self.assertEqual(self.category(self.source['id'])['count'], 2)
        self.assertEqual(self.category(self.target['id'])['count'], 2)
        self.assertEqual(self.category(self.source['id'])['status'], 'Active')

    def test_merge_messages_follow_the_sequence_diagram(self):
        controller = MergeCategoriesController(ProjectCategory(self.store))
        messages = Mock()
        with (
            patch.object(controller.categories, 'find_pair', wraps=controller.categories.find_pair) as find_pair,
            patch.object(controller.categories, 'merge_into', wraps=controller.categories.merge_into) as merge_into,
            patch.object(ProjectCategoryAssignment, 'reassign', wraps=ProjectCategoryAssignment.reassign) as reassign,
            patch.object(controller.categories, '_mark_merged', wraps=controller.categories._mark_merged) as mark_merged,
        ):
            messages.attach_mock(find_pair, 'find_pair')
            messages.attach_mock(merge_into, 'merge_into')
            messages.attach_mock(reassign, 'reassign')
            messages.attach_mock(mark_merged, 'mark_merged')
            result = controller.merge_categories(self.source['id'], self.target['id'], 1, 1)
        self.assertEqual([message[0] for message in messages.mock_calls],
                         ['find_pair', 'merge_into', 'reassign', 'mark_merged'])
        connections = [message.args[0] for message in messages.mock_calls]
        self.assertTrue(all(connection is connections[0] for connection in connections))
        self.assertEqual(result['target']['id'], self.target['id'])
        self.assertEqual(result['movedCount'], 2)
        self.assertEqual(self.category(self.target['id'])['count'], 3)

    def test_invalid_merge_paths_stop_before_entity_mutation(self):
        archived = self.entity.create('Archived choice', '')
        self.entity.change_status(archived['id'], 1, 'Active', 'Archived')
        controller = MergeCategoriesController(ProjectCategory(self.store))
        selections = [
            (self.source['id'], self.source['id'], 1, 1),
            (archived['id'], self.target['id'], 2, 1),
            (self.source['id'], archived['id'], 1, 2),
            ('missing-source', self.target['id'], 1, 1),
            (self.source['id'], 'missing-target', 1, 1),
            (self.source['id'], self.target['id'], 0, 1),
            (self.source['id'], self.target['id'], 1, 0),
        ]
        for selection in selections:
            with self.subTest(selection=selection):
                before = self.merge_state()
                with patch.object(controller.categories, 'merge_into', wraps=controller.categories.merge_into) as merge_into:
                    with self.assertRaises(BusinessError):
                        controller.merge_categories(*selection)
                    merge_into.assert_not_called()
                self.assertEqual(self.merge_state(), before)

    def test_merge_api_rejects_missing_or_malformed_selections(self):
        for source_id, target_id in [(None, self.target['id']), (self.source['id'], None),
                                     ([], self.target['id']), (self.source['id'], {}), ('', self.target['id'])]:
            with self.subTest(source=source_id, target=target_id):
                before = self.merge_state()
                response = self.send('/categories/merge', {'sourceId': source_id, 'targetId': target_id,
                                                          'sourceVersion': 1, 'targetVersion': 1})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.merge_state(), before)

    def test_merge_api_rolls_back_after_source_was_marked(self):
        with self.store.transaction(write=True) as connection:
            connection.execute(f"""CREATE TRIGGER fail_target_update BEFORE UPDATE OF version ON categories
                WHEN NEW.id = '{self.target['id']}' AND NEW.version > OLD.version
                BEGIN SELECT RAISE(ABORT, 'simulated target failure'); END""")
        before = self.merge_state()
        with self.assertLogs(self.app.logger, level='ERROR'):
            response = self.merge()
        self.assertEqual(response.status_code, 503)
        self.assertIn('error', response.json)
        self.assertEqual(self.merge_state(), before)

    def test_existing_database_migrates_without_losing_records(self):
        legacy_path = str(Path(self.folder.name) / 'legacy.sqlite3')
        original = self.merge_state()
        source = sqlite3.connect(self.store.filename)
        legacy = sqlite3.connect(legacy_path)
        try:
            source.backup(legacy)
            legacy.execute('ALTER TABLE categories DROP COLUMN deleted_at')
            legacy.commit()
            columns = [row[1] for row in legacy.execute('PRAGMA table_info(categories)')]
            self.assertNotIn('deleted_at', columns)
        finally:
            source.close()
            legacy.close()
        migrated = SQLiteStore(legacy_path)
        SQLiteStore(legacy_path)
        with migrated.transaction() as connection:
            for table, records in original.items():
                migrated_records = [dict(row) for row in connection.execute(f'SELECT * FROM {table} ORDER BY rowid')]
                self.assertEqual(migrated_records, records)
            self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(), [])
            columns = [row['name'] for row in connection.execute('PRAGMA table_info(categories)')]
            self.assertEqual(columns.count('deleted_at'), 1)
        result = MergeCategoriesController(ProjectCategory(migrated)).merge_categories(self.source['id'], self.target['id'], 1, 1)
        entity = ProjectCategory(migrated)
        entity.delete(self.source['id'], 2)
        self.assertEqual(entity.list_deleted()[0]['target'], result['target']['name'])

    def test_merge_rejects_same_or_inactive_categories(self):
        same = self.send('/categories/merge', {'sourceId': self.source['id'], 'targetId': self.source['id'],
                                              'sourceVersion': 1, 'targetVersion': 1})
        self.assertEqual(same.status_code, 400)
        self.send('/categories/' + self.source['id'] + '/archive', {'version': 1})
        result = self.send('/categories/merge', {'sourceId': self.source['id'], 'targetId': self.target['id'],
                                               'sourceVersion': 2, 'targetVersion': 1})
        self.assertEqual(result.status_code, 409)

    def test_daily_boundaries_and_category_filter_have_no_double_counting(self):
        report = self.report()
        self.assertEqual([row['value'] for row in report['rows']], [2, 2, 1, 1])
        filtered = self.report(categoryId=self.source['id'])
        self.assertEqual([row['value'] for row in filtered['rows']], [1, 2, 1, 0])
        self.assertEqual(filtered['period']['start'], '2026-11-03T16:00:00.000000Z')
        self.assertEqual(filtered['period']['end'], '2026-11-04T16:00:00.000000Z')

    def test_week_month_and_invalid_periods(self):
        week = Period.selected('weekly', '2026-11-04')
        self.assertEqual((week.start_date, week.end_date), ('2026-11-02', '2026-11-09'))
        month = Period.selected('monthly', '2024-02-15')
        self.assertEqual((month.start_date, month.end_date), ('2024-02-01', '2024-03-01'))
        for values in [{'period': 'hourly', 'date': '2026-11-04'}, {'period': 'daily', 'date': 'bad'}]:
            self.assertEqual(self.send('/reports', values).status_code, 400)

    def test_comparison_zero_baseline_and_equal_periods(self):
        values = {'period': 'daily', 'baselineDate': '2025-11-04', 'comparisonDate': '2026-11-04'}
        report = self.send('/reports/compare', values).json['report']
        self.assertTrue(all(row['percentChange'] is None for row in report['rows']))
        self.assertEqual([row['difference'] for row in report['rows']], [2, 2, 1, 1])
        values['baselineDate'] = values['comparisonDate']
        report = self.send('/reports/compare', values).json['report']
        self.assertTrue(all(row['difference'] == 0 and row['percentChange'] == 0 for row in report['rows']))

    def test_export_retains_original_snapshot_after_new_activity_and_rename(self):
        report = self.report(categoryId=self.source['id'])
        self.entity.update_details(self.source['id'], 'Renamed', '', 1)
        with self.store.transaction(write=True) as connection:
            connection.execute("INSERT INTO activities VALUES ('later-view', 1, 'VIEW', '2026-11-04T00:00:00.000000Z', 'customer')")
        response = self.client.get('/api/management/reports/' + report['id'] + '/export')
        rows = list(csv.reader(StringIO(response.data.decode('utf-8-sig'))))
        self.assertIn(['Category', 'Modern Style'], rows)
        self.assertIn(['Project views', '2'], rows)
        self.assertEqual(response.mimetype, 'text/csv')

    def test_export_handles_formula_like_category_names(self):
        category = self.entity.create('=1+1', '')
        report = self.report(categoryId=category['id'])
        response = self.client.get('/api/management/reports/' + report['id'] + '/export')
        rows = list(csv.reader(StringIO(response.data.decode('utf-8-sig'))))
        self.assertIn(['Category', "'=1+1"], rows)

    def test_activity_retries_are_deduplicated_and_invalid_projects_rejected(self):
        values = {'projectId': 1, 'type': 'VIEW', 'eventId': 'customer-test-event'}
        first = self.client.post('/api/activity', json=values, headers={'X-CSRF-Token': self.token})
        second = self.client.post('/api/activity', json=values, headers={'X-CSRF-Token': self.token})
        self.assertTrue(first.json['recorded'])
        self.assertFalse(second.json['recorded'])
        values['projectId'] = 999
        self.assertEqual(self.client.post('/api/activity', json=values, headers={'X-CSRF-Token': self.token}).status_code, 404)

    def test_authenticated_access_request_protection_and_private_files(self):
        self.assertEqual(self.client.post('/api/management/categories', json={'name': 'Blocked'}).status_code, 403)
        self.assertEqual(self.app.test_client().get('/api/management/categories').status_code, 401)
        self.assertEqual(self.client.get('/instance/session-secret').status_code, 404)
        self.assertEqual(self.client.get('/app.py').status_code, 404)

    def test_persistence_and_concurrent_name_uniqueness(self):
        def create_duplicate(_):
            try:
                self.entity.create('Same name', '')
                return 'created'
            except BusinessError:
                return 'duplicate'
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(list(executor.map(create_duplicate, range(2))), ['created', 'duplicate'])
        restarted = create_app(config=self.config).test_client()
        restarted.post('/api/auth/login', json={'email': 'manager@demo.agroup', 'password': 'demo'})
        matches = restarted.get('/api/management/categories?search=Same%20name').json['categories']
        self.assertEqual(len(matches), 1)


if __name__ == '__main__':
    unittest.main()
