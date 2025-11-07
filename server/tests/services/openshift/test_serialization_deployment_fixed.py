import pickle
from tests.services.openshift import fixtures
from tests.utils.test import UDSTransactionTestCase

class TestOpenshiftUserServiceFixed(UDSTransactionTestCase):
    def setUp(self) -> None:
        """
        Set up test environment and clear fixtures before each test.
        """
        super().setUp()
        fixtures.clear()

    # --- Serialization Tests ---
    def test_userservice_fixed_serialization(self) -> None:
        """
        Test that userservice_fixed object is correctly serialized and deserialized with all fields preserved.
        """
        userservice = fixtures.create_userservice_fixed()
        userservice._name = 'fixed-vm'
        userservice._reason = 'fixed-reason'
        data = pickle.dumps(userservice)
        userservice2 = pickle.loads(data)
        self.assertEqual(userservice2._name, 'fixed-vm')
        self.assertEqual(userservice2._reason, 'fixed-reason')