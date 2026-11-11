import unittest

from nexora.core.vault import KeyringBackend, MemoryBackend, SecureVault, VaultUnavailableError, vault_from_config


class FakeKeyring:
    def __init__(self):
        self.store = {}

    def set_password(self, service, user, pw):
        self.store[(service, user)] = pw

    def get_password(self, service, user):
        return self.store.get((service, user))

    def delete_password(self, service, user):
        del self.store[(service, user)]


class VaultTests(unittest.TestCase):
    def test_validation(self):
        vault = SecureVault()
        with self.assertRaises(ValueError):
            vault.set_secret("", "x")
        with self.assertRaises(ValueError):
            vault.set_secret("k", "")

    def test_revoke_missing_returns_false(self):
        self.assertFalse(SecureVault().revoke_secret("nope"))

    def test_repr_never_leaks_values(self):
        vault = SecureVault()
        vault.set_secret("token", "super-secret-value")
        self.assertNotIn("super-secret-value", repr(vault))
        self.assertTrue(vault.has_secret("token"))

    def test_memory_backend_is_volatile(self):
        self.assertFalse(SecureVault(MemoryBackend()).persistent)

    def test_keyring_backend_delegates_to_os_store(self):
        fake = FakeKeyring()
        vault = SecureVault(KeyringBackend(keyring_module=fake))
        vault.set_secret("api", "abc")
        self.assertEqual(fake.store[("nexora-os", "api")], "abc")
        self.assertEqual(vault.get_secret("api"), "abc")
        self.assertTrue(vault.revoke_secret("api"))
        self.assertFalse(vault.revoke_secret("api"))
        self.assertTrue(vault.persistent)

    def test_keyring_missing_is_a_clear_error(self):
        try:
            import keyring  # noqa: F401
            self.skipTest("keyring instalado")
        except ImportError:
            with self.assertRaises(VaultUnavailableError):
                vault_from_config({"vault": {"backend": "keyring"}})

    def test_default_from_config_is_memory(self):
        self.assertEqual(vault_from_config({"vault": {"backend": "memory"}}).backend_name, "memory")


if __name__ == "__main__":
    unittest.main()
