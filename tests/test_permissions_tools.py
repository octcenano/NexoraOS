import unittest

from nexora.core.permissions import (
    ApprovalRequiredError,
    SENSITIVE_TOOLS,
    Permission,
    ToolPolicy,
    may_access,
)


class PermissionTests(unittest.TestCase):
    def test_may_access_requires_grant_and_scope(self):
        p = Permission("github", ("repo",), granted=False)
        self.assertFalse(may_access(p, "repo"))
        p2 = Permission("github", ("repo",), granted=True)
        self.assertTrue(may_access(p2, "repo"))
        self.assertFalse(may_access(p2, "admin"))


class ToolPolicyTests(unittest.TestCase):
    def test_may_use_only_declared_tools(self):
        policy = ToolPolicy(mode="security", allowed_tools=("defensive_audit_readonly",))
        self.assertTrue(policy.may_use("defensive_audit_readonly"))
        self.assertFalse(policy.may_use("execute_commands"))

    def test_sensitive_tools_always_require_approval(self):
        for tool in SENSITIVE_TOOLS:
            policy = ToolPolicy(mode="forge", allowed_tools=(tool,))
            self.assertTrue(policy.requires_approval(tool))
            with self.assertRaises(ApprovalRequiredError):
                policy.authorize_use(tool, user_approved=False)
            policy.authorize_use(tool, user_approved=True)  # no lanza

    def test_undeclared_tool_is_rejected_even_with_approval(self):
        policy = ToolPolicy(mode="forge", allowed_tools=("local_ai",))
        with self.assertRaises(PermissionError):
            policy.authorize_use("execute_commands", user_approved=True)

    def test_approval_tool_must_be_declared(self):
        with self.assertRaises(ValueError):
            ToolPolicy(mode="forge", allowed_tools=("local_ai",), approval_tools=("file_export",))

    def test_empty_mode_rejected(self):
        with self.assertRaises(ValueError):
            ToolPolicy(mode="")


if __name__ == "__main__":
    unittest.main()
