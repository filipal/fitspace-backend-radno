"""Tests for avatar-related API routes."""
import json
from unittest.mock import Mock, patch

from src.routes import api_routes


class TestAvatarRoutes:
    """Collection of avatar route tests."""

    def setup_method(self):
        self.connection = Mock()

    def test_create_avatar_success(self):
        event = {
            'path': '/api/v1/users/1/avatars',
            'httpMethod': 'POST',
            'body': json.dumps({
                'display_name': ' Competition Prep ',
                'age': '28',
                'gender': 'FEMALE',
                'height_cm': '172.5',
                'weight_kg': 68,
                'body_fat_percent': '18.2',
                'waist_cm': 70,
            })
        }

        created_avatar = {
            'id': 10,
            'user_id': 1,
            'display_name': 'Competition Prep',
            'age': 28,
            'gender': 'female',
            'height_cm': 172.5,
            'weight_kg': 68.0,
            'body_fat_percent': 18.2,
            'shoulder_circumference_cm': None,
            'waist_cm': 70.0,
            'hips_cm': None,
            'notes': None,
            'created_at': 'now',
            'updated_at': 'now'
        }

        with patch('src.routes.api_routes.Avatar') as mock_avatar_class:
            mock_avatar_instance = Mock()
            mock_avatar_class.return_value = mock_avatar_instance
            mock_avatar_instance.create.return_value = created_avatar

            response = api_routes.handle_request(event, self.connection)

            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['data']['display_name'] == 'Competition Prep'

            create_args = mock_avatar_instance.create.call_args
            assert create_args[0][0] == 1
            assert create_args[0][1] == {
                'display_name': 'Competition Prep',
                'age': 28,
                'gender': 'female',
                'height_cm': 172.5,
                'weight_kg': 68.0,
                'body_fat_percent': 18.2,
                'waist_cm': 70.0
            }

    def test_list_avatars_success(self):
        event = {
            'path': '/api/v1/users/2/avatars',
            'httpMethod': 'GET'
        }

        avatars = [
            {'id': 1, 'user_id': 2, 'display_name': 'Cut', 'created_at': 'now', 'updated_at': 'now'},
            {'id': 2, 'user_id': 2, 'display_name': 'Bulk', 'created_at': 'now', 'updated_at': 'now'}
        ]

        with patch('src.routes.api_routes.Avatar') as mock_avatar_class:
            mock_instance = Mock()
            mock_avatar_class.return_value = mock_instance
            mock_instance.list_for_user.return_value = avatars

            response = api_routes.handle_request(event, self.connection)

            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert len(body['data']) == 2
            mock_instance.list_for_user.assert_called_once_with(2)

    def test_get_avatar_success(self):
        event = {
            'path': '/api/v1/users/3/avatars/5',
            'httpMethod': 'GET'
        }

        avatar = {'id': 5, 'user_id': 3, 'display_name': 'Default'}

        with patch('src.routes.api_routes.Avatar') as mock_avatar_class:
            mock_instance = Mock()
            mock_avatar_class.return_value = mock_instance
            mock_instance.get.return_value = avatar

            response = api_routes.handle_request(event, self.connection)

            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['data']['id'] == 5
            mock_instance.get.assert_called_once_with(3, 5)

    def test_patch_avatar_partial_update(self):
        event = {
            'path': '/api/v1/users/4/avatars/7',
            'httpMethod': 'PATCH',
            'body': json.dumps({'weight_kg': '82.4', 'notes': 'updated'})
        }

        updated_avatar = {'id': 7, 'user_id': 4, 'weight_kg': 82.4, 'notes': 'updated'}

        with patch('src.routes.api_routes.Avatar') as mock_avatar_class:
            mock_instance = Mock()
            mock_avatar_class.return_value = mock_instance
            mock_instance.update.return_value = updated_avatar

            response = api_routes.handle_request(event, self.connection)

            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['data']['weight_kg'] == 82.4

            mock_instance.update.assert_called_once_with(
                4,
                7,
                {'weight_kg': 82.4, 'notes': 'updated'}
            )