import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import storage
import utils
import handlers
import access_control


class StorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "bot.db")
        storage.init_db(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_model_history_trim_and_clear(self) -> None:
        self.assertIsNone(storage.get_user_model(1))

        storage.set_user_model(1, "gemini-2.5-flash")
        self.assertEqual(storage.get_user_model(1), "gemini-2.5-flash")

        storage.append_turn(1, "gemini-2.5-flash", "hello", "hi")
        history = storage.load_history(1, 20)
        self.assertEqual([item.role for item in history], ["user", "model"])
        self.assertEqual(history[0].parts[0].text, "hello")
        self.assertEqual(history[1].parts[0].text, "hi")

        for index in range(25):
            storage.append_turn(
                1,
                "gemini-2.5-flash",
                f"user {index}",
                f"model {index}",
            )

        history = storage.load_history(1, 20)
        self.assertEqual(len(history), 40)
        self.assertEqual(history[0].role, "user")
        self.assertEqual(history[-1].role, "model")
        self.assertEqual(history[-1].parts[0].text, "model 24")

        with closing(sqlite3.connect(self.db_path)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM chat_messages WHERE user_id = 1"
            ).fetchone()[0]
        self.assertEqual(count, 40)

        storage.clear_user_history(1)
        self.assertEqual(storage.get_user_model(1), "gemini-2.5-flash")
        self.assertEqual(storage.load_history(1, 20), [])

    def test_access_request_lifecycle(self) -> None:
        self.assertIsNone(storage.get_access_status("user", 2))

        status, created = storage.create_access_request(
            "user",
            2,
            "alice",
            "Alice",
            "Example",
            None,
            2,
        )
        self.assertEqual(status, "pending")
        self.assertTrue(created)
        self.assertEqual(storage.get_access_status("user", 2), "pending")

        status, created = storage.create_access_request(
            "user",
            2,
            "alice2",
            "Alice",
            "New",
            None,
            2,
        )
        self.assertEqual(status, "pending")
        self.assertFalse(created)

        storage.review_access_request("user", 2, "approved", 100)
        self.assertEqual(storage.get_access_status("user", 2), "approved")

        storage.review_access_request("user", 2, "rejected", 100)
        self.assertEqual(storage.get_access_status("user", 2), "rejected")

        storage.review_access_request("user", 2, "revoked", 100)
        self.assertEqual(storage.get_access_status("user", 2), "revoked")

    def test_approved_list_only_returns_users(self) -> None:
        status, created = storage.create_access_request(
            "chat",
            -100123,
            "requester",
            "Request",
            "User",
            "Test Group",
            9,
        )
        self.assertEqual(status, "pending")
        self.assertTrue(created)

        storage.review_access_request("chat", -100123, "approved", 100)
        storage.review_access_request("user", 3, "approved", 100)
        storage.review_access_request("user", 4, "rejected", 100)
        storage.review_access_request("user", 5, "revoked", 100)

        records = storage.list_approved_access()
        subjects = {
            (record["subject_type"], record["subject_id"])
            for record in records
        }
        self.assertEqual(subjects, {("user", 3)})

    def test_access_request_setting_defaults_to_enabled(self) -> None:
        self.assertTrue(storage.get_access_requests_enabled())

        storage.set_access_requests_enabled(False)
        self.assertFalse(storage.get_access_requests_enabled())

        storage.set_access_requests_enabled(True)
        self.assertTrue(storage.get_access_requests_enabled())


class FakeChat:
    def __init__(self, model: str, history: list | None = None):
        self.model = model
        self.history = history or []

    def get_history(self) -> list:
        return self.history


class FakeChats:
    def create(self, model: str, history: list | None = None) -> FakeChat:
        return FakeChat(model, history)


class FakeAio:
    chats = FakeChats()


class FakeClient:
    aio = FakeAio()


class FakeUser:
    def __init__(
        self,
        user_id: int,
        username: str | None = "user",
        first_name: str | None = "First",
        last_name: str | None = "Last",
    ):
        self.id = user_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name


class FakeChatInfo:
    def __init__(self, chat_id: int = 1, chat_type: str = "private", title: str | None = None):
        self.id = chat_id
        self.type = chat_type
        self.title = title


class FakeMessage:
    def __init__(self, user_id: int, chat_type: str = "private", chat_id: int = 1, title: str | None = None):
        self.from_user = FakeUser(user_id)
        self.chat = FakeChatInfo(chat_id=chat_id, chat_type=chat_type, title=title)


class FakeCallback:
    def __init__(self, user_id: int, data: str):
        self.from_user = FakeUser(user_id)
        self.data = data
        self.id = "callback-id"
        self.message = type("CallbackMessage", (), {
            "chat": FakeChatInfo(chat_id=99),
            "message_id": 123,
        })()


class FakeBot:
    def __init__(self):
        self.replies: list[str] = []
        self.sent: list[tuple[int, str]] = []
        self.answers: list[tuple[str, str, bool | None]] = []
        self.edits: list[str] = []

    async def reply_to(self, message, text, **kwargs):
        self.replies.append(text)

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text))

    async def answer_callback_query(self, callback_query_id, text=None, show_alert=None, **kwargs):
        self.answers.append((callback_query_id, text, show_alert))

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)


class UtilsSqliteTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        storage.init_db(os.path.join(self.tmp.name, "bot.db"))
        utils.chat_dict.clear()
        utils.client = FakeClient()
        access_control.init_admin_user_ids("100")

    async def asyncTearDown(self) -> None:
        utils.chat_dict.clear()
        utils.client = None
        access_control.admin_user_ids = set()
        self.tmp.cleanup()

    async def test_restore_switch_clear_and_image_summary(self) -> None:
        session = await utils.init_user(7)
        self.assertIsNone(session["model"])
        self.assertIsNone(session["chat"])

        await utils.select_model(7, "gemini-2.5-flash")
        await utils.save_turn(7, "hello", "hi")
        await utils.save_turn(7, [object(), "what is this?"], "an image answer")
        await utils.save_turn(7, "empty", "   ")
        self.assertEqual(len(utils.chat_dict[7]["chat"].history), 4)

        history = storage.load_history(7, 20)
        self.assertEqual(
            [item.parts[0].text for item in history],
            ["hello", "hi", "[Image] what is this?", "an image answer"],
        )

        utils.chat_dict.clear()
        restored = await utils.init_user(7)
        self.assertEqual(restored["model"], "gemini-2.5-flash")
        self.assertEqual(restored["chat"].model, "gemini-2.5-flash")
        self.assertEqual(len(restored["chat"].history), 4)

        await utils.select_model(7, "gemini-2.5-pro")
        switched = utils.chat_dict[7]
        self.assertEqual(switched["model"], "gemini-2.5-pro")
        self.assertEqual(switched["chat"].model, "gemini-2.5-pro")
        self.assertEqual(len(switched["chat"].history), 4)

        await utils.clear_history(7)
        self.assertEqual(storage.get_user_model(7), "gemini-2.5-pro")
        self.assertEqual(storage.load_history(7, 20), [])
        self.assertEqual(utils.chat_dict[7]["chat"].model, "gemini-2.5-pro")

    async def test_access_request_and_admin_review_flow(self) -> None:
        bot = FakeBot()
        message = FakeMessage(7)

        authorized = await handlers.ensure_authorized(message, bot)
        self.assertFalse(authorized)
        self.assertEqual(storage.get_access_status("user", 7), "pending")
        self.assertEqual(len(bot.sent), 1)
        self.assertEqual(bot.sent[0][0], 100)

        authorized = await handlers.ensure_authorized(message, bot)
        self.assertFalse(authorized)
        self.assertEqual(len(bot.sent), 1)

        callback = FakeCallback(200, "access:approve:user:7")
        await handlers.access_callback(callback, bot)
        self.assertEqual(storage.get_access_status("user", 7), "pending")
        self.assertEqual(bot.answers[-1][1], "Only administrators can review requests")

        callback = FakeCallback(100, "access:approve:user:7")
        await handlers.access_callback(callback, bot)
        self.assertEqual(storage.get_access_status("user", 7), "approved")
        self.assertIn("approved", bot.edits[-1])

        authorized = await handlers.ensure_authorized(message, bot)
        self.assertTrue(authorized)

    async def test_rejected_user_is_not_resubmitted(self) -> None:
        storage.create_access_request("user", 8, "user", "First", "Last", None, 8)
        storage.review_access_request("user", 8, "rejected", 100)
        bot = FakeBot()

        authorized = await handlers.ensure_authorized(FakeMessage(8), bot)

        self.assertFalse(authorized)
        self.assertEqual(storage.get_access_status("user", 8), "rejected")
        self.assertEqual(bot.sent, [])
        self.assertIn("rejected", bot.replies[-1])

    async def test_group_access_is_checked_by_user_id(self) -> None:
        bot = FakeBot()
        message = FakeMessage(7, chat_type="group", chat_id=-100123, title="Test Group")

        authorized = await handlers.ensure_authorized(message, bot)
        self.assertFalse(authorized)
        self.assertEqual(storage.get_access_status("user", 7), "pending")
        self.assertIsNone(storage.get_access_status("chat", -100123))
        self.assertIn("New user access request", bot.sent[0][1])

        callback = FakeCallback(100, "access:approve:user:7")
        await handlers.access_callback(callback, bot)
        self.assertEqual(storage.get_access_status("user", 7), "approved")

        self.assertTrue(await handlers.ensure_authorized(message, bot))
        private_message = FakeMessage(7)
        self.assertTrue(await handlers.ensure_authorized(private_message, bot))

    async def test_access_list_is_admin_only_and_revoke_is_protected(self) -> None:
        storage.create_access_request("user", 7, "user", "First", "Last", None, 7)
        storage.review_access_request("user", 7, "approved", 100)
        storage.create_access_request("chat", -100123, "user", "First", "Last", "Test Group", 7)
        storage.review_access_request("chat", -100123, "approved", 100)

        bot = FakeBot()
        await handlers.access(FakeMessage(7), bot)
        self.assertIn("Only administrators", bot.replies[-1])
        self.assertEqual(len(bot.sent), 0)

        await handlers.access_callback(FakeCallback(7, "access:revoke:user:7"), bot)
        self.assertEqual(storage.get_access_status("user", 7), "approved")
        self.assertEqual(bot.answers[-1][1], "Only administrators can review requests")

        await handlers.access(FakeMessage(100), bot)
        self.assertIn("Approved access records", bot.replies[-1])
        self.assertEqual(len(bot.sent), 1)

        await handlers.access_callback(FakeCallback(100, "access:revoke:user:7"), bot)
        self.assertEqual(storage.get_access_status("user", 7), "revoked")

    async def test_access_request_switch_is_admin_only(self) -> None:
        bot = FakeBot()

        await handlers.accessrequest(FakeMessage(7), bot)
        self.assertIn("Only administrators", bot.replies[-1])
        self.assertTrue(storage.get_access_requests_enabled())

        admin_message = FakeMessage(100)
        admin_message.text = "/accessrequest"
        await handlers.accessrequest(admin_message, bot)
        self.assertFalse(storage.get_access_requests_enabled())
        self.assertIn("closed", bot.replies[-1])

        closed_request = FakeMessage(7)
        authorized = await handlers.ensure_authorized(closed_request, bot)
        self.assertFalse(authorized)
        self.assertIsNone(storage.get_access_status("user", 7))
        self.assertIn("currently closed", bot.replies[-1])

        await handlers.accessrequest(admin_message, bot)
        self.assertTrue(storage.get_access_requests_enabled())
        self.assertIn("open", bot.replies[-1])

        authorized = await handlers.ensure_authorized(closed_request, bot)
        self.assertFalse(authorized)
        self.assertEqual(storage.get_access_status("user", 7), "pending")

    async def test_existing_pending_request_still_reports_when_switch_is_closed(self) -> None:
        storage.create_access_request("user", 7, "user", "First", "Last", None, 7)
        storage.set_access_requests_enabled(False)

        bot = FakeBot()
        authorized = await handlers.ensure_authorized(FakeMessage(7), bot)

        self.assertFalse(authorized)
        self.assertEqual(storage.get_access_status("user", 7), "pending")
        self.assertIn("submitted", bot.replies[-1])


if __name__ == "__main__":
    unittest.main()
