"""
ICT711 Assessment 3 - Member 3: Testing, Results and Coverage
Automated tests for the four planned cases M3-01 to M3-04.

Target application: django-todo 2.7.0 running inside the GTD host project.
Run with:  python manage.py test member3_tests -v 2 --durations 0

Behaviour checked against the django-todo 2.7.0 source before writing assertions:
  * Comments are posted to the URL named "todo:task_detail" with the submit field
    "add_comment" and the textarea field "comment-body" (views/task_detail.py,
    function handle_add_comment). The body is cleaned with bleach.clean(strip=True),
    a Comment row is created, and send_email_to_thread_participants() emails the
    task creator, assignees and previous commenters.
  * The comment textarea has the HTML "required" attribute (browser-side check
    only). The server performs no blank-comment validation and Comment.body is
    blank=True.
  * Search is a GET request to "todo:search" with parameter "q". It matches
    title OR note with icontains (case-insensitive) and, for non-superusers,
    keeps only tasks whose list belongs to one of the user's groups. The template
    receives "found_tasks" and "query_string" and shows
    "No results to show, sorry." when nothing matches.
  * Every todo view needs a logged-in user AND is_staff=True, because
    TODO_STAFF_ONLY defaults to True (todo/defaults.py, todo/utils.staff_check).

Each test method is ONE planned case. Sub-checks inside a case are reported with
subTest so the team total stays at 16 cases.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from todo.models import Comment, Task, TaskList


class Member3BaseTestCase(TestCase):
    """Shared test data: one staff user in one group, one list, two tasks,
    and a second group the user does NOT belong to."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.group = Group.objects.create(name="ICT711 Member 3 Group")
        cls.user = User.objects.create_user(
            username="m3_staff",
            email="m3_staff@example.com",
            password="test-only-password",
            is_staff=True,
        )
        cls.user.groups.add(cls.group)

        cls.task_list = TaskList.objects.create(
            name="M3 Test List", slug="m3-test-list", group=cls.group
        )
        cls.task = Task.objects.create(
            title="Prepare quarterly invoice",
            note="Remember to attach the zebrafinch summary",
            task_list=cls.task_list,
            created_by=cls.user,
        )
        cls.second_task = Task.objects.create(
            title="Book meeting room",
            note="Level 3",
            task_list=cls.task_list,
            created_by=cls.user,
        )

        # Data in a group the test user is NOT a member of.
        cls.other_group = Group.objects.create(name="ICT711 Other Group")
        cls.other_list = TaskList.objects.create(
            name="Other Group List", slug="other-group-list", group=cls.other_group
        )
        cls.hidden_task = Task.objects.create(
            title="Hidden invoice task",
            note="Belongs to another group",
            task_list=cls.other_list,
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.detail_url = reverse("todo:task_detail", kwargs={"task_id": self.task.pk})
        self.search_url = reverse("todo:search")

    def post_comment(self, body):
        """Send the same POST the task detail page's comment form sends."""
        return self.client.post(
            self.detail_url, {"add_comment": "Add Comment", "comment-body": body}
        )


class M3CommentTests(Member3BaseTestCase):
    """M3-01 and M3-02: task comments."""

    def test_m3_01_add_valid_comment(self):
        """M3-01 Add a valid task comment.
        Expected: the comment is saved once against the right task and author,
        appears on the task page, unsafe HTML (<script>) is removed, a success
        message is queued, and a notification email is sent."""
        body = "Valid M3-01 comment <b>bold</b><script>alert(1)</script>"
        response = self.post_comment(body)

        with self.subTest("request succeeds"):
            self.assertEqual(response.status_code, 200)

        with self.subTest("exactly one comment saved on this task"):
            self.assertEqual(Comment.objects.filter(task=self.task).count(), 1)

        comment = Comment.objects.get(task=self.task)

        with self.subTest("author recorded"):
            self.assertEqual(comment.author, self.user)

        with self.subTest("unsafe HTML removed by bleach, safe formatting kept"):
            # bleach.clean(strip=True) removes disallowed tags such as <script>
            # but keeps tags on its default allow-list such as <b>.
            self.assertIn("Valid M3-01 comment", comment.body)
            self.assertNotIn("<script>", comment.body)
            self.assertIn("<b>bold</b>", comment.body)

        with self.subTest("success message queued for the user"):
            shown = [str(m) for m in get_messages(response.wsgi_request)]
            self.assertTrue(any("Comment posted" in m for m in shown), shown)

        with self.subTest("comment visible on a fresh page load"):
            self.assertContains(self.client.get(self.detail_url), "Valid M3-01 comment")

        with self.subTest("no comment added to any other task"):
            self.assertEqual(Comment.objects.exclude(task=self.task).count(), 0)

        with self.subTest("notification email sent to thread participants"):
            self.assertEqual(len(mail.outbox), 1)
            self.assertIn("m3_staff@example.com", mail.outbox[0].to)
            self.assertIn(self.task.title, mail.outbox[0].subject)

    def test_m3_02_empty_comment_rejected(self):
        """M3-02 Submit an empty comment and check validation.
        Requirement: a blank comment must be rejected by the SERVER and nothing saved.
        The browser 'required' attribute is client-side only, so this test posts
        directly to bypass the browser. Expected to FAIL on django-todo 2.7.0
        because handle_add_comment() has no server-side validation.
        Keep the failure; do not weaken the assertion."""
        for label, body in (("empty string", ""), ("whitespace only", "   ")):
            with self.subTest(label):
                before = Comment.objects.filter(task=self.task).count()
                outbox_before = len(mail.outbox)

                self.post_comment(body)

                self.assertEqual(
                    Comment.objects.filter(task=self.task).count(),
                    before,
                    f"Server saved a blank comment ({label}): no server-side validation",
                )
                self.assertEqual(
                    len(mail.outbox),
                    outbox_before,
                    f"Notification email sent for a blank comment ({label})",
                )


class M3SearchTests(Member3BaseTestCase):
    """M3-03 and M3-04: task search."""

    def test_m3_03_search_known_keyword(self):
        """M3-03 Search for a known task keyword.
        Expected: the matching task is returned; matching is case-insensitive and
        includes the note field; tasks from other groups are never returned."""
        response = self.client.get(self.search_url, {"q": "invoice"})

        with self.subTest("request succeeds"):
            self.assertEqual(response.status_code, 200)

        with self.subTest("only the user's matching task is returned"):
            self.assertEqual(list(response.context["found_tasks"]), [self.task])

        with self.subTest("search term echoed back"):
            self.assertEqual(response.context["query_string"], "invoice")

        with self.subTest("result rendered on the page"):
            self.assertContains(response, "Prepare quarterly invoice")
            self.assertContains(response, "1 search results")

        with self.subTest("other group's task not leaked"):
            self.assertNotContains(response, "Hidden invoice task")

        with self.subTest("case-insensitive match"):
            upper = self.client.get(self.search_url, {"q": "INVOICE"})
            self.assertEqual(list(upper.context["found_tasks"]), [self.task])

        with self.subTest("keyword found in the note field"):
            note = self.client.get(self.search_url, {"q": "zebrafinch"})
            self.assertEqual(list(note.context["found_tasks"]), [self.task])

    def test_m3_04_search_no_match(self):
        """M3-04 Search for a keyword with no matching tasks.
        Expected: page loads normally, zero results, a 'no results' message,
        and no task titles listed."""
        response = self.client.get(self.search_url, {"q": "nonexistentkeyword123"})

        with self.subTest("request succeeds"):
            self.assertEqual(response.status_code, 200)

        with self.subTest("zero results returned"):
            self.assertEqual(response.context["found_tasks"].count(), 0)

        with self.subTest("no-results message shown"):
            self.assertContains(response, "No results to show")

        with self.subTest("no task titles listed"):
            for title in (self.task.title, self.second_task.title, self.hidden_task.title):
                self.assertNotContains(response, title)


class M3ExploratoryTests(Member3BaseTestCase):
    """OPTIONAL exploratory check - NOT one of the 16 planned cases.
    Report it separately as a defect candidate, not in the 16-case totals.
    Opening the search page with no query string should not crash the server."""

    def test_explore_search_page_without_query_string(self):
        self.client.raise_request_exception = False
        response = self.client.get(self.search_url)
        self.assertNotEqual(
            response.status_code,
            500,
            "Search page crashes (HTTP 500) when opened with no query string",
        )
