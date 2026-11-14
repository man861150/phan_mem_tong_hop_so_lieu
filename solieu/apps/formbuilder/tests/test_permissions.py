from django.test import Client

from apps.accounts.permissions import can
from apps.formbuilder.tests.base import FormFixture


class PermissionMatrixTests(FormFixture):
    def test_role_actions(self):
        for action in (
            "view_form_templates",
            "design_form_template",
            "publish_form_template",
            "archive_form_template",
        ):
            self.assertTrue(can(self.head, action, self.htkn.pk))
            self.assertFalse(can(self.head, action, self.gdcn.pk))
            self.assertTrue(can(self.admin, action, self.gdcn.pk))
            self.assertFalse(can(self.officer, action, self.htkn.pk))
        self.assertTrue(can(self.center, "view_form_templates"))
        self.assertFalse(can(self.center, "design_form_template"))
        self.assertFalse(can(self.center, "publish_form_template"))
        self.assertFalse(can(self.center, "archive_form_template"))

    def test_anonymous_is_redirected_and_officer_is_forbidden(self):
        template = self.make_template()
        anonymous = Client(HTTP_HOST="localhost")
        response = anonymous.get("/bieu-mau/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dang-nhap/", response.url)
        officer = self.login(self.officer)
        for url in (
            "/bieu-mau/",
            "/bieu-mau/tao-moi/",
            f"/bieu-mau/{template.pk}/thiet-ke/",
            f"/bieu-mau/{template.pk}/xem-truoc/",
            f"/bieu-mau/{template.pk}/phien-ban/",
            "/bieu-mau/999999/thiet-ke/",
        ):
            self.assertEqual(officer.get(url).status_code, 403, url)
        self.assertEqual(
            officer.post(f"/bieu-mau/{template.pk}/xuat-ban/").status_code,
            403,
        )

    def test_department_head_is_scoped_and_center_head_is_read_only(self):
        template = self.make_template()
        own = self.login(self.head)
        self.assertEqual(own.get("/bieu-mau/").status_code, 200)
        self.assertContains(own.get("/"), 'href="/bieu-mau/"')
        other = self.login(self.head_other)
        self.assertEqual(
            other.get(f"/bieu-mau/{template.pk}/thiet-ke/").status_code, 404
        )
        field = template.current_draft.fields.get(core_key="ten")
        self.assertEqual(
            other.get(f"/bieu-mau/truong/{field.pk}/thuoc-tinh/").status_code,
            404,
        )
        center = self.login(self.center)
        self.assertEqual(center.get("/bieu-mau/").status_code, 200)
        self.assertEqual(
            center.get(f"/bieu-mau/{template.pk}/thiet-ke/").status_code, 200
        )
        self.assertEqual(
            center.get(f"/bieu-mau/{template.pk}/xem-truoc/").status_code, 200
        )
        self.assertEqual(center.post("/bieu-mau/tao-moi/").status_code, 403)
        self.assertEqual(
            center.post(f"/bieu-mau/{template.pk}/xuat-ban/").status_code, 403
        )
        self.assertEqual(
            center.post(f"/bieu-mau/{template.pk}/luu-tru/").status_code, 403
        )
        self.assertEqual(
            center.post(f"/bieu-mau/{template.pk}/nhan-ban/").status_code, 403
        )
        self.assertNotContains(self.login(self.officer).get("/"), 'href="/bieu-mau/"')

    def test_admin_lists_every_department(self):
        self.make_template()
        self.make_template(
            name="Techmart",
            phong=self.gdcn,
            user=self.admin,
            activity_type=self.loai_other,
        )
        admin = self.login(self.admin)
        response = admin.get("/bieu-mau/")
        self.assertContains(response, "Biểu mẫu lớp")
        self.assertContains(response, "Techmart")
