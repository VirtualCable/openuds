import pickle

from tests.services.openshift import fixtures
from tests.utils.test import UDSTransactionTestCase


class TestOpenshiftDeploymentSerialization(UDSTransactionTestCase):
    def setUp(self) -> None:
        """
        Set up test environment and clear fixtures before each test.
        """
        super().setUp()
        fixtures.clear()
        
    def _make_userservice(self):
        """
        Helper to create a userservice with all fields set for serialization tests.
        """
        userservice = fixtures.create_userservice()
        userservice._name = 'test-vm'
        userservice._ip = '192.168.1.100'
        userservice._mac = '00:11:22:33:44:55'
        userservice._vmid = 'test-vm-id'
        userservice._reason = 'test-reason'
        userservice._waiting_name = True
        return userservice
        
    # --- Serialization Tests ---
    def test_userservice_serialization(self) -> None:
        """
        Test that userservice object is correctly serialized and deserialized with all fields preserved.
        """
        userservice = self._make_userservice()
        data = pickle.dumps(userservice)
        userservice2 = pickle.loads(data)

        self.assertEqual(userservice2._name, 'test-vm')
        self.assertEqual(userservice2._ip, '192.168.1.100')
        self.assertEqual(userservice2._mac, '00:11:22:33:44:55')
        self.assertEqual(userservice2._vmid, 'test-vm-id')
        self.assertEqual(userservice2._reason, 'test-reason')
        self.assertTrue(userservice2._waiting_name)

    def test_userservice_methods_after_serialization(self) -> None:
        """
        Test that userservice methods return correct values after serialization and deserialization.
        """
        userservice = self._make_userservice()
        data = pickle.dumps(userservice)
        userservice2 = pickle.loads(data)

        self.assertEqual(userservice2.get_name(), 'test-vm')
        self.assertEqual(userservice2.get_ip(), '192.168.1.100')
        self.assertEqual(userservice2._mac, '00:11:22:33:44:55')

    # --- Field Presence Tests ---
    def test_autoserializable_fields(self) -> None:
        """
        Test that all expected autoserializable fields are present in userservice object.
        """
        userservice = self._make_userservice()
        expected = ['_name', '_ip', '_mac', '_vmid', '_reason', '_waiting_name']
        for field in expected:
            self.assertTrue(hasattr(userservice, field), f"Missing field: {field}")